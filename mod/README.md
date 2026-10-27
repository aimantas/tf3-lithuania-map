# Lietuva: Lithuania Island Map for Transport Fever 3

A Lithuania-shaped island built from real geographic data. Real terrain, rivers, 33 towns in their real places sized by population, 16 optional starter industries and a Lithuanian town-name set.

## Install

1. Put this folder in your Transport Fever 3 `mods` folder (Mod Hub does this for you) and enable **Lietuva: Lithuania Island Map**.
2. Copy `map-kit/heightmaps/*` into the `heightmaps` folder and `map-kit/towns_industries/*` into the `towns_industries` folder of your Transport Fever 3 local userdata directory. Both sit next to `mods`.

## Make the map

Gotchas from testing on 27 Oct 2026: in the heightmap dialog press **Return** after typing each number, or the old value stays and the terrain comes out about 16 times too high. In the towns import list, pick the `Lietuva_33_…` row: if a file called `request` is listed, don't select it.

1. Main menu: **Map Editor**, new map, **Temperate**, **Very Large**, **1:1**. Optional: choose the **Lietuviški / Lithuanian** town-name set.
2. Heightmap import: `Lietuva_4097_playable.png`, minimum height **-12**, maximum **180**, water level **0**. Baltic Sea and the Curonian Lagoon should be on the west side.
3. Towns and industries import: `Lietuva_33_towns_starter_industries` (or `Lietuva_33_towns` for towns only). Use an empty map so nothing duplicates.
4. Connect towns with the editor's road tool, save the map, start a new game from it.

`Lietuva_4097_natural.png` keeps the rivers at their real heights. It looks closer to the real country but most rivers are not navigable at a single sea level.

## What is real and what is game design

| Part | Source | Adjusted for the game |
| --- | --- | --- |
| Terrain | Mapzen Terrain Tiles (EU-DEM, SRTM, ETOPO1) | 420 km squeezed into 16.384 km (about 25.6x), heights halved |
| Coast | Lithuania's national border | Fictional island: everything outside the border is sea |
| Rivers | OpenStreetMap Nemunas and Neris | Widened and lowered to sea level so ships can use them |
| Towns | OpenStreetMap place nodes, population tags | Population / 1,000, minimum 25 residents of capacity. Tags have mixed dates |
| Industries | None | Placed by hand for a starter economy |

## Files

- `content/names`: the Lietuviški / Lithuanian name set (357 town names, 20 street-name examples; person names use the base UK set).
- `map-kit/heightmaps`: two 16-bit 4097 x 4097 PNG heightmaps.
- `map-kit/towns_industries`: two Map Editor presets.
- `map-kit/reference`: map settings, town and industry tables, OpenStreetMap source snapshots, terrain attribution.

Data notices: see `ATTRIBUTION.md`. Story of how the map was made: https://aimantas.com/writing/lithuania-transport-fever-3-map/
