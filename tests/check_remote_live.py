import sys
import json
import urllib.request

BASE = 'https://basic-image-steganography-detection-tool.onrender.com'

def run():
    print(f"Testing live remote deployment at: {BASE}")
    try:
        # 1. Health
        req = urllib.request.Request(f"{BASE}/health", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            print(f"[LIVE CHECK 1] GET /health -> Status: {r.status}, Data: {data}")

        # 2. Homepage
        req = urllib.request.Request(f"{BASE}/", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8')
            print(f"[LIVE CHECK 2] GET / -> Status: {r.status}, HTML Size: {len(html)} bytes")

        # 3. API Analyze
        boundary = '----LiveBoundaryCheck999'
        with open('tests/test_samples/clean_sample.png', 'rb') as f:
            img_bytes = f.read()

        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="image"; filename="clean_sample.png"\r\n'
            f'Content-Type: image/png\r\n\r\n'
        ).encode('utf-8') + img_bytes + f'\r\n--{boundary}--\r\n'.encode('utf-8')

        req = urllib.request.Request(
            f"{BASE}/api/analyze",
            data=body,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'User-Agent': 'Mozilla/5.0'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as r:
            res_data = json.loads(r.read())
            print(f"[LIVE CHECK 3] POST /api/analyze -> Status: {r.status}")
            print(f"               Risk Level: {res_data.get('scoring', {}).get('risk_level')}")
            print(f"               Suspicion Score: {res_data.get('scoring', {}).get('suspicion_score')}")
            print(f"               Confidence: {res_data.get('scoring', {}).get('confidence')}")

        print("\nAll remote live checks passed successfully!")
    except Exception as e:
        print(f"Error during remote live check: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run()
