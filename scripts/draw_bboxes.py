#!/usr/bin/env python3
"""Label QA: draw the YOLO boxes over the rendered images.

Reads <dataset>/images/*.png and <dataset>/labels/*.txt (YOLO format:
"class cx cy w h", normalised to 0..1), draws every box with its class name
and writes annotated copies to <dataset>/qa/ (inside the gitignored dataset/
folder by default). Open them to check that the boxes sit on the pangolins
before training.

It also prints problems it can detect without looking at the pixels:
  - images without a label file, label files without an image
  - malformed lines, unknown class ids
  - coordinates outside 0..1, boxes that extend past the image edge
  - very small boxes (default: under 8 px on a side)
  - label files that disagree with metadata.json (if present)

Requires Pillow:  pip install pillow

Examples:
  python scripts/draw_bboxes.py                      # all images in dataset/
  python scripts/draw_bboxes.py --limit 5            # first 5 images
  python scripts/draw_bboxes.py --images 002 013     # specific images
  python scripts/draw_bboxes.py --dataset path/to/dataset --out /tmp/qa

Exit code is 1 if any problem was found, so it can run in CI.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
COLORS = ["#ff3b30", "#34c759", "#0a84ff", "#ffcc00", "#af52de", "#ff9500"]


def read_classes(dataset: Path) -> list[str]:
    path = dataset / "classes.txt"
    if path.exists():
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return []


def read_labels(path: Path, problems: list[str]) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        try:
            if len(parts) != 5:
                raise ValueError
            cls = int(parts[0])
            cx, cy, w, h = (float(v) for v in parts[1:])
        except ValueError:
            problems.append(f"{path.name}:{n}: malformed line {line!r}")
            continue
        boxes.append((cls, cx, cy, w, h))
    return boxes


def check_box(name: str, i: int, box, img_w: int, img_h: int, n_classes: int,
              min_px: float, problems: list[str]) -> None:
    cls, cx, cy, w, h = box
    tag = f"{name} box {i}"
    if n_classes and not 0 <= cls < n_classes:
        problems.append(f"{tag}: class id {cls} not in classes.txt")
    if not all(0.0 <= v <= 1.0 for v in (cx, cy, w, h)):
        problems.append(f"{tag}: coordinates outside 0..1 ({cx:.3f} {cy:.3f} {w:.3f} {h:.3f})")
    eps = 1e-4
    if cx - w / 2 < -eps or cx + w / 2 > 1 + eps or cy - h / 2 < -eps or cy + h / 2 > 1 + eps:
        problems.append(f"{tag}: box extends past the image edge")
    if w * img_w < min_px or h * img_h < min_px:
        problems.append(f"{tag}: tiny box {w * img_w:.1f}x{h * img_h:.1f} px")


def check_metadata(dataset: Path, labels: dict[str, list], problems: list[str]) -> None:
    path = dataset / "metadata.json"
    if not path.exists():
        return
    try:
        entries = json.loads(path.read_text()).get("images", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        problems.append(f"metadata.json: cannot parse ({exc})")
        return
    for entry in entries:
        stem = Path(entry.get("image", "")).stem
        if stem not in labels:
            continue
        meta = [(b["x"], b["y"], b["w"], b["h"]) for b in entry.get("bboxes", [])]
        lab = [b[1:] for b in labels[stem]]
        if len(meta) != len(lab):
            problems.append(f"{stem}: metadata.json has {len(meta)} boxes, label file has {len(lab)}")
            continue
        for i, (m, l) in enumerate(zip(meta, lab)):
            if any(abs(a - b) > 1e-4 for a, b in zip(m, l)):
                problems.append(f"{stem} box {i}: metadata.json and label file disagree")


def draw(img: Image.Image, boxes, classes: list[str]) -> Image.Image:
    img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    W, H = img.size
    width = max(2, round(min(W, H) / 300))
    try:
        font = ImageFont.load_default(size=max(14, H // 50))
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    for i, (cls, cx, cy, w, h) in enumerate(boxes):
        color = COLORS[cls % len(COLORS)]
        x0, y0 = (cx - w / 2) * W, (cy - h / 2) * H
        x1, y1 = (cx + w / 2) * W, (cy + h / 2) * H
        d.rectangle([x0, y0, x1, y1], outline=color, width=width)
        name = classes[cls] if 0 <= cls < len(classes) else str(cls)
        text = f"{i}:{name}"
        tb = d.textbbox((0, 0), text, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        ty = y0 - th - 2 * width if y0 - th - 2 * width >= 0 else y1 + width
        tx = min(max(0, x0), W - tw - 2 * width)
        d.rectangle([tx, ty, tx + tw + 2 * width, ty + th + 2 * width], fill=color)
        d.text((tx + width, ty + width - tb[1]), text, fill="black", font=font)
    d.text((10, 10), f"{len(boxes)} box(es)", fill="white", font=font,
           stroke_width=2, stroke_fill="black")
    return img


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", type=Path, default=repo / "dataset",
                    help="dataset folder with images/ and labels/ (default: ./dataset)")
    ap.add_argument("--out", type=Path, help="output folder (default: <dataset>/qa)")
    ap.add_argument("--images", nargs="+", metavar="STEM",
                    help="only these images, by file stem (e.g. 002 013)")
    ap.add_argument("--limit", type=int, help="only the first N images")
    ap.add_argument("--min-px", type=float, default=8.0,
                    help="flag boxes smaller than this many pixels on a side (default: 8)")
    ap.add_argument("--max-width", type=int, default=1280,
                    help="downscale output images to this width; 0 keeps full size (default: 1280)")
    args = ap.parse_args()

    dataset = args.dataset.resolve()
    img_dir, lbl_dir = dataset / "images", dataset / "labels"
    if not img_dir.is_dir() or not lbl_dir.is_dir():
        print(f"error: {dataset} needs images/ and labels/ folders", file=sys.stderr)
        return 2
    out = (args.out or dataset / "qa").resolve()

    classes = read_classes(dataset)
    images = {p.stem: p for p in sorted(img_dir.iterdir()) if p.suffix.lower() in IMAGE_EXTS}
    label_files = {p.stem: p for p in sorted(lbl_dir.glob("*.txt"))}
    problems: list[str] = []

    for stem in sorted(set(label_files) - set(images)):
        problems.append(f"{stem}: label file without image")

    stems = sorted(images)
    if args.images:
        missing = [s for s in args.images if s not in images]
        if missing:
            print(f"error: no such image(s): {' '.join(missing)}", file=sys.stderr)
            return 2
        stems = args.images
    if args.limit:
        stems = stems[: args.limit]

    out.mkdir(parents=True, exist_ok=True)
    labels: dict[str, list] = {}
    n_boxes = 0
    for stem in stems:
        if stem not in label_files:
            problems.append(f"{stem}: image without label file")
            boxes = []
        else:
            boxes = read_labels(label_files[stem], problems)
            labels[stem] = boxes
        with Image.open(images[stem]) as img:
            for i, box in enumerate(boxes):
                check_box(stem, i, box, img.width, img.height, len(classes), args.min_px, problems)
            annotated = draw(img, boxes, classes)
        if args.max_width and annotated.width > args.max_width:
            ratio = args.max_width / annotated.width
            annotated = annotated.resize((args.max_width, round(annotated.height * ratio)))
        annotated.save(out / f"{stem}.jpg", quality=90)
        n_boxes += len(boxes)

    check_metadata(dataset, labels, problems)

    print(f"Drew {n_boxes} box(es) on {len(stems)} image(s) -> {out}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("No problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
