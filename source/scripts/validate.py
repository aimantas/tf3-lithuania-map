"""Validate import assets, geography and dependencies without executing TF3."""
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image
from PIL import ImageDraw
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'
m=json.loads((OUT/'map-settings.json').read_text())
towns=json.loads((OUT/'towns.json').read_text())
assert len(towns)==33 and len({t['name'] for t in towns})==33
for file in ['Lietuva_4097_playable.png','Lietuva_4097_natural.png']:
 b=(OUT/file).read_bytes()
 width,height,depth,color=struct.unpack('>IIBB',b[16:26])
 assert (width,height,depth,color)==(4097,4097,16,0), (file,width,height,depth,color)
 a=np.asarray(Image.open(OUT/file))
 assert np.ptp(a)>40000 and not np.isnan(a).any()
a=np.asarray(Image.open(OUT/'Lietuva_4097_playable.png'))/65535*(m['height_import_max']-m['height_import_min'])+m['height_import_min']
if m.get('edition')=='Lithuania-shaped island v2':
 boundary=shape(json.loads((ROOT/'data/lithuania-boundary.geojson').read_text())['geometry'])
 boundary=transform(Transformer.from_crs(4326,3346,always_xy=True).transform,boundary)
 mask=Image.new('L',(4097,4097));draw=ImageDraw.Draw(mask)
 west,south,east,north=m['bounds_lks94']
 def point(x,y):return ((x-west)/(east-west)*4096,(north-y)/(north-south)*4096)
 for polygon in list(boundary.geoms) if boundary.geom_type=='MultiPolygon' else [boundary]:
  draw.polygon([point(x,y) for x,y in polygon.exterior.coords],fill=255)
  for ring in polygon.interiors:draw.polygon([point(x,y) for x,y in ring.coords],fill=0)
 assert np.all(a[np.asarray(mask)==0]<0),'Land remains outside the national outline'
 capacities={t['name']:t['starting_capacities'][0] for t in towns}
 assert capacities['Vilnius']>capacities['Kaunas']>capacities['Klaipėda']>capacities['Šiauliai']>capacities['Panevėžys']
 assert capacities['Kaunas']==316 and min(capacities.values())>=25
for t in towns:
 assert abs(t['x'])<8192 and abs(t['y'])<8192
 px=round((t['x']/16384+.5)*4096);py=round((.5-t['y']/16384)*4096)
 assert a[py,px]>0, t['name']+' town in water'
industries=json.loads((OUT/'industries.json').read_text())
assert len(industries)==16
for t in industries:
 px=round((t['position']['x']/16384+.5)*4096);py=round((.5-t['position']['y']/16384)*4096)
 assert a[py,px]>0,'Industry in water'
nearest=min(math.hypot(t['x']-s['x'],t['y']-s['y']) for i,t in enumerate(towns) for s in towns[i+1:])
assert nearest>250, 'Town centres too close for the chosen scale'
game=Path.home()/'Library/Application Support/Steam/steamapps/common/Transport Fever 3'
industry_plan=['farm','forest','saw_mill','food_factory','brewery','furniture_factory','paper_mill','printing_press']
for name in industry_plan:
 with zipfile.ZipFile(game/f'base/content/industries/{name}.zip') as z:
  assert f'{name}/{name}.con.lua' in z.namelist(),name
for p in (ROOT/'mod').rglob('*.json'):json.loads(p.read_text())
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ['.png','.lua']}
(OUT/'checksums.json').write_text(json.dumps(hashes,indent=2))
print(f'PASS: 16-bit grayscale PNGs, 33 unique dry-land towns, minimum town spacing {nearest:.0f}m, 8 valid TF3 industry resources, valid manifests; island outline and city-capacity ordering verified when applicable.')
