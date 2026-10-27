"""Build the TF3 Lithuania import kit from cached, attributed geographic data."""
import io
import json
import math
import time
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy.ndimage import map_coordinates, gaussian_filter, distance_transform_edt
from shapely.geometry import shape, box
from shapely.ops import transform
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = ROOT / '.build'
OUT.mkdir(exist_ok=True)
PIXELS = 4097
GAME_METERS = 16384
REAL_METERS = 420000
MIN_H, MAX_H = -12.0, 180.0
ZOOM = 9
TO_LKS = Transformer.from_crs(4326, 3346, always_xy=True)
TO_LONLAT = Transformer.from_crs(3346, 4326, always_xy=True)

def lua(v):
    if isinstance(v, str):
        return '"' + ''.join('\\%03d' % b for b in v.encode('utf-8')) + '"'
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, list): return '{' + ','.join(lua(x) for x in v) + '}'
    if isinstance(v, dict): return '{' + ','.join('[' + lua(k) + ']=' + lua(x) for k,x in v.items()) + '}'
    raise TypeError(v)

countries = json.loads((DATA / 'countries.geojson').read_text())
country = next(f for f in countries['features'] if f['properties']['ADM0_A3'] == 'LTU')
lt = transform(TO_LKS.transform, shape(country['geometry']))
x0, y0, x1, y1 = lt.bounds
cx, cy = (x0+x1)/2, (y0+y1)/2
west, south = cx-REAL_METERS/2, cy-REAL_METERS/2
east, north = cx+REAL_METERS/2, cy+REAL_METERS/2
bounds = (west, south, east, north)

def project(lon, lat):
    x, y = TO_LKS.transform(lon, lat)
    return (x-cx)/REAL_METERS*GAME_METERS, (y-cy)/REAL_METERS*GAME_METERS

def pixel(lon, lat):
    x, y = TO_LKS.transform(lon, lat)
    return (x-west)/REAL_METERS*(PIXELS-1), (north-y)/REAL_METERS*(PIXELS-1)

def slippy(lon, lat):
    n = 2**ZOOM
    return (lon+180)/360*n, (1-np.arcsinh(np.tan(np.deg2rad(lat)))/np.pi)/2*n

print('Sampling terrain tiles...', flush=True)
xx, yy = np.meshgrid(np.linspace(west,east,PIXELS,dtype='float32'), np.linspace(north,south,PIXELS,dtype='float32'))
lon, lat = TO_LONLAT.transform(xx, yy)
sx, sy = slippy(lon, lat)
tx0, tx1 = int(np.floor(sx.min())), int(np.floor(sx.max()))
ty0, ty1 = int(np.floor(sy.min())), int(np.floor(sy.max()))
cache = DATA / 'tiles'; cache.mkdir(exist_ok=True)
tile_ids = [(x,y) for y in range(ty0,ty1+1) for x in range(tx0,tx1+1)]

def tile(item):
    x,y = item
    filename = cache / f'{ZOOM}-{x}-{y}.png'
    if not filename.exists():
        url = f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{ZOOM}/{x}/{y}.png'
        last = None
        for attempt in range(3):
            try:
                r=requests.get(url,timeout=25);r.raise_for_status()
                im=Image.open(io.BytesIO(r.content));assert im.size==(256,256)
                filename.write_bytes(r.content);break
            except Exception as e:
                last=e;time.sleep(attempt+1)
        else: raise last
    a=np.asarray(Image.open(filename).convert('RGB'),dtype='float32')
    return x,y,a[:,:,0]*256+a[:,:,1]+a[:,:,2]/256-32768

mosaic=np.zeros(((ty1-ty0+1)*256,(tx1-tx0+1)*256),dtype='float32')
with ThreadPoolExecutor(max_workers=8) as pool:
    for count,(x,y,a) in enumerate(pool.map(tile,tile_ids),1):
        mosaic[(y-ty0)*256:(y-ty0+1)*256,(x-tx0)*256:(x-tx0+1)*256]=a
        if count%20==0: print(f'Tiles {count}/{len(tile_ids)}',flush=True)
