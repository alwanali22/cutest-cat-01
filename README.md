# Noir Hugs a Fish — cutest-cat v4

A black kitten with big amber eyes hugs a big pink fish plush.
Entry for the make.fun `cutest-cat-01` competition.

## Run

```sh
python3 main.py
```

Writes one picture to `/output/entry.png` (or `out/entry.png` when
`/output` is not writable). PNG, 1024×1024, under 1 MiB.

## Notes

- Pure Python 3.13 standard library: a small supersampled rasterizer
  (ellipses, polygons, thick lines, arcs) plus a minimal PNG writer.
- Deterministic: two runs produce byte-identical output. No network,
  no files read.
