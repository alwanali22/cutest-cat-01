# Milo in a Teacup — cutest-cat-01 entry (v2)

A sleepy cream kitten curled inside a big teal teacup: paws draped over the
rim, big droopy-but-bright amber eyes, a curled tail peeking out, steam
wisps curling up, and a tiny fish biscuit waiting on the saucer.

The program is pure Python 3.13 standard library: its own rasterizer (2x
supersampled span fills, box downsample) and its own PNG encoder. It writes
one deterministic picture to `/output/entry.png` (1024x1024).

Run it: `mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py`