dem=map_coordinates(mosaic,[(sy-ty0)*256-.5,(sx-tx0)*256-.5],order=1,mode='nearest').astype('float32')
del xx,yy,lon,lat,sx,sy,mosaic
# Preserve sea-level coast while reducing exaggerated compressed-map gradients.
natural=np.clip(gaussian_filter(dem,1.1)*0.5,MIN_H,MAX_H)

river_mask=Image.new('L',(PIXELS,PIXELS));draw=ImageDraw.Draw(river_mask)
used_rivers=[]
river_source='OpenStreetMap'
if (DATA/'rivers-osm.json').exists():
    for way in json.loads((DATA/'rivers-osm.json').read_text())['elements']:
        tags=way.get('tags',{})
        raw_name=tags.get('name:lt',tags.get('name',''))
        river_name='Nemunas' if any(s in raw_name for s in ['Nemunas','Neman','Неман']) else 'Neris' if 'Neris' in raw_name else ''
        if river_name not in ('Nemunas','Neris') or len(way.get('geometry',[]))<2:continue
        draw.line([pixel(p['lon'],p['lat']) for p in way['geometry']],fill=255,width=10 if river_name=='Nemunas' else 6)
        if river_name not in used_rivers:used_rivers.append(river_name)
else:
    river_source='Natural Earth (generalized fallback)'
    for feature in json.loads((DATA/'rivers-region.geojson').read_text())['features']:
        river_name=feature['properties'].get('name')
        if river_name not in ('Neman','Neris'):continue
        g=shape(feature['geometry'])
        lines=list(g.geoms) if g.geom_type=='MultiLineString' else [g]
        for line in lines:draw.line([pixel(x,y) for x,y,*_ in line.coords],fill=255,width=10 if river_name=='Neman' else 6)
        used_rivers.append(river_name)
water=np.asarray(river_mask)>0
for feature in json.loads((DATA/'lakes-region.geojson').read_text())['features']:
    if feature['properties'].get('name')!='Kauno marios':continue
    g=shape(feature['geometry'])
    polys=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
    for poly in polys:draw.polygon([pixel(x,y) for x,y,*_ in poly.exterior.coords],fill=255)
water=np.asarray(river_mask)>0
distance=distance_transform_edt(~water)
weight=np.exp(-(distance/14)**2).astype('float32')
playable=natural*(1-weight)+(-3.0)*weight
playable[water]=-3
del distance,weight

# Fictional island edition: preserve Lithuania's national outline, with a
# gradual beach inside the border and a shallow shelf outside it.
outline_image=Image.new('L',(PIXELS,PIXELS))
outline_draw=ImageDraw.Draw(outline_image)
polygons=list(lt.geoms) if lt.geom_type=='MultiPolygon' else [lt]
def boundary_pixel(x,y):
    return ((x-west)/REAL_METERS*(PIXELS-1),(north-y)/REAL_METERS*(PIXELS-1))
for poly in polygons:
    outline_draw.polygon([boundary_pixel(x,y) for x,y in poly.exterior.coords],fill=255)
    for ring in poly.interiors:
        outline_draw.polygon([boundary_pixel(x,y) for x,y in ring.coords],fill=0)
island=np.asarray(outline_image)>0
inside=distance_transform_edt(island)
outside=distance_transform_edt(~island)
playable=np.where(island,np.minimum(playable,inside*.9),-np.clip(outside*.5,.5,12)).astype('float32')
del inside,outside

