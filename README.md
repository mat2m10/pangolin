# pangolin

Procedural Blender pipeline that builds a rigged 3D pangolin, scatters posed
pangolins through a forest scene, renders the scene with Eevee and writes
YOLO-format bounding-box labels. The output is a synthetic object-detection
dataset intended for training a pangolin detector (see
[pangolin_detector](https://github.com/mat2m10/pangolin_detector)).

Status: proof of concept. The repo currently holds a 20-image sample dataset
(37 boxes) in `dataset/`.

## Requirements

- **Blender 4.4** (all `.blend` files were saved with 4.4; older versions may
  not open them).
- The third-party `.glb` vegetation models in an `assets/` folder next to the
  `.blend` files (see [Assets](#assets)). `assets/` is gitignored, so **a fresh
  clone cannot generate images until you add them**.

## Repository layout

| File | What it is |
| --- | --- |
| `rig.blend` | Armature (15 bones) for the pangolin |
| `body.blend`, `head.blend`, `leg.blend`, `scales.blend` | Procedural builders for each body part |
| `character.blend`, `assembly.blend` | Parts assembled onto the rig. `assembly.blend` is the pangolin the forest generator imports (`PANGOLIN_BLEND`) |
| `forest_generation.blend` | **Entry point.** Forest scene plus the generator scripts |
| `forest.blend`, `forest_v2.blend` | Earlier versions of the forest scene |
| `dataset/` | Generated sample dataset (images, YOLO labels, `metadata.json`, `dataset.yaml`) |
| `dataset_generation.log` | Log of the run that produced `dataset/` |

All code currently lives inside the `.blend` files as Blender text blocks
(Scripting workspace), not as `.py` files in the repo.

## Generating a dataset

1. Put the `.glb` assets in `assets/` (next to `forest_generation.blend`).
2. Open `forest_generation.blend` in Blender 4.4.
3. Go to the **Scripting** workspace. The file has two text blocks:
   - `Text`: the dataset generator ("PANGOLIN DATASET GENERATOR v3").
     Settings are in its `CONTROL PANEL` section at the top (`NUM_IMAGES`,
     pangolin count/scale/exposure ranges, camera height and tilt, render
     size and samples).
   - `Text.001`: the forest/pangolin scene builder. The generator executes it,
     so you normally do not run it yourself.
4. Select `Text` and press **Run Script**.

For each image the generator places 2 to 6 pangolins in random poses
(standing, walking, relaxed, partial curl, ball, tail curl) and sizes, moves the camera, renders, and
projects each pangolin's meshes to a 2D box. Pangolins that end up completely
off-screen get no box. Output goes to `dataset/` next to the `.blend`:

```
dataset/
  images/000.png ...        rendered frames
  labels/000.txt ...        YOLO labels: class cx cy w h (normalised)
  classes.txt               one class: pangolin
  metadata.json             per image: seed, pangolins placed/visible, boxes
  dataset.yaml              YOLO dataset config
```

Progress is written to `dataset_generation.log`. Image `i` uses seed
`1000 + i`.

Known limitations:

- Generation runs from the Blender GUI only. There is no headless/CLI entry
  point yet.
- The generator writes absolute paths (the `\\wsl.localhost\...` path of the
  machine it ran on) into `dataset.yaml` and the log, and sets both `train` and
  `val` to `images`. Fix `dataset.yaml` before training.

## Training

Train with Ultralytics YOLO, pointing it at `dataset/dataset.yaml`, e.g.
`yolo detect train data=dataset/dataset.yaml model=yolo11n.pt`. Training and
inference otherwise live in
[pangolin_detector](https://github.com/mat2m10/pangolin_detector), which
consumes this dataset.

## Assets

The forest uses these `.glb` models, loaded from `assets/`:

- `spruce_tree.glb`
- `realistic_tree_2_free.glb`
- `petiolate_oak_tree.glb`
- `linden_tree.glb`
- `fir_tree.glb`
- `bush_cover__freefire.glb`
- `greenhouse_foliage.glb`
- `florida_foliage.glb`

> **TODO (owner): source and licence of the `.glb` assets.**
> For each model above, add where it was downloaded from (URL), its author and
> its licence (e.g. CC-BY 4.0, CC0, Sketchfab Standard), plus any attribution
> the licence requires. The forest `.blend` files may embed these models, and
> this repository is public, so check that redistribution is allowed.

## Licence

No licence has been chosen yet for the code and the pangolin models in this
repository.
