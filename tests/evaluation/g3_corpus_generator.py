"""
Phase G3 — Corpus expansion.

Adds REAL, public-domain sample images (bundled with scikit-image
specifically for use in image-processing testing/research -- these ship
with the library and are the standard corpus used throughout the
scikit-image test suite itself) alongside G2's synthetic proxies. This is a
genuine upgrade from "purely synthetic proxy" to a mix of real photographs,
real scanned-text-page images, a real vector-logo alpha PNG, and real
naturally-repeating textures (brick/grass/gravel) for the copy-move
false-positive probe -- exactly the "prefer real legally usable... material"
instruction in the G3 spec.

Images with identifiable real people's faces (astronaut, camera/"cameraman")
are deliberately excluded to avoid unnecessary personally-identifiable
content, even though both are standard, freely-redistributable test images.

All G2 synthetic proxy classes are still generated (imported from
g2_corpus_generator) so this is additive, not a replacement -- G2's corpus
remains reproducible on its own.
"""
import os
import json
from io import BytesIO
from typing import Dict, Any, List

import numpy as np
from PIL import Image
from skimage import data as skdata

from tests.evaluation.g2_corpus_generator import (
    generate_g2_corpus, embed_lsb, apply_copy_move, apply_splice_noise,
    _seeded_rng, _save, _record, PAYLOAD_LEVELS, IMG_SIZE,
)

TARGET_SIZE = IMG_SIZE  # 256, matches G2 for direct comparability


def _prep_real_image(arr: np.ndarray, size: int = TARGET_SIZE) -> Image.Image:
    """Center-crop to square, then resize to a consistent working size."""
    if arr.dtype == bool:
        arr = (arr.astype(np.uint8) * 255)
    if arr.ndim == 2:
        img = Image.fromarray(arr, mode='L')
    elif arr.shape[2] == 4:
        img = Image.fromarray(arr, mode='RGBA')
    else:
        img = Image.fromarray(arr, mode='RGB')
    w, h = img.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    img = img.crop((left, top, left + s, top + s))
    return img.resize((size, size), Image.LANCZOS)


REAL_SOURCES = {
    'photograph_real_coffee': lambda: skdata.coffee(),
    'photograph_real_chelsea': lambda: skdata.chelsea(),
    'photograph_real_rocket': lambda: skdata.rocket(),
    'document_real_page': lambda: skdata.page(),
    'document_real_text': lambda: skdata.text(),
    'grayscale_real_moon': lambda: skdata.moon(),
    'illustration_real_colorwheel': lambda: skdata.colorwheel(),
    'illustration_real_checkerboard': lambda: skdata.checkerboard(),
    'alpha_real_logo': lambda: skdata.logo(),
    'repeated_texture_real_brick': lambda: skdata.brick(),
    'repeated_texture_real_grass': lambda: skdata.grass(),
    'repeated_texture_real_gravel': lambda: skdata.gravel(),
}

# Maps each concrete source id to the broader image_class used for
# class-level aggregation in the report (so multiple real bases per class
# are averaged together, same convention as G2).
SOURCE_TO_CLASS = {
    'photograph_real_coffee': 'photograph_real',
    'photograph_real_chelsea': 'photograph_real',
    'photograph_real_rocket': 'photograph_real',
    'document_real_page': 'document_real',
    'document_real_text': 'document_real',
    'grayscale_real_moon': 'grayscale_real',
    'illustration_real_colorwheel': 'illustration_real',
    'illustration_real_checkerboard': 'illustration_real',
    'alpha_real_logo': 'alpha_real',
    'repeated_texture_real_brick': 'repeated_texture_real',
    'repeated_texture_real_grass': 'repeated_texture_real',
    'repeated_texture_real_gravel': 'repeated_texture_real',
}

PROVENANCE_NOTE = (
    "Real, public-domain sample image bundled with scikit-image "
    "(https://scikit-image.org/docs/stable/api/skimage.data.html), used "
    "here for image-processing evaluation exactly as it is used throughout "
    "scikit-image's own test suite. Not a real photograph/scan submitted by "
    "any person; contains no personally-identifiable content (images with "
    "identifiable real faces were deliberately excluded from this corpus)."
)