desired=['Vilnius','Kaunas','Klaipėda','Šiauliai','Panevėžys','Alytus','Marijampolė','Utena','Telšiai','Tauragė','Palanga','Mažeikiai','Jonava','Kėdainiai','Ukmergė','Visaginas','Druskininkai','Šilutė','Rokiškis','Biržai','Plungė','Kretinga','Jurbarkas','Raseiniai','Anykščiai','Šakiai','Vilkaviškis','Molėtai','Ignalina','Švenčionys','Pasvalys','Pakruojis','Radviliškis']
elements=json.loads((DATA/'towns-osm.json').read_text())['elements']
byname={e['tags'].get('name'):e for e in elements}
assert all(n in byname for n in desired)
towns=[];records=[]
land_distance=distance_transform_edt(playable>0)
for name in desired:
    e=byname[name];px,py=pixel(e['lon'],e['lat']);px,py=round(px),round(py)
    ox,oy=px,py
    # Select a dry town centre near the OSM point, not in a widened river.
    candidates=[]
    for dy in range(-36,37,4):
        for dx in range(-36,37,4):
            x,y=px+dx,py+dy
            if playable[y,x]>3 and land_distance[y,x]>10:candidates.append((dx*dx+dy*dy,x,y))
    assert candidates, 'No dry town site for '+name
    _,px,py=min(candidates)
    # Cached OSM population tags are approximate and not a uniform census year.
    # Use a uniform 1:1000 scale, with a 25-resident floor for playable small towns.
    population=int(e['tags']['population'])
    size=max(25,round(population/1000))
    capacities=[size,size,size]
    x=(px/(PIXELS-1)-.5)*GAME_METERS;y=(.5-py/(PIXELS-1))*GAME_METERS
    towns.append({'name':name,'position':{'x':round(x,2),'y':round(y,2)},'sizeFactors':[v/100 for v in capacities],'initialLandUseCapacities':capacities})
    records.append({'name':name,'osm_id':e['id'],'lon':e['lon'],'lat':e['lat'],'x':x,'y':y,'game_offset_m':round(math.hypot(px-ox,py-oy)*4,1),'population_reference':population,'population_date':e['tags'].get('population:date','unknown'),'starting_capacities':capacities})
    # Keep building pads small and avoid flattening the shoreline itself.
    r=24;patch=playable[py-r:py+r+1,px-r:px+r+1];gy,gx=np.mgrid[-r:r+1,-r:r+1]
    blend=np.clip((r-np.hypot(gx,gy))/12,0,1).astype('float32')
    blend[patch<=0]=0
    level=float(np.median(patch[patch>0]));patch[:]=patch*(1-blend)+level*blend

def write_height(name,height):
    pixels=np.round((np.clip(height,MIN_H,MAX_H)-MIN_H)/(MAX_H-MIN_H)*65535).astype('uint16')
    Image.fromarray(pixels).save(OUT/name)
    assert Image.open(OUT/name).size==(PIXELS,PIXELS)
