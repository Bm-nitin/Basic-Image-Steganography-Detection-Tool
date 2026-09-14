"""
Phase G2 — Diverse evaluation corpus generator.

Generates a deterministic, reproducible, purely-synthetic corpus covering the
image classes requested in the G2 spec. This is NOT real-world photography,
scanned documents, or screenshots -- it is programmatically constructed proxy
content built to exhibit the *statistical characteristics* each class is
concerned with (large flat regions, sharp text-like edges, low color count,
alpha variation, natural-looking texture, etc.), using only PIL/NumPy/SciPy.

This is stated plainly, not glossed over: every "photograph" and "screenshot"
sample below is a synthetic proxy for that class, not an actual photograph or
UI capture. Real-world validation with genuine photographs/screenshots/scans
is a follow-up need, not something this generator can substitute for (no
network access is available in this environment to source real licensed
images, and no image should be fabricated to *look* more authentic than it
is).

No production scoring code is imported for anything other than read-only
analysis by the separate baseline runner -- this file only builds images and
records ground truth.
"""
import os
import json
import hashlib
from io import BytesIO
from typing import Dict, Any, List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

RNG_SEED_BASE = 20260101  # deterministic, arbitrary, fixed for reproducibility
IMG_SIZE = 256


def _seeded_rng(label: str) -> np.random.RandomState:
    """Deterministic per-label RNG so regenerating the corpus is reproducible."""
    h = int(hashlib.sha256(label.encode('utf-8')).hexdigest()[:8], 16)
    return np.random.RandomState((RNG_SEED_BASE + h) % (2**32 - 1))


# ---------------------------------------------------------------------------
# Per-class clean-image builders
# ---------------------------------------------------------------------------

def build_photograph_proxy(size=IMG_SIZE) -> Image.Image:
    """
    Synthetic proxy for natural photographic texture: smoothed correlated
    noise per channel (mimics natural pixel-to-pixel correlation and gradual
    tonal variation), not an actual photograph.
    """
    rng = _seeded_rng('photograph')
    channels = []
    for base, spread in [(90, 60), (110, 55), (130, 50)]:
        noise = rng.normal(0, 1.0, (size, size))
        smooth = gaussian_filter(noise, sigma=8)
        smooth = (smooth - smooth.min()) / (smooth.max() - smooth.min())
        channels.append((base + spread * smooth).astype(np.uint8))
    arr = np.stack(channels, axis=2)
    # light fine-grain sensor-noise-like texture on top of the smooth base
    fine = rng.normal(0, 4.0, arr.shape)
    arr = np.clip(arr.astype(np.float32) + fine, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode='RGB')


def build_screenshot_proxy(size=IMG_SIZE) -> Image.Image:
    """Synthetic UI-like layout: flat light background, solid-color widgets, thin borders."""
    img = Image.new('RGB', (size, size), color=(245, 246, 248))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, size - 1, 28], fill=(60, 90, 160))  # title bar
    draw.rectangle([10, 40, size - 10, 80], fill=(255, 255, 255), outline=(200, 200, 205))
    draw.rectangle([10, 90, 110, 130], fill=(70, 130, 180), outline=(50, 100, 150))  # button 1
    draw.rectangle([120, 90, 220, 130], fill=(220, 90, 90), outline=(180, 60, 60))  # button 2
    for y in range(150, 230, 20):
        draw.line([10, y, size - 10, y], fill=(210, 210, 215), width=1)
    draw.rectangle([10, 235, 60, 246], fill=(30, 30, 30))  # small icon block
    return img