def apply_copy_move_multi(img: Image.Image, seed_label: str, block=40, n_regions=3) -> Image.Image:
    """Apply several independent copy-move clones at different locations/offsets."""
    rng = _seeded_rng(seed_label)
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    placed = 0
    attempts = 0
    used_targets = []
    while placed < n_regions and attempts < 50:
        attempts += 1
        sy, sx = rng.randint(0, h - block), rng.randint(0, w - block)
        ty, tx = rng.randint(0, h - block), rng.randint(0, w - block)
        if abs(ty - sy) < block and abs(tx - sx) < block:
            continue
        if any(abs(ty - uy) < block and abs(tx - ux) < block for uy, ux in used_targets):
            continue
        stamp = arr[sy:sy + block, sx:sx + block].copy()
        arr[ty:ty + block, tx:tx + block] = stamp
        used_targets.append((ty, tx))
        placed += 1
    return Image.fromarray(arr, mode='RGB'), placed


def apply_weak_copy_move(img: Image.Image, seed_label: str, block=10) -> Image.Image:
    """A deliberately tiny, below-typical-block-size clone -- an edge case, not expected to reliably trigger."""
    rng = _seeded_rng(seed_label)
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    sy, sx = h // 5, w // 5
    stamp = arr[sy:sy + block, sx:sx + block].copy()
    ty, tx = 3 * h // 5, 3 * w // 5
    arr[ty:ty + block, tx:tx + block] = stamp
    return Image.fromarray(arr, mode='RGB')


