import os
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw

def generate_samples(output_dir: str = 'tests/test_samples'):
    """
    Generates controlled test images:
    1. clean_sample.png: Clean image with natural gradients and geometric features.
    2. stego_lsb_sample.png: Clean image with pseudo-random encrypted payload embedded in LSB.
    3. stego_eof_sample.jpg: Valid JPEG with appended payload beyond the \xFF\xD9 marker.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Generate Clean Sample
    w, h = 300, 300
    img = Image.new('RGB', (w, h), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    # Draw smooth gradient and shapes
    for y in range(h):
        r = int(30 + 180 * (y / h))
        for x in range(w):
            g = int(20 + 120 * (x / w))
            b = int(40 + 140 * ((x + y) / (w + h)))
            # Force LSBs to have a natural correlation rather than purely random
            img.putpixel((x, y), (r, g, b))

    draw.ellipse([60, 60, 240, 240], fill=(220, 160, 80), outline=(255, 255, 255))
    draw.rectangle([100, 100, 200, 200], fill=(70, 130, 180))

    clean_path = os.path.join(output_dir, 'clean_sample.png')
    img.save(clean_path, format='PNG')
    print(f"Generated clean sample: {clean_path}")

    # 2. Generate Stego LSB Sample
    # Embed pseudorandom payload into the LSB of pixels
    stego_arr = np.array(img).copy()
    np.random.seed(42)  # Deterministic seed for reproducible testing
    # Generate random bits (0 or 1)
    payload_bits = np.random.randint(0, 2, size=stego_arr.shape, dtype=np.uint8)
    # Clear LSB and embed random bit: (val & 0xFE) | bit
    stego_arr = (stego_arr & np.uint8(0xFE)) | payload_bits

    stego_img = Image.fromarray(stego_arr)
    stego_path = os.path.join(output_dir, 'stego_lsb_sample.png')
    stego_img.save(stego_path, format='PNG')
    print(f"Generated LSB stego sample: {stego_path}")

    # 3. Generate Stego EOF Sample (Appended trailing data in JPEG)
    jpg_buf = BytesIO()
    img.save(jpg_buf, format='JPEG', quality=90)
    raw_jpeg = jpg_buf.getvalue()

    # Append secret payload past the EOF marker
    secret_payload = b"\n--- SECRET FORENSIC PAYLOAD ---\nHIDDEN_DATA_KEY=CYBERSEC_CONFIDENTIAL_TOKEN_2026\n"
    tampered_jpeg = raw_jpeg + secret_payload

    eof_path = os.path.join(output_dir, 'stego_eof_sample.jpg')
    with open(eof_path, 'wb') as f:
        f.write(tampered_jpeg)
    print(f"Generated EOF trailing data sample: {eof_path}")

if __name__ == '__main__':
    generate_samples()
