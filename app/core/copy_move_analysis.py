from typing import Dict, Any, Union, List, Tuple
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image


class CopyMoveAnalyzer:
    """
    Analyzes images for localized duplicate regions consistent with copy-move / clone-stamp manipulation.

    Forensic Methodology:
    1. Converts image to 2D grayscale float32 luminance.
    2. Bounds compute on large images by adaptive proportional downsampling (max dimension <= 600px).
    3. Partitions image into overlapping spatial blocks (16x16 with stride 8).
    4. Filters out flat / low-texture blocks (std < 10.0) and 1D straight lines/borders
       (anisotropy filter) to prevent false positives on uniform backgrounds and borders.
    5. Computes a compact 8D descriptor for each textured block:
       - Mean luminance
       - 4 quadrant sub-means
       - Horizontal and vertical mean gradient magnitudes
       - Dynamic range (contrast)
    6. Constructs a spatial KD-tree (scipy.spatial.cKDTree) for fast nearest-neighbor matching.
    7. Enforces a physical separation constraint (center distance >= 32px) to ignore adjacent blocks.
    8. Performs rigid displacement vector clustering:
       - True copy-move manipulations duplicate contiguous regions, producing a cluster of block pairs
         sharing the exact same rigid translation vector.
       - Coincidental texture similarity produces isolated, uncoordinated matches that are discarded.
    9. Reports clustered duplicate regions and calculates a bounded copy-move suspicion indicator.

    Forensic Caveat:
    Copy-move indicators are heuristic, NOT proof of manipulation.
    Natural scenes with repetitive architecture (windows, tiles), symmetric reflections,
    or repeating patterns may exhibit duplicate characteristics.
    """

    BLOCK_SIZE = 16
    STRIDE = 8
    MIN_STD = 10.0
    MIN_SPATIAL_DIST = 32.0
    MAX_MATCHES_REPORTED = 10

    # --- G3 fix (see G3 technical report, Step 3) ---
    # A genuinely localized copy-move forgery produces a small, bounded
    # number of displacement clusters and clustered blocks (a deliberate,
    # finite set of copy-paste operations). Naturally repetitive/periodic
    # content (tiled patterns, repeated grid lines, large flat regions) can
    # instead produce a very large number of coherent-but-coincidental
    # clusters spanning much of the image -- evidence of global structural
    # repetition, not a planted duplicate. This distinction is used in the
    # copy-move literature (e.g. filtering to the single most-frequent
    # displacement vector; discarding matches inconsistent with a bounded,
    # localized transformation) even though implementations vary.
    #
    # These two caps were set from the empirically observed gap in the G3
    # evaluation corpus (tests/evaluation/g3_results/), not chosen a priori:
    #   - Every genuine/ambiguous case observed: cluster_count <= 3,
    #     clustered_blocks <= 15.
    #   - Every extreme, clearly-periodic false positive observed
    #     (a repeated document grid, a checkerboard pattern):
    #     cluster_count >= 15, clustered_blocks >= 194.
    # The caps below sit within that large observed gap, with substantial
    # margin on both sides, rather than at a boundary tuned to any single
    # sample. They address the extreme, unambiguous portion of the measured
    # false-positive burden only -- see the G3 report for the smaller-
    # magnitude cases (e.g. a single large flat region producing one
    # coincidental cluster of ~8-15 blocks) that remain unresolved because
    # they sit too close, in this corpus, to the only confirmed genuine
    # small-scale copy-move-positive sample to separate safely without
    # risking that true positive.
    MAX_CLUSTERS_BEFORE_PERIODICITY = 8
    MAX_CLUSTERED_BLOCKS_BEFORE_PERIODICITY = 50

    @classmethod
    def analyze(cls, image_input: Union[Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Executes block-based copy-move detection and reports clustered duplicates.
        Accepts PIL Image or NumPy array.
        """
        # 1. Normalize input to 2D grayscale float32 array
        if isinstance(image_input, Image.Image):
            gray_pil = image_input.convert('L')
            gray_arr = np.array(gray_pil, dtype=np.float32)
        elif isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 2:
                gray_arr = image_input.astype(np.float32)
            elif len(image_input.shape) == 3 and image_input.shape[2] >= 3:
                gray_arr = (0.299 * image_input[:, :, 0] +
                            0.587 * image_input[:, :, 1] +
                            0.114 * image_input[:, :, 2]).astype(np.float32)
            else:
                gray_arr = image_input[:, :, 0].astype(np.float32)
        else:
            return {
                'available': False,
                'reason': 'invalid_input_type',
                'total_blocks': 0,
                'candidate_matches': 0,
                'cluster_count': 0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'matches': [],
                'details': 'Invalid image input format for copy-move analysis.'
            }

        h, w = gray_arr.shape
        if h < 32 or w < 32:
            return {
                'available': False,
                'reason': 'insufficient_dimensions',
                'total_blocks': 0,
                'candidate_matches': 0,
                'cluster_count': 0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'matches': [],
                'details': 'Image dimensions too small for copy-move block matching.'
            }

        # Check for constant/uniform image
        if float(np.std(gray_arr)) < 1e-4:
            return {
                'available': True,
                'total_blocks': 0,
                'candidate_matches': 0,
                'cluster_count': 0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'matches': [],
                'details': 'Completely uniform image; no textured blocks available for copy-move matching.'
            }

        # Adaptive downsampling for large images to bound compute
        scale_factor = 1
        if max(h, w) > 600:
            scale_factor = max(1, int(max(h, w) / 500))
            gray_arr = gray_arr[::scale_factor, ::scale_factor]
            h, w = gray_arr.shape

        bs = cls.BLOCK_SIZE
        stride = cls.STRIDE

        blocks: List[np.ndarray] = []
        coords: List[Tuple[int, int]] = []
        features: List[List[float]] = []

        h_steps = (h - bs) // stride + 1
        w_steps = (w - bs) // stride + 1
        total_possible_blocks = h_steps * w_steps

        # 2. Block feature extraction with texture and 1D line suppression
        for y_idx in range(h_steps):
            y = y_idx * stride
            for x_idx in range(w_steps):
                x = x_idx * stride
                b = gray_arr[y:y + bs, x:x + bs]
                b_std = float(np.std(b))
                if b_std < cls.MIN_STD:
                    continue

                ix = np.diff(b, axis=1)
                iy = np.diff(b, axis=0)
                sx = float(np.sum(ix ** 2))
                sy = float(np.sum(iy ** 2))

                # Require 2D energy in both axes to suppress straight 1D borders/lines
                if min(sx, sy) < 250.0:
                    continue
                if max(sx, sy) / (min(sx, sy) + 50.0) > 6.0:
                    continue

                # 8D compact descriptor
                m = float(np.mean(b)) / 255.0
                q1 = float(np.mean(b[:bs // 2, :bs // 2])) / 255.0
                q2 = float(np.mean(b[:bs // 2, bs // 2:])) / 255.0
                q3 = float(np.mean(b[bs // 2:, :bs // 2])) / 255.0
                q4 = float(np.mean(b[bs // 2:, bs // 2:])) / 255.0
                gx = float(np.mean(np.abs(ix))) / 255.0
                gy = float(np.mean(np.abs(iy))) / 255.0
                contrast = (float(np.max(b)) - float(np.min(b))) / 255.0

                features.append([m, q1, q2, q3, q4, gx, gy, contrast])
                coords.append((x, y))
                blocks.append(b)

        total_textured_blocks = len(features)
        if total_textured_blocks < 10:
            return {
                'available': True,
                'total_blocks': total_possible_blocks,
                'candidate_matches': 0,
                'cluster_count': 0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'matches': [],
                'details': f"Insufficient textured blocks ({total_textured_blocks}) for copy-move clustering."
            }

        # 3. KD-tree nearest-neighbor querying
        feat_arr = np.array(features, dtype=np.float32)
        tree = cKDTree(feat_arr)
        k_neighbors = min(6, total_textured_blocks)
        dists, indices = tree.query(feat_arr, k=k_neighbors)

        displacements: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
        candidate_match_count = 0

        for i in range(total_textured_blocks):
            x1, y1 = coords[i]
            for k in range(1, dists.shape[1]):
                d = dists[i, k]
                j = indices[i, k]
                if d > 0.03:
                    break

                x2, y2 = coords[j]
                if np.hypot(x1 - x2, y1 - y2) >= cls.MIN_SPATIAL_DIST and i < j:
                    mae = float(np.mean(np.abs(blocks[i] - blocks[j])))
                    if mae < 3.0:
                        candidate_match_count += 1
                        dx = round((x2 - x1) / stride) * stride
                        dy = round((y2 - y1) / stride) * stride
                        bin_vec = (dx, dy)
                        match_entry = {
                            'source': {
                                'x': int(x1 * scale_factor),
                                'y': int(y1 * scale_factor),
                                'width': int(bs * scale_factor),
                                'height': int(bs * scale_factor)
                            },
                            'target': {
                                'x': int(x2 * scale_factor),
                                'y': int(y2 * scale_factor),
                                'width': int(bs * scale_factor),
                                'height': int(bs * scale_factor)
                            },
                            'distance': round(float(d), 4),
                            'similarity': round(float(max(0.0, 1.0 - (mae / 25.5))), 3)
                        }
                        displacements.setdefault(bin_vec, []).append(match_entry)

        # 4. Filter for significant clusters (>= 3 matches sharing translation vector)
        significant_clusters = {k: v for k, v in displacements.items() if len(v) >= 3}
        cluster_count = len(significant_clusters)
        total_clustered_blocks = sum(len(v) for v in significant_clusters.values())

        # Collect top reported matches from the most significant clusters
        reported_matches: List[Dict[str, Any]] = []
        sorted_clusters = sorted(significant_clusters.values(), key=lambda cl: len(cl), reverse=True)
        for cl in sorted_clusters:
            for match in cl:
                if len(reported_matches) < cls.MAX_MATCHES_REPORTED:
                    reported_matches.append(match)

        # Compute bounded anomaly indicator [0.0, 1.0]
        # Isolated matches are normal, but clustered duplicates indicate a duplicated region
        raw_indicator = total_clustered_blocks / 6.0
        uncapped_indicator = float(max(0.0, min(1.0, raw_indicator)))

        # G3 fix: an extremely large number of clusters or clustered blocks
        # is evidence of global periodic/repetitive structure (e.g. a tiled
        # texture or a repeated document grid), not a bounded, localized
        # forgery -- see the class docstring and the constants above for the
        # evidence this threshold is drawn from. The indicator itself (not
        # just the boolean suspicion flag) must be suppressed here, since
        # TamperingAnalyzer's aggregation reads `anomaly_indicator` directly
        # (both in its weighted sum and its max-pooling boost) rather than
        # this detector's own `is_suspicious` decision.
        is_periodic_like = bool(
            cluster_count > cls.MAX_CLUSTERS_BEFORE_PERIODICITY
            or total_clustered_blocks > cls.MAX_CLUSTERED_BLOCKS_BEFORE_PERIODICITY
        )
        anomaly_indicator = 0.0 if is_periodic_like else uncapped_indicator
        is_suspicious = bool((not is_periodic_like) and (anomaly_indicator > 0.40 or cluster_count >= 2))

        details_msg = (
            f"Copy-move evaluation: {total_textured_blocks} textured blocks inspected, "
            f"{candidate_match_count} candidate duplicate pairs, "
            f"{cluster_count} coherent displacement clusters ({total_clustered_blocks} clustered blocks)."
            + (" Pattern consistent with periodic/repetitive structure rather than a localized duplicate; suspicion suppressed." if is_periodic_like else "")
        )

        return {
            'available': True,
            'total_blocks': total_possible_blocks,
            'candidate_matches': candidate_match_count,
            'cluster_count': cluster_count,
            'anomaly_indicator': round(anomaly_indicator, 4),
            'is_periodic_like': is_periodic_like,
            'is_suspicious': is_suspicious,
            'matches': reported_matches,
            'details': details_msg
        }