def generate_g3_corpus(output_dir: str = 'tests/evaluation/g3_samples',
                        g2_output_dir: str = 'tests/evaluation/g2_samples') -> List[Dict[str, Any]]:
    os.makedirs(output_dir, exist_ok=True)

    # G2's full synthetic-proxy corpus is regenerated as-is and included
    # (not duplicated on disk -- kept in its own g2_samples directory) so
    # the expanded corpus is additive.
    g2_records = generate_g2_corpus(g2_output_dir)
    for r in g2_records:
        r['corpus_source'] = 'G2_synthetic_proxy'

    g3_records: List[Dict[str, Any]] = []

    # 1. Real-image clean + stego (low/medium/high)
    for source_id, loader in REAL_SOURCES.items():
        base_img = _prep_real_image(loader())
        image_class = SOURCE_TO_CLASS[source_id]
        fmt = 'PNG'

        fname = f"{source_id}_clean.png"
        path = _save(base_img, output_dir, fname, fmt)
        rec = _record(path, image_class, fmt, base_img, {
            'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none',
            'embedding_rate': 0.0, 'has_tampering': False, 'tampering_type': 'none'
        })
        rec['corpus_source'] = 'real_public_domain'
        rec['source_id'] = source_id
        rec['provenance'] = PROVENANCE_NOTE
        g3_records.append(rec)

        for level, rate in PAYLOAD_LEVELS.items():
            stego_img = embed_lsb(base_img, rate, f"{source_id}_stego_{level}")
            fname = f"{source_id}_stego_{level}.png"
            path = _save(stego_img, output_dir, fname, fmt)
            rec = _record(path, image_class, fmt, stego_img, {
                'has_steganography': True, 'stego_type': 'spatial_lsb', 'payload_level': level,
                'embedding_rate': rate, 'has_tampering': False, 'tampering_type': 'none'
            })
            rec['corpus_source'] = 'real_public_domain'
            rec['source_id'] = source_id
            rec['provenance'] = PROVENANCE_NOTE
            g3_records.append(rec)

    # 2. Copy-move TRUE POSITIVES on real photographs (needed to measure
    #    sensitivity loss/gain of any copy-move fix candidate, per Step 3).
    coffee = _prep_real_image(skdata.coffee())
    rocket = _prep_real_image(skdata.rocket())
    chelsea = _prep_real_image(skdata.chelsea())

    cm_single = apply_copy_move(coffee, 'g3_cm_single_coffee', block=48)
    path = _save(cm_single, output_dir, 'photograph_real_coffee_tamper_copymove_single.png', 'PNG')
    rec = _record(path, 'photograph_real', 'PNG', cm_single, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': True, 'tampering_type': 'copy_move_single_region'
    })
    rec.update({'corpus_source': 'real_public_domain_tampered', 'source_id': 'photograph_real_coffee'})
    g3_records.append(rec)

    cm_multi_img, n_placed = apply_copy_move_multi(rocket, 'g3_cm_multi_rocket', block=40, n_regions=3)
    path = _save(cm_multi_img, output_dir, 'photograph_real_rocket_tamper_copymove_multi.png', 'PNG')
    rec = _record(path, 'photograph_real', 'PNG', cm_multi_img, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': True, 'tampering_type': f'copy_move_multi_region_n{n_placed}'
    })
    rec.update({'corpus_source': 'real_public_domain_tampered', 'source_id': 'photograph_real_rocket'})
    g3_records.append(rec)

    weak_img = apply_weak_copy_move(chelsea, 'g3_cm_weak_chelsea', block=10)
    path = _save(weak_img, output_dir, 'photograph_real_chelsea_tamper_copymove_weak.png', 'PNG')
    rec = _record(path, 'photograph_real', 'PNG', weak_img, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': True, 'tampering_type': 'copy_move_weak_10px'
    })
    rec.update({
        'corpus_source': 'real_public_domain_tampered', 'source_id': 'photograph_real_chelsea',
        'note': 'Deliberately tiny (10px) clone -- an edge case not necessarily expected to be reliably detected; used to characterize detector behavior at the sensitivity floor, not as a strict pass/fail.'
    })
    g3_records.append(rec)

    # 3. Splice-noise tampering on real document + illustration content
    page_img = _prep_real_image(skdata.page())
    splice_doc = apply_splice_noise(page_img.convert('RGB'), 'g3_splice_page', patch=50)
    path = _save(splice_doc, output_dir, 'document_real_page_tamper_splice.png', 'PNG')
    rec = _record(path, 'document_real', 'PNG', splice_doc, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': True, 'tampering_type': 'noise_disparity'
    })
    rec.update({'corpus_source': 'real_public_domain_tampered', 'source_id': 'document_real_page'})
    g3_records.append(rec)

    # 4. JPEG recompression negative control on a real photo
    buf = BytesIO()
    coffee.convert('RGB').save(buf, format='JPEG', quality=90)
    recompressed = Image.open(BytesIO(buf.getvalue())).convert('RGB')
    path = _save(recompressed, output_dir, 'photograph_real_coffee_recompressed.jpg', 'JPEG', quality=70)
    rec = _record(path, 'photograph_real', 'JPEG', recompressed, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': False, 'tampering_type': 'none'
    })
    rec.update({'corpus_source': 'real_public_domain', 'source_id': 'photograph_real_coffee'})
    g3_records.append(rec)

    # 5. Tiny and large image edge cases (Step 4 items 9, 10)
    tiny = coffee.resize((32, 32), Image.LANCZOS)
    path = _save(tiny, output_dir, 'photograph_real_coffee_tiny_32.png', 'PNG')
    rec = _record(path, 'photograph_real', 'PNG', tiny, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': False, 'tampering_type': 'none'
    })
    rec.update({'corpus_source': 'real_public_domain', 'source_id': 'photograph_real_coffee', 'note': 'Edge case: tiny image (32x32).'})
    g3_records.append(rec)

    large = coffee.resize((1024, 1024), Image.LANCZOS)
    path = _save(large, output_dir, 'photograph_real_coffee_large_1024.png', 'PNG')
    rec = _record(path, 'photograph_real', 'PNG', large, {
        'has_steganography': False, 'stego_type': 'none', 'payload_level': 'none', 'embedding_rate': 0.0,
        'has_tampering': False, 'tampering_type': 'none'
    })
    rec.update({'corpus_source': 'real_public_domain', 'source_id': 'photograph_real_coffee', 'note': 'Edge case: large image (1024x1024).'})
    g3_records.append(rec)

    all_records = g2_records + g3_records

    metadata_path = os.path.join(output_dir, 'g3_metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump({
            'corpus_version': 'G3-v1',
            'sample_count_total': len(all_records),
            'sample_count_g2_synthetic': len(g2_records),
            'sample_count_g3_new': len(g3_records),
            'real_image_sources': list(REAL_SOURCES.keys()),
            'note': (
                "G3 extends G2's synthetic-proxy corpus (regenerated unchanged, "
                "see g2_samples/metadata.json) with real, public-domain images "
                "bundled with scikit-image, plus additional tampering edge "
                "cases (multi-region copy-move, weak/tiny copy-move, tiny and "
                "large images). This remains a small evaluation corpus, not a "
                "representative real-world sample -- see the G3 report's "
                "Limitations section for an explicit adequacy statement."
            ),
            'g3_samples': g3_records,
        }, f, indent=2, default=str)

    return all_records


if __name__ == '__main__':
    recs = generate_g3_corpus()
    print(f"Generated {len(recs)} total G3 corpus samples (G2 + G3 additions).")
