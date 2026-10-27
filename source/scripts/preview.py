"""Draw a terrain-data preview; this is not an in-game screenshot."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer

ROOT=Path(__file__).resolve().parents[1]
meta=json.loads((ROOT/'output/map-settings.json').read_text())
h=np.load(ROOT/'output/preview-height.npy')
towns=json.loads((ROOT/'output/towns.json').read_text())
cmap=LinearSegmentedColormap.from_list('baltic',['#bdcaa5','#a8b78d','#d7cca5','#c0ae87','#e3d9c2'])
rgb=LightSource(azdeg=310,altdeg=45).shade(np.maximum(h,0),cmap,vert_exag=.7,dx=16,dy=16,blend_mode='soft')
rgb[h<0]=[.27,.49,.59,1]
fig,ax=plt.subplots(figsize=(12,12),dpi=125)
fig.patch.set_facecolor('#f4f0e6')
ax.imshow(rgb,extent=[-8192,8192,-8192,8192])
lt=shape(json.loads((ROOT/'data/lithuania-boundary.geojson').read_text())['geometry'])
tr=Transformer.from_crs(4326,3346,always_xy=True)
cx=(meta['bounds_lks94'][0]+meta['bounds_lks94'][2])/2
cy=(meta['bounds_lks94'][1]+meta['bounds_lks94'][3])/2
def convert(x,y,z=None):
 x,y=tr.transform(x,y);return (np.asarray(x)-cx)/420000*16384,(np.asarray(y)-cy)/420000*16384
lt=transform(convert,lt)
polys=list(lt.geoms) if lt.geom_type=='MultiPolygon' else [lt]
for p in polys:
 x,y=p.exterior.xy;ax.plot(x,y,color='#faf8ee',lw=1.4,alpha=.95)
major={'Vilnius','Kaunas','Klaipėda','Šiauliai','Panevėžys','Alytus','Marijampolė','Utena','Telšiai','Tauragė','Mažeikiai','Rokiškis','Biržai','Druskininkai','Šilutė','Jurbarkas','Visaginas','Šakiai','Plungė'}
for t in towns:
 ax.scatter(t['x'],t['y'],s=18 if t['name'] in major else 7,color='#173126',edgecolor='#fff8e8',linewidth=.8,zorder=4)
 if t['name'] in major:
  offset=(-7,6) if t['name'] in ['Kaunas','Panevėžys','Jurbarkas'] else (7,6)
  ax.annotate(t['name'],(t['x'],t['y']),xytext=offset,textcoords='offset points',ha='right' if offset[0]<0 else 'left',fontsize=8.5,color='#10261f',bbox=dict(boxstyle='round,pad=.15',fc='#f6f1df',ec='none',alpha=.83),zorder=5)
ax.text(-7350,2900,'BALTIJOS\nJŪRA',fontsize=12,color='#e9f2ef',fontstyle='italic',linespacing=1.7,ha='center')
ax.annotate('N',(7400,7450),ha='center',color='#15362b',fontsize=12,fontweight='bold')
ax.annotate('',(7400,7160),(7400,6680),arrowprops=dict(arrowstyle='-|>',color='#15362b',lw=1.5))
ax.set_xlim(-8192,8192);ax.set_ylim(-8192,8192);ax.axis('off')
fig.text(.07,.948,'LIETUVA',fontsize=30,fontweight='bold',color='#15362b')
fig.text(.07,.916,'Transport Fever 3 · Lithuania-shaped island · population-scaled towns',fontsize=11,color='#496052')
fig.text(.07,.047,'33 towns  /  16.384 × 16.384 km game map  /  16-bit heightmap',fontsize=10,color='#314b40')
fig.text(.07,.027,'DATA PREVIEW · Not an in-game screenshot. Rivers and relief adjusted for gameplay.',fontsize=8,color='#64756b')
fig.subplots_adjust(left=.055,right=.945,bottom=.08,top=.89)
fig.savefig(ROOT/'output/Lietuva_preview.png',facecolor=fig.get_facecolor())
print(ROOT/'output/Lietuva_preview.png')
