# tiles/

Each subfolder is one **tile** — an agent bound to (at most) one connector.

```
tiles/<tile_id>/
  manifest.yaml   # TileManifest: id, name, connector?, model?, instructions,
                  #               allowed_tools, permission_tier, provides/consumes
  handler.py      # implements tiles_ai.contracts.Tile
  README.md       # what this tile does + how to configure it
```

To author a tile: copy a reference folder, edit `manifest.yaml`, implement
`run` in `handler.py`. A tile with no `connector` is an "instant" tile (no app,
no credentials). A tile with no `model` uses the global default brain. See
[`../SPEC.md`](../SPEC.md).
