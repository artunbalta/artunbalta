#!/usr/bin/env python3
"""Prepare a source photo for ASCII conversion.

Pipeline:
    1. Remove the background with ``rembg`` so the subject is isolated.
    2. Boost local contrast with OpenCV CLAHE (contrast-limited adaptive
       histogram equalization) so a flat face gains real highlights/shadows.
    3. Composite onto a PURE WHITE background (so the background maps to the
       blank end of the ASCII ramp).
    4. Convert to grayscale.

    python scripts/prep_photo.py [source-photo.png]  ->  source-prepped.png

The heavy libs (rembg / opencv / numpy / pillow) are imported lazily so the
daily CI job, which never runs this script, doesn't need them installed.
If the input photo is missing, this prints instructions and exits non-zero
WITHOUT crashing the rest of the pipeline (the README still works without a
portrait — make_ascii_svg.py falls back to a placeholder).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = "source-photo.png"
OUT = ROOT / "source-prepped.png"


def main(argv):
    src_name = argv[1] if len(argv) > 1 else DEFAULT_SRC
    src = Path(src_name)
    if not src.is_absolute():
        src = ROOT / src_name

    if not src.exists():
        print(
            f"No source photo found at '{src_name}'.\n"
            f"  -> Drop a photo named '{DEFAULT_SRC}' in the repo root, then run:\n"
            f"       python scripts/prep_photo.py\n"
            f"       python scripts/make_ascii_svg.py\n"
            f"The README still renders without it (a placeholder portrait is used).",
            file=sys.stderr,
        )
        return 1

    # Lazy heavy imports (only needed when a photo actually exists).
    import cv2
    import numpy as np
    from PIL import Image
    from rembg import new_session, remove

    print(f"Loading {src.name} ...")
    img = Image.open(src).convert("RGBA")

    # isnet-general-use segments the whole subject far better than the default
    # u2net when a dark object (here the black mortarboard) sits against a dark
    # background — u2net sliced the cap's left corner off. Override with
    # REMBG_MODEL if needed.
    model = os.environ.get("REMBG_MODEL", "isnet-general-use")
    print(f"Removing background with rembg ({model}; first run downloads it)...")
    session = new_session(model)
    cut = remove(img, session=session)  # RGBA with background made transparent
    if cut.mode != "RGBA":
        cut = cut.convert("RGBA")

    rgba = np.array(cut)
    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    # Drop faint (<0.3) semi-transparent halo so leftover background smudges map
    # to pure white -> blank in the ASCII, without eroding the solid subject.
    alpha[alpha < 0.3] = 0.0

    print("Boosting local contrast with CLAHE ...")
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    print("Compositing onto pure white + converting to grayscale ...")
    gray_f = gray.astype(np.float32)
    # subject luminance where opaque, pure white (255) where transparent
    composited = gray_f * alpha + 255.0 * (1.0 - alpha)
    out = np.clip(composited, 0, 255).astype(np.uint8)

    Image.fromarray(out, mode="L").save(OUT)
    print(f"Wrote {OUT.relative_to(ROOT)}  ({out.shape[1]}x{out.shape[0]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
