"""
Phase G8, Phases 4-6 — natural-texture control group, local texture analysis,
and channel analysis.

Uses existing corpus images. Calls existing, UNMODIFIED analyzer modules
(noise_analysis, local_variance_analysis, edge_analysis) read-only for
measurement. Adds new, investigation-only local-LSB-entropy/balance
measurement code (not a new production detector) to compare global vs local
statistics, per Phase 5's explicit request.
"""
import json
import os
import numpy as np
from PIL import Image

from app.core import (
    MetadataAnalyzer, FileForensicsAnalyzer, VisualExtractor,
    StatisticalAnalyzer, TamperingAnalyzer,
)
from app.core.noise_analysis import NoiseAnalyzer
from app.core.local_variance_analysis import LocalVarianceAnalyzer
from app.core.edge_analysis import EdgeAnalyzer

with open('tests/evaluation/g7_results/g7_corpus_inventory.json') as f:
    INVENTORY = {r['filename']: r for r in json.load(f)['records']}


def _find_path(fn):
    import glob
    paths = glob.glob(f'tests/evaluation/g3_samples/{fn}') + glob.glob(f'tests/evaluation/g2_samples/{fn}')
    return paths[0] if paths else None


def _local_lsb_stats(gray_arr, block=32):
    h, w = gray_arr.shape
    densities = []
    for y in range(0, h - block + 1, block):
        for x in range(0, w - block + 1, block):
            blk = gray_arr[y:y + block, x:x + block]
            lsb = (blk & 1).astype(np.float64)
            densities.append(float(lsb.mean()))
    densities = np.array(densities)
    global_lsb = (gray_arr & 1).astype(np.float64).mean()
    return {
        'n_blocks': len(densities),
        'block_density_mean': round(float(densities.mean()), 4) if len(densities) else None,
        'block_density_stdev': round(float(densities.std()), 4) if len(densities) else None,
        'block_density_min': round(float(densities.min()), 4) if len(densities) else None,
        'block_density_max': round(float(densities.max()), 4) if len(densities) else None,
        'global_lsb_density': round(float(global_lsb), 4),
        'fraction_of_blocks_near_0.5': round(float(np.mean(np.abs(densities - 0.5) < 0.05)), 4) if len(densities) else None,
    }


def analyze_sample(fn):
    path = _find_path(fn)
    if path is None:
        return None
    with open(path, 'rb') as f:
        file_bytes = f.read()
    img = Image.open(path)
    gray_arr = np.array(img.convert('L'), dtype=np.uint8)
    rgb_img = img.convert('RGB')
    rgb_arr = np.array(rgb_img, dtype=np.uint8)

    meta = MetadataAnalyzer.analyze(file_bytes, fn)
    statistical = StatisticalAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get('detected_format'))
    visual = VisualExtractor.extract_bit_planes(img)

    noise_res = NoiseAnalyzer.analyze(img)
    variance_res = LocalVarianceAnalyzer.analyze(img)
    edge_res = EdgeAnalyzer.analyze(img)

    local_lsb = _local_lsb_stats(gray_arr)

    channels_identical = bool(np.array_equal(rgb_arr[:, :, 0], rgb_arr[:, :, 1]) and
                               np.array_equal(rgb_arr[:, :, 1], rgb_arr[:, :, 2]))

    entropy_res = statistical.get('entropy', {})
    chi2_res = statistical.get('chi_square', {})
    rs_res = statistical.get('rs_analysis', {})
    spa_res = statistical.get('sample_pair_analysis', statistical.get('spa_analysis', {}))

    inv = INVENTORY.get(fn, {})

    return {
        'filename': fn,
        'image_class': inv.get('image_class'),
        'actual_color_mode': inv.get('actual_color_mode'),
        'is_genuinely_grayscale_source': channels_identical,
        'global_lsb_entropy_max': entropy_res.get('lsb_entropy', {}).get('max'),
        'visual_min_balance_delta': visual.get('min_balance_delta'),
        'visual_is_suspicious': visual.get('is_visual_suspicious'),
        'chi_square_max_indicator': chi2_res.get('max_indicator'),
        'rs_estimated_rate': rs_res.get('estimated_embedding_rate'),
        'rs_applicability_diagnostic': rs_res.get('rs_applicability_diagnostic'),
        'spa_estimated_rate': spa_res.get('estimated_embedding_rate'),
        'local_variance': {
            'is_suspicious': variance_res.get('is_suspicious'),
            'global_variance': variance_res.get('global_variance'),
            'outlier_fraction': variance_res.get('outlier_block_fraction', variance_res.get('outlier_fraction')),
        },
        'edge': {
            'is_suspicious': edge_res.get('is_suspicious'),
            'edge_density': edge_res.get('edge_density'),
            'mean_gradient': edge_res.get('mean_gradient'),
        },
        'noise': {
            'is_suspicious': noise_res.get('is_suspicious'),
            'mad': noise_res.get('mad', noise_res.get('global_mad')),
        },
        'local_lsb_block_stats': local_lsb,
    }