def build_document_proxy(size=IMG_SIZE) -> Image.Image:
    """
    Synthetic scanned-document/marksheet-like proxy: large white background,
    black horizontal text-like bars, a table grid, and a colored logo block --
    matching the characteristics flagged in the original audit.
    """
    rng = _seeded_rng('document')
    img = Image.new('RGB', (size, size), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([15, 10, 55, 35], fill=(30, 70, 150))  # logo block
    y = 50
    while y < size - 20:
        width = int(rng.randint(60, size - 30))
        draw.rectangle([15, y, 15 + width, y + 6], fill=(10, 10, 10))
        y += 16
    # table grid
    for gx in range(15, size - 10, 40):
        draw.line([gx, size - 90, gx, size - 10], fill=(120, 120, 120), width=1)
    for gy in range(size - 90, size - 5, 16):
        draw.line([15, gy, size - 15, gy], fill=(120, 120, 120), width=1)
    return img


def build_illustration_proxy(size=IMG_SIZE) -> Image.Image:
    """Flat-color synthetic illustration: solid geometric shapes, sharp edges, no gradients."""
    img = Image.new('RGB', (size, size), color=(235, 225, 200))
    draw = ImageDraw.Draw(img)
    draw.ellipse([30, 30, 150, 150], fill=(210, 60, 60))
    draw.polygon([(160, 40), (230, 120), (140, 180)], fill=(60, 140, 90))
    draw.rectangle([40, 170, 130, 230], fill=(60, 90, 190))
    draw.rectangle([150, 190, 230, 240], fill=(230, 200, 40))
    return img


def build_repeated_structure_proxy(size=IMG_SIZE) -> Image.Image:
    """
    Illustration with a regularly-spaced repeated object (e.g. a row of
    identical icons/trees) -- a deliberate copy-move false-positive probe,
    per the original audit's finding that legitimately repeated real objects
    can trigger rigid-displacement copy-move clustering.
    """
    img = Image.new('RGB', (size, size), color=(200, 225, 235))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, size - 60, size, size], fill=(120, 170, 100))  # "ground"
    for x in range(20, size - 20, 45):
        draw.ellipse([x, size - 110, x + 30, size - 60], fill=(40, 110, 50))  # identical "tree" canopy
        draw.rectangle([x + 12, size - 65, x + 18, size - 45], fill=(90, 60, 30))  # identical "trunk"
    return img


def build_low_color_proxy(size=IMG_SIZE) -> Image.Image:
    """Illustration proxy quantized to a small palette (low-color PNG class)."""
    base = build_illustration_proxy(size)
    return base.convert('P', palette=Image.ADAPTIVE, colors=8).convert('RGB')


def build_alpha_proxy(size=IMG_SIZE) -> Image.Image:
    """RGBA image with spatially-varying (non-constant) alpha, not just a flat alpha value."""
    rng = _seeded_rng('alpha')
    base = build_illustration_proxy(size).convert('RGBA')
    arr = np.array(base)
    yy, xx = np.mgrid[0:size, 0:size]
    alpha = (128 + 100 * np.sin(xx / 25.0) * np.cos(yy / 30.0)).clip(0, 255).astype(np.uint8)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, mode='RGBA')


def build_grayscale_proxy(size=IMG_SIZE) -> Image.Image:
    """Single-channel synthetic proxy with smoothed-noise natural-looking texture."""
    rng = _seeded_rng('grayscale')
    noise = rng.normal(0, 1.0, (size, size))
    smooth = gaussian_filter(noise, sigma=6)
    smooth = (smooth - smooth.min()) / (smooth.max() - smooth.min())
    arr = (40 + 180 * smooth).astype(np.uint8)
    fine = rng.normal(0, 3.0, arr.shape)
    arr = np.clip(arr.astype(np.float32) + fine, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode='L')


CLASS_BUILDERS = {
    'photograph_proxy': build_photograph_proxy,
    'screenshot_proxy': build_screenshot_proxy,
    'document_proxy': build_document_proxy,
    'illustration_proxy': build_illustration_proxy,
    'low_color_proxy': build_low_color_proxy,
    'alpha_proxy': build_alpha_proxy,
    'grayscale_proxy': build_grayscale_proxy,
}


# ---------------------------------------------------------------------------
# Stego / tampering transforms
# ---------------------------------------------------------------------------

PAYLOAD_LEVELS = {'low': 0.15, 'medium': 0.50, 'high': 1.00}


