import urllib.request
import re
import pytest

def test_live_workflow():
    try:
        urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=0.5)
    except Exception:
        pytest.skip("Local test server not running on http://127.0.0.1:5000")

    boundary = '----WebKitFormBoundaryForensicTest123'
    with open('tests/test_samples/stego_lsb_sample.png', 'rb') as f:
        img_data = f.read()

    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="stego_lsb_sample.png"\r\n'
        f'Content-Type: image/png\r\n\r\n'
    ).encode('utf-8') + img_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')

    req = urllib.request.Request(
        'http://127.0.0.1:5000/analyze',
        data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST'
    )

    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8')
        print(f"POST /analyze status: {resp.getcode()}")
        print(f"HTML response size:  {len(html):,} bytes")
        match = re.search(r'/download-report/([a-f0-9\-]+)', html)
        assert match is not None, "Failed to locate report ID in rendered HTML!"
        report_id = match.group(1)
        print(f"Extracted Report ID:   {report_id}")

        pdf_url = f'http://127.0.0.1:5000/download-report/{report_id}'
        with urllib.request.urlopen(pdf_url) as pdf_resp:
            pdf_bytes = pdf_resp.read()
            print(f"GET /download-report:  {pdf_resp.getcode()}")
            print(f"PDF bytes received:    {len(pdf_bytes):,} bytes")
            print(f"Valid %PDF header:     {pdf_bytes.startswith(b'%PDF')}")
            assert pdf_bytes.startswith(b'%PDF'), "Downloaded file is not a valid PDF!"

    print("\nLive end-to-end HTTP test passed successfully!")

if __name__ == '__main__':
    test_live_workflow()
