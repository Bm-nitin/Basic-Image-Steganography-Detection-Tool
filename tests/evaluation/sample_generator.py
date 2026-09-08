import os
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw

def create_base_carrier(width=256, height=256):
    """
    Creates a clean photographic carrier image with smooth gradients and geometric objects.
    Preserves natural pixel-to-pixel correlation and low entropy in LSB planes.
    """
    img = Image.new('RGB', (width, height), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        r = int(30 + 180 * (y / height))
        for x in range(width):
            g = int(20 + 120 * (x / width))
            b = int(40 + 140 * ((x + y) / (width + height)))
            img.putpixel((x, y), (r, g, b))
    draw.ellipse([50, 50, width - 50, height - 50], fill=(220, 160, 80), outline=(255, 255, 255))
    draw.rectangle([90, 90, width - 90, height - 90], fill=(70, 130, 180))
    return img

def generate_evaluation_dataset(output_dir='tests/evaluation/samples'):
    """
    Generates 8 controlled benchmark test samples with verified ground truth.
    """
    os.makedirs(output_dir, exist_ok=True)
    samples = []

    base_img = create_base_carrier(256, 256)
    base_arr = np.array(base_img)

    # 1. Clean Carrier PNG
    clean_png_path = os.path.join(output_dir, 'clean_carrier.png')
    base_img.save(clean_png_path, format='PNG')
    samples.append({
        'id': 'clean_png',
        'name': 'Clean Carrier Baseline (PNG)',
        'filepath': clean_png_path,
        'format': 'PNG',
        'ground_truth': {
            'has_steganography': False,
            'stego_type': 'none',
            'embedding_rate': 0.0,
            'has_tampering': False,
            'tampering_type': 'none'
        }
    })

    # 2. Clean Carrier JPEG
    clean_jpg_path = os.path.join(output_dir, 'clean_carrier.jpg')
    base_img.save(clean_jpg_path, format='JPEG', quality=90)
    samples.append({
        'id': 'clean_jpeg',
        'name': 'Clean Carrier Baseline (JPEG)',
        'filepath': clean_jpg_path,
        'format': 'JPEG',
        'ground_truth': {
            'has_steganography': False,
            'stego_type': 'none',
            'embedding_rate': 0.0,
            'has_tampering': False,
            'tampering_type': 'none'
        }
    })

    # 3. Stego LSB Low (~15% embedding)
    rng = np.random.RandomState(42)
    arr_low = base_arr.copy()
    mask = rng.rand(*arr_low.shape) < 0.15
    arr_low[mask] = (arr_low[mask] & 0xFE) | rng.randint(0, 2, arr_low.shape, dtype=np.uint8)[mask]
    stego_low_path = os.path.join(output_dir, 'stego_lsb_low.png')
    Image.fromarray(arr_low).save(stego_low_path, format='PNG')
    samples.append({
        'id': 'stego_lsb_low',
        'name': 'Low Capacity LSB Steganography (~15%)',
        'filepath': stego_low_path,
        'format': 'PNG',
        'ground_truth': {
            'has_steganography': True,
            'stego_type': 'spatial_lsb',
            'embedding_rate': 0.15,
            'has_tampering': False,
            'tampering_type': 'none'
        }
    })

    # 4. Stego LSB Medium (~50% embedding)
    arr_med = base_arr.copy()
    mask = rng.rand(*arr_med.shape) < 0.50
    arr_med[mask] = (arr_med[mask] & 0xFE) | rng.randint(0, 2, arr_med.shape, dtype=np.uint8)[mask]
    stego_med_path = os.path.join(output_dir, 'stego_lsb_medium.png')
    Image.fromarray(arr_med).save(stego_med_path, format='PNG')
    samples.append({
        'id': 'stego_lsb_med',
        'name': 'Medium Capacity LSB Steganography (~50%)',
        'filepath': stego_med_path,
        'format': 'PNG',
        'ground_truth': {
            'has_steganography': True,
            'stego_type': 'spatial_lsb',
            'embedding_rate': 0.50,
            'has_tampering': False,
            'tampering_type': 'none'
        }
    })

    # 5. Stego LSB High (100% embedding)
    arr_high = (base_arr.copy() & 0xFE) | rng.randint(0, 2, base_arr.shape, dtype=np.uint8)
    stego_high_path = os.path.join(output_dir, 'stego_lsb_high.png')
    Image.fromarray(arr_high).save(stego_high_path, format='PNG')
    samples.append({
        'id': 'stego_lsb_high',
        'name': 'High Capacity LSB Steganography (100%)',
        'filepath': stego_high_path,
        'format': 'PNG',
        'ground_truth': {
            'has_steganography': True,
            'stego_type': 'spatial_lsb',
            'embedding_rate': 1.0,
            'has_tampering': False,
            'tampering_type': 'none'
        }
    })

    # 6. Stego Appended EOF (780 bytes)
    buf = BytesIO()
    base_img.save(buf, format='JPEG', quality=90)
    raw_jpg = buf.getvalue()
    payload = b'--- CONTROLLED_EVAL_SECRET_PAYLOAD_EOF ---' + b'A' * 740
    stego_eof_bytes = raw_jpg + payload
    stego_eof_path = os.path.join(output_dir, 'stego_eof.jpg')
    with open(stego_eof_path, 'wb') as f:
        f.write(stego_eof_bytes)
    samples.append({
        'id': 'stego_eof',
        'name': 'Appended EOF Trailing Data (JPEG + 780B)',
        'filepath': stego_eof_path,
        'format': 'JPEG',
        'ground_truth': {
            'has_steganography': True,
            'stego_type': 'appended_eof',
            'embedding_rate': 0.0,
            'has_tampering': False,
            'tampering_type': 'none'
        }
    })

    # 7. Tampering: Copy-Move Cloned Region (Identical 48x48 translated textured blocks)
    np.random.seed(123)
    arr_cm = base_arr.copy()
    stamp = np.random.randint(40, 220, (48, 48, 3), dtype=np.uint8)
    arr_cm[24:72, 24:72] = stamp
    arr_cm[24:72, 128:176] = stamp
    tamper_cm_path = os.path.join(output_dir, 'tamper_copymove.png')
    Image.fromarray(arr_cm).save(tamper_cm_path, format='PNG')
    samples.append({
        'id': 'tamper_copymove',
        'name': 'Copy-Move Cloned Manipulation',
        'filepath': tamper_cm_path,
        'format': 'PNG',
        'ground_truth': {
            'has_steganography': False,
            'stego_type': 'none',
            'embedding_rate': 0.0,
            'has_tampering': True,
            'tampering_type': 'copy_move'
        }
    })

    # 8. Tampering: Spliced Noise Inconsistency (80x80 localized gaussian noise patch)
    arr_splice = base_arr.copy().astype(np.float32)
    np.random.seed(42)
    noisy_patch = np.random.normal(0, 45.0, (80, 80, 3)).astype(np.float32)
    arr_splice[64:144, 64:144] += noisy_patch
    arr_splice = np.clip(arr_splice, 0, 255).astype(np.uint8)
    tamper_noise_path = os.path.join(output_dir, 'tamper_spliced_noise.png')
    Image.fromarray(arr_splice).save(tamper_noise_path, format='PNG')
    samples.append({
        'id': 'tamper_spliced_noise',
        'name': 'Spliced Local Noise Inconsistency',
        'filepath': tamper_noise_path,
        'format': 'PNG',
        'ground_truth': {
            'has_steganography': False,
            'stego_type': 'none',
            'embedding_rate': 0.0,
            'has_tampering': True,
            'tampering_type': 'noise_disparity'
        }
    })

    return samples

if __name__ == '__main__':
    samples = generate_evaluation_dataset()
    print(f'Generated {len(samples)} controlled evaluation samples successfully.')