def embed_lsb(img: Image.Image, rate: float, seed_label: str) -> Image.Image:
    """
    Random-bit LSB replacement over `rate` fraction of pixel/channel values.
    Identical method to the existing tests/evaluation/sample_generator.py, so
    G1 and G2 results are directly comparable.
    """
    rng = _seeded_rng(seed_label)
    mode = img.mode
    arr = np.array(img)
    if mode == 'L':
        mask = rng.rand(*arr.shape) < rate
        arr[mask] = (arr[mask] & 0xFE) | rng.randint(0, 2, arr.shape, dtype=np.uint8)[mask]
        return Image.fromarray(arr, mode='L')
    elif mode == 'RGBA':
        rgb = arr[:, :, :3].copy()
        mask = rng.rand(*rgb.shape) < rate
        rgb[mask] = (rgb[mask] & 0xFE) | rng.randint(0, 2, rgb.shape, dtype=np.uint8)[mask]
        arr[:, :, :3] = rgb  # alpha channel left untouched
        return Image.fromarray(arr, mode='RGBA')
    else:
        rgb_img = img.convert('RGB')
        rgb = np.array(rgb_img)
        mask = rng.rand(*rgb.shape) < rate
        rgb[mask] = (rgb[mask] & 0xFE) | rng.randint(0, 2, rgb.shape, dtype=np.uint8)[mask]
        return Image.fromarray(rgb, mode='RGB')


def apply_copy_move(img: Image.Image, seed_label: str, block=48) -> Image.Image:
    rng = _seeded_rng(seed_label)
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    sy, sx = h // 4, w // 4
    stamp = arr[sy:sy + block, sx:sx + block].copy()
    ty, tx = h // 2, w // 2
    if ty + block <= h and tx + block <= w:
        arr[ty:ty + block, tx:tx + block] = stamp
    return Image.fromarray(arr, mode='RGB')


def apply_splice_noise(img: Image.Image, seed_label: str, patch=80) -> Image.Image:
    rng = _seeded_rng(seed_label)
    arr = np.array(img.convert('RGB')).astype(np.float32)
    h, w = arr.shape[:2]
    y0, x0 = h // 3, w // 3
    y1, x1 = min(h, y0 + patch), min(w, x0 + patch)
    noise = rng.normal(0, 45.0, (y1 - y0, x1 - x0, 3)).astype(np.float32)
    arr[y0:y1, x0:x1] += noise
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode='RGB')


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------

def _save(img: Image.Image, out_dir: str, filename: str, fmt: str, **save_kwargs) -> str:
    path = os.path.join(out_dir, filename)
    if fmt == 'JPEG' and img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    img.save(path, format=fmt, **save_kwargs)
    return path


def _record(filepath, image_class, fmt, img, ground_truth) -> Dict[str, Any]:
    return {
        'filename': os.path.basename(filepath),
        'filepath': filepath,
        'image_class': image_class,
        'format': fmt,
        'dimensions': list(img.size),
        'color_mode': img.mode,
        'has_alpha': img.mode in ('RGBA', 'LA'),
        'ground_truth': ground_truth,
    }