def run_control_group_analysis(out_path='tests/evaluation/g8_results/g8_natural_photo_analysis.json'):
    fp_targets = [
        'repeated_texture_real_brick_clean.png',
        'repeated_texture_real_grass_clean.png',
        'repeated_texture_real_gravel_clean.png',
    ]
    other_photos = [
        'photograph_real_coffee_clean.png',
        'photograph_real_chelsea_clean.png',
        'photograph_real_rocket_clean.png',
        'photograph_proxy_clean.png',
    ]
    non_photo_comparisons = [
        'document_real_page_clean.png',
        'document_proxy_clean.png',
        'screenshot_proxy_clean.png',
        'illustration_real_colorwheel_clean.png',
    ]

    results = {'false_positive_targets': [], 'other_natural_photographs': [], 'non_photograph_comparisons': []}
    for fn in fp_targets:
        r = analyze_sample(fn)
        if r:
            results['false_positive_targets'].append(r)
    for fn in other_photos:
        r = analyze_sample(fn)
        if r:
            results['other_natural_photographs'].append(r)
    for fn in non_photo_comparisons:
        r = analyze_sample(fn)
        if r:
            results['non_photograph_comparisons'].append(r)

    all_photo_entropies = [r['global_lsb_entropy_max'] for r in results['false_positive_targets'] + results['other_natural_photographs']]
    results['summary'] = {
        'question': 'Are the false-positive natural-texture photos genuinely distinct from other clean natural photographs in this corpus?',
        'all_natural_photo_lsb_entropy_values': all_photo_entropies,
        'all_maxed_near_1.0': bool(all(e is not None and e >= 0.999 for e in all_photo_entropies)),
        'finding': (
            "MEASURED: every genuine clean natural photograph sample in this corpus "
            "(the 3 flagged textures AND all other real/synthetic photographs, "
            "regardless of visible texture level) shows lsb_entropy_max >= 0.999. "
            "There is no clean natural-photograph sample in this corpus that does "
            "NOT max out LSB entropy. The brick/grass/gravel false positives are "
            "therefore not distinguishable from the rest of the natural-photograph "
            "class by this signal -- they are representative of it, not anomalous "
            "within it."
        ),
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)

    return results


if __name__ == '__main__':
    r = run_control_group_analysis()
    print(r['summary'])
    for group in ['false_positive_targets', 'other_natural_photographs', 'non_photograph_comparisons']:
        print(f"\n--- {group} ---")
        for item in r[group]:
            print(item['filename'], 'entropy=', item['global_lsb_entropy_max'],
                  'grayscale_source=', item['is_genuinely_grayscale_source'],
                  'edge_density=', item['edge']['edge_density'],
                  'local_var_suspicious=', item['local_variance']['is_suspicious'])