write_height('Lietuva_4097_playable.png',playable)
write_height('Lietuva_4097_natural.png',natural)
np.save(OUT/'preview-height.npy',playable[::4,::4])
(OUT/'Lietuva_33_towns.lua').write_text('function data()\nreturn '+lua({'towns':towns,'industries':[]})+'\nend\n')
(OUT/'towns.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
(DATA/'lithuania-boundary.geojson').write_text(json.dumps(country,ensure_ascii=False))

# A separate optional layout: game industries, not real-world business locations.
industry_plan=[('farm','Pakruojis',(-200,160)),('farm','Kėdainiai',(240,180)),('farm','Vilkaviškis',(-220,-180)),
 ('forest','Utena',(240,-190)),('forest','Rokiškis',(-200,180)),('forest','Druskininkai',(190,230)),
 ('saw_mill','Alytus',(-220,180)),('saw_mill','Telšiai',(230,-180)),
 ('food_factory','Kaunas',(260,-190)),('food_factory','Panevėžys',(-230,170)),
 ('brewery','Biržai',(-200,-200)),('brewery','Šiauliai',(-250,-180)),
 ('furniture_factory','Vilnius',(230,200)),('furniture_factory','Klaipėda',(250,160)),
 ('paper_mill','Jonava',(220,190)),('printing_press','Marijampolė',(220,200))]
industries=[]
for kind,town_name,(dx,dy) in industry_plan:
    town=next(t for t in towns if t['name']==town_name);x=town['position']['x']+dx;y=town['position']['y']+dy
    px=round((x/GAME_METERS+.5)*(PIXELS-1));py=round((.5-y/GAME_METERS)*(PIXELS-1))
    candidates=[]
    for dy2 in range(-50,51,4):
        for dx2 in range(-50,51,4):
            nx,ny=px+dx2,py+dy2
            wx=(nx/4096-.5)*GAME_METERS;wy=(.5-ny/4096)*GAME_METERS
            far_from_towns=all(math.hypot(wx-t['position']['x'],wy-t['position']['y'])>150 for t in towns)
            far_from_industries=all(math.hypot(wx-t['position']['x'],wy-t['position']['y'])>140 for t in industries)
            if playable[ny,nx]>3 and land_distance[ny,nx]>20 and far_from_towns and far_from_industries:
                candidates.append((dx2*dx2+dy2*dy2,nx,ny,wx,wy))
    assert candidates, 'No dry industrial site near '+town_name
    _,px,py,x,y=min(candidates)
    industries.append({'position':{'x':x,'y':y},'angle':0,'onWater':False,
        'fileName':f'::/industries/{kind}/{kind}.con','tag':kind})
(OUT/'Lietuva_33_towns_starter_industries.lua').write_text('function data()\nreturn '+lua({'towns':towns,'industries':industries})+'\nend\n')
(OUT/'industries.json').write_text(json.dumps(industries,ensure_ascii=False,indent=2))
allnames=sorted({e['tags'].get('name') for e in elements if e['tags'].get('name')})
streets=['Vilniaus gatvė','Kauno gatvė','Klaipėdos gatvė','Vytauto gatvė','Gedimino gatvė','Dariaus ir Girėno gatvė','Laisvės alėja','J. Basanavičiaus gatvė','Maironio gatvė','Žemaitės gatvė','S. Daukanto gatvė','Taikos prospektas','Respublikos gatvė','Stoties gatvė','Turgaus gatvė','Parko gatvė','Miško gatvė','Sodų gatvė','Naujoji gatvė','Birutės gatvė']
script='function data()\nreturn {\n towns = function(_capture, params)\n local names='+lua(allnames)+'\n local result={}\n for i=1,params.num do result[i]=names[(i-1)%#names+1] end\n return result\n end,\n streets = function(_capture, params)\n local names='+lua(streets)+'\n local result={}\n for i=1,params.num do result[i]=names[(i-1)%#names+1] end\n return result\n end,\n}\nend\n'
(ROOT/'mod/content/names/lithuania/names.script.lua').write_text(script)
manifest={'name':'Lietuva','pixels':PIXELS,'game_size_m':GAME_METERS,'real_coverage_m':REAL_METERS,'crs':'EPSG:3346','bounds_lks94':bounds,'height_import_min':MIN_H,'height_import_max':MAX_H,'water_level':0,'vertical_scale':.5,'horizontal_compression':REAL_METERS/GAME_METERS,'source_zoom':ZOOM,'source_tiles':len(tile_ids),'towns':len(towns),'name_set_count':len(allnames),'optional_industries':len(industries),'waterways':used_rivers,'river_source':river_source,'max_town_adjustment_m':max(r['game_offset_m'] for r in records),'height_range_playable':[float(playable.min()),float(playable.max())],'caveat':'Playable waterways are widened and lowered to shared sea level. Industry locations are game design.'}
(OUT/'map-settings.json').write_text(json.dumps(manifest,indent=2))
manifest.update({'edition':'Lithuania-shaped island v2','population_scale':1000,'minimum_residential_capacity':25,'population_source':'Cached OpenStreetMap population tags; mixed or unknown dates, approximate relative sizes, not current census counts.','caveat':'Fictional island following Lithuania national borders. Rivers widened and lowered to shared sea level. Industry locations are game design.'})
(OUT/'map-settings.json').write_text(json.dumps(manifest,indent=2))
final=ROOT/'output';final.mkdir(exist_ok=True)
for p in OUT.iterdir():p.replace(final/p.name)
OUT.rmdir()
print(json.dumps(manifest,indent=2),flush=True)