def generate_g2_corpus(output_dir: str = 'tests/evaluation/g2_samples') -> List[Dict[str, Any]]:
    os.makedirs(output_dir, exist_ok=True)
    records: List[Dict[str, Any]] = []

    # 1. Clean + stego (low/medium/high) for every class
    for class_name, builder in CLASS_BUILDERS.items():
        clean_img = builder()
        fmt = 'PNG'
        fname = f"{class_name}_clean.png"
        path = _save(clean_img, output_dir, fname, fmt)
        records.append(_record(path, class_name, fmt, clean_img, {
            'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none',
            'embedding_rate': 0.0, 'has_tampering': False, 'tampering_type': 'none'
        }))

        for level, rate in PAYLOAD_LEVELS.items():
            stego_img = embed_lsb(clean_img, rate, f"{class_name}_stego_{level}")
            fname = f"{class_name}_stego_{level}.png"
            path = _save(stego_img, output_dir, fname, fmt)
            records.append(_record(path, class_name, fmt, stego_img, {
                'has_steganography': True, 'stego_type': 'spatial_lsb', 'payload_level': level,
                'embedding_rate': rate, 'has_tampering': False, 'tampering_type': 'none'
            }))

    # 2. JPEG clean + JPEG-appended-EOF stego variant (representative subset: photograph, screenshot)
    for class_name in ['photograph_proxy', 'screenshot_proxy']:
        clean_img = CLASS_BUILDERS[class_name]()
        fname = f"{class_name}_clean.jpg"
        path = _save(clean_img.convert('RGB'), output_dir, fname, 'JPEG', quality=90)
        records.append(_record(path, class_name, 'JPEG', clean_img, {
            'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none',
            'embedding_rate': 0.0, 'has_tampering': False, 'tampering_type': 'none'
        }))

        buf = BytesIO()
        clean_img.convert('RGB').save(buf, format='JPEG', quality=90)
        payload = b'--- G2_CONTROLLED_EVAL_SECRET_PAYLOAD_EOF ---' + b'B' * 512
        eof_bytes = buf.getvalue() + payload
        eof_fname = f"{class_name}_stego_appended_eof.jpg"
        eof_path = os.path.join(output_dir, eof_fname)
        with open(eof_path, 'wb') as f:
            f.write(eof_bytes)
        records.append({
            'filename': eof_fname, 'filepath': eof_path, 'image_class': class_name,
            'format': 'JPEG', 'dimensions': list(clean_img.size), 'color_mode': 'RGB',
            'has_alpha': False,
            'ground_truth': {
                'has_steganography': True, 'stego_type': 'appended_eof', 'payload_level': 'n/a',
                'embedding_rate': 0.0, 'has_tampering': False, 'tampering_type': 'none'
            }
        })

    # 3. Tampering samples (representative subset: photograph, document, repeated-structure probe)
    photo = CLASS_BUILDERS['photograph_proxy']()
    doc = CLASS_BUILDERS['document_proxy']()
    repeated = build_repeated_structure_proxy()

    cm_img = apply_copy_move(photo, 'tamper_copymove_photo')
    path = _save(cm_img, output_dir, 'photograph_proxy_tamper_copymove.png', 'PNG')
    records.append(_record(path, 'photograph_proxy', 'PNG', cm_img, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': True, 'tampering_type': 'copy_move'
    }))

    splice_img = apply_splice_noise(photo, 'tamper_splice_photo')
    path = _save(splice_img, output_dir, 'photograph_proxy_tamper_splice.png', 'PNG')
    records.append(_record(path, 'photograph_proxy', 'PNG', splice_img, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': True, 'tampering_type': 'noise_disparity'
    }))

    splice_doc_img = apply_splice_noise(doc, 'tamper_splice_doc', patch=60)
    path = _save(splice_doc_img, output_dir, 'document_proxy_tamper_splice.png', 'PNG')
    records.append(_record(path, 'document_proxy', 'PNG', splice_doc_img, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': True, 'tampering_type': 'noise_disparity'
    }))

    # Copy-move false-positive probe: NOT tampered -- ground truth is clean.
    # Ground truth "has_tampering: False" is deliberate: the repeated objects
    # are a legitimate feature of the image, not a forgery.
    path = _save(repeated, output_dir, 'repeated_structure_proxy_clean.png', 'PNG')
    records.append(_record(path, 'repeated_structure_proxy', 'PNG', repeated, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': False, 'tampering_type': 'none'
    }))

    # JPEG recompression as a tampering negative control (re-saving at a
    # different quality is NOT tampering by itself; ground truth is clean).
    buf = BytesIO()
    photo.convert('RGB').save(buf, format='JPEG', quality=90)
    recompressed = Image.open(BytesIO(buf.getvalue())).convert('RGB')
    path = _save(recompressed, output_dir, 'photograph_proxy_recompressed.jpg', 'JPEG', quality=70)
    records.append(_record(path, 'photograph_proxy', 'JPEG', recompressed, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': False, 'tampering_type': 'none'
    }))

    metadata_path = os.path.join(output_dir, 'metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump({
            'corpus_version': 'G2-v1',
            'image_size': IMG_SIZE,
            'sample_count': len(records),
            'note': (
                "All samples are programmatically generated synthetic proxies for "
                "the stated image class (see module docstring). None are real "
                "photographs, screenshots, or scans. No personally identifiable "
                "information is present in this corpus."
            ),
            'samples': records
        }, f, indent=2)

    return records


if __name__ == '__main__':
    recs = generate_g2_corpus()
    print(f"Generated {len(recs)} G2 corpus samples.")
