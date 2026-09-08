import io
import struct
import os
import pytest
from PIL import Image

from app.core.file_forensics import FileForensicsAnalyzer
from app.core.metadata_analyzer import MetadataAnalyzer

# Fixtures for synthetic test images (strictly benign synthetic byte streams)
@pytest.fixture
def clean_png_bytes():
    bio = io.BytesIO()
    img = Image.new('RGB', (32, 32), color=(10, 20, 30))
    img.save(bio, format='PNG')
    return bio.getvalue()

@pytest.fixture
def clean_jpeg_bytes():
    bio = io.BytesIO()
    img = Image.new('RGB', (32, 32), color=(40, 50, 60))
    img.save(bio, format='JPEG')
    return bio.getvalue()

@pytest.fixture
def clean_bmp_bytes():
    bio = io.BytesIO()
    img = Image.new('RGB', (16, 16), color=(70, 80, 90))
    img.save(bio, format='BMP')
    return bio.getvalue()

@pytest.fixture
def clean_webp_bytes():
    bio = io.BytesIO()
    img = Image.new('RGB', (16, 16), color=(100, 110, 120))
    img.save(bio, format='WEBP')
    return bio.getvalue()


class TestFileForensicsAnalyzer:
    # 1. Clean PNG produces zero embedded signatures and clean structural findings
    def test_clean_png(self, clean_png_bytes):
        meta = MetadataAnalyzer.analyze(clean_png_bytes, 'clean.png')
        res = FileForensicsAnalyzer.analyze(clean_png_bytes, meta)
        assert res['embedded_signature_count'] == 0
        assert len(res['embedded_signatures']) == 0
        assert res['polyglot_suspected'] is False
        assert res['trailing_data']['detected'] is False
        assert res['structural_anomaly_indicator'] == 0.0

    # 2. Clean JPEG produces zero embedded signatures
    def test_clean_jpeg(self, clean_jpeg_bytes):
        meta = MetadataAnalyzer.analyze(clean_jpeg_bytes, 'clean.jpg')
        res = FileForensicsAnalyzer.analyze(clean_jpeg_bytes, meta)
        assert res['embedded_signature_count'] == 0
        assert res['polyglot_suspected'] is False
        assert res['trailing_data']['detected'] is False

    # 3. Clean BMP produces zero embedded signatures
    def test_clean_bmp(self, clean_bmp_bytes):
        meta = MetadataAnalyzer.analyze(clean_bmp_bytes, 'clean.bmp')
        res = FileForensicsAnalyzer.analyze(clean_bmp_bytes, meta)
        assert res['embedded_signature_count'] == 0
        assert res['polyglot_suspected'] is False
        assert res['trailing_data']['detected'] is False

    # 4. Clean WebP produces zero embedded signatures
    def test_clean_webp(self, clean_webp_bytes):
        meta = MetadataAnalyzer.analyze(clean_webp_bytes, 'clean.webp')
        res = FileForensicsAnalyzer.analyze(clean_webp_bytes, meta)
        assert res['embedded_signature_count'] == 0
        assert res['polyglot_suspected'] is False
        assert res['trailing_data']['detected'] is False

    # 5. PNG header at offset 0 is NOT reported as embedded PNG
    def test_png_header_at_offset_0_not_reported(self, clean_png_bytes):
        meta = MetadataAnalyzer.analyze(clean_png_bytes, 'sample.png')
        res = FileForensicsAnalyzer.analyze(clean_png_bytes, meta)
        reported_types = [s['type'] for s in res['embedded_signatures']]
        assert 'Embedded PNG' not in reported_types
        assert all(s['offset'] > 0 for s in res['embedded_signatures'])

    # 6. JPEG header at offset 0 is NOT reported as embedded JPEG
    def test_jpeg_header_at_offset_0_not_reported(self, clean_jpeg_bytes):
        meta = MetadataAnalyzer.analyze(clean_jpeg_bytes, 'sample.jpg')
        res = FileForensicsAnalyzer.analyze(clean_jpeg_bytes, meta)
        reported_types = [s['type'] for s in res['embedded_signatures']]
        assert 'Embedded JPEG' not in reported_types
        assert all(s['offset'] > 0 for s in res['embedded_signatures'])

    # 7. Embedded PDF signature
    def test_embedded_pdf_signature(self, clean_png_bytes):
        synthetic_pdf = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"
        tampered = clean_png_bytes + synthetic_pdf
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        pdf_sigs = [s for s in res['embedded_signatures'] if s['type'] == 'PDF']
        assert len(pdf_sigs) >= 1
        assert pdf_sigs[0]['offset'] >= len(clean_png_bytes)
        assert pdf_sigs[0]['evidence_strength'] == 'high'

    # 8. Embedded ZIP signature
    def test_embedded_zip_signature(self, clean_png_bytes):
        synthetic_zip = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 16 + struct.pack('<H', 8) + struct.pack('<H', 0) + b"test.txt"
        tampered = clean_png_bytes + synthetic_zip
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        zip_sigs = [s for s in res['embedded_signatures'] if s['type'] == 'ZIP']
        assert len(zip_sigs) >= 1
        assert zip_sigs[0]['evidence_strength'] in ('high', 'medium')

    # 9. Embedded PE MZ signature (synthetic DOS/PE structure)
    def test_embedded_pe_mz_signature(self, clean_png_bytes):
        # Construct benign synthetic PE header
        pe_offset = 0x80
        synthetic_pe = b"MZ" + b"\x00" * 58 + struct.pack('<I', pe_offset) + b"\x00" * (pe_offset - 64) + b"PE\x00\x00" + b"\x00" * 32
        tampered = clean_png_bytes + synthetic_pe
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        pe_sigs = [s for s in res['embedded_signatures'] if s['type'] == 'Windows PE']
        assert len(pe_sigs) >= 1
        assert pe_sigs[0]['evidence_strength'] == 'high'
        assert 'PE executable' in pe_sigs[0]['reason']

    # 10. Embedded ELF signature
    def test_embedded_elf_signature(self, clean_png_bytes):
        synthetic_elf = b"\x7fELF\x02\x01\x01" + b"\x00" * 32
        tampered = clean_png_bytes + synthetic_elf
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        elf_sigs = [s for s in res['embedded_signatures'] if s['type'] == 'ELF']
        assert len(elf_sigs) >= 1
        assert elf_sigs[0]['evidence_strength'] in ('high', 'medium')

    # 11. Embedded 7z signature
    def test_embedded_7z_signature(self, clean_png_bytes):
        synthetic_7z = b"7z\xbc\xaf\x27\x1c\x00\x04" + b"\x00" * 16
        tampered = clean_png_bytes + synthetic_7z
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        sz_sigs = [s for s in res['embedded_signatures'] if s['type'] == '7-Zip']
        assert len(sz_sigs) >= 1

    # 12. Embedded RAR signature
    def test_embedded_rar_signature(self, clean_png_bytes):
        synthetic_rar = b"Rar!\x1a\x07\x00" + b"\x00" * 16
        tampered = clean_png_bytes + synthetic_rar
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        rar_sigs = [s for s in res['embedded_signatures'] if s['type'] == 'RAR']
        assert len(rar_sigs) >= 1

    # 13. Embedded GZIP signature
    def test_embedded_gzip_signature(self, clean_png_bytes):
        synthetic_gzip = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03" + b"\x00" * 16
        tampered = clean_png_bytes + synthetic_gzip
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        gzip_sigs = [s for s in res['embedded_signatures'] if s['type'] == 'GZIP']
        assert len(gzip_sigs) >= 1
        assert gzip_sigs[0]['evidence_strength'] in ('high', 'medium')

    # 14. Trailing data detection
    def test_trailing_data_detection(self, clean_jpeg_bytes):
        appended_bytes = b"EXTRA_TRAILING_FORENSIC_PAYLOAD_12345"
        tampered = clean_jpeg_bytes + appended_bytes
        meta = MetadataAnalyzer.analyze(tampered, 'sample.jpg')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        assert res['trailing_data']['detected'] is True
        assert res['trailing_data']['size'] == len(appended_bytes)
        assert res['trailing_data']['offset'] == len(clean_jpeg_bytes)
        assert 'EXTRA_TRAILING' in res['trailing_data']['preview_ascii']

    # 15. PDF appended after JPEG EOF
    def test_pdf_appended_after_jpeg_eof(self, clean_jpeg_bytes):
        synthetic_pdf = b"%PDF-1.4\n%Trailer payload test\n%%EOF"
        tampered = clean_jpeg_bytes + synthetic_pdf
        meta = MetadataAnalyzer.analyze(tampered, 'sample.jpg')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        pdf_sigs = [s for s in res['embedded_signatures'] if s['type'] == 'PDF']
        assert len(pdf_sigs) >= 1
        assert pdf_sigs[0]['after_image_eof'] is True
        assert pdf_sigs[0]['location'] == 'trailing'

    # 16. Possible polyglot indicator
    def test_possible_polyglot_indicator(self, clean_png_bytes):
        synthetic_zip = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 16 + struct.pack('<H', 8) + struct.pack('<H', 0) + b"file.bin"
        tampered = clean_png_bytes + synthetic_zip
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        assert res['polyglot_suspected'] is True
        assert 'ZIP' in res['polyglot_reason']
        assert res['structural_anomaly_indicator'] == 1.0

    # 17. Multiple embedded signatures
    def test_multiple_embedded_signatures(self, clean_png_bytes):
        synthetic_multi = b"%PDF-1.7\n" + b"\x00" * 20 + b"PK\x03\x04\x14\x00" + b"\x00" * 20
        tampered = clean_png_bytes + synthetic_multi
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        types_found = {s['type'] for s in res['embedded_signatures']}
        assert 'PDF' in types_found
        assert 'ZIP' in types_found
        assert res['embedded_signature_count'] >= 2

    # 18. Random bytes containing no known signatures
    def test_random_bytes_no_known_signatures(self, clean_png_bytes):
        # 256 bytes of repetitive ASCII text without container signatures
        neutral_data = b"ABCDEFGHIJ" * 25
        tampered = clean_png_bytes + neutral_data
        meta = MetadataAnalyzer.analyze(tampered, 'sample.png')
        res = FileForensicsAnalyzer.analyze(tampered, meta)
        assert res['embedded_signature_count'] == 0
        assert res['polyglot_suspected'] is False
        assert res['trailing_data']['detected'] is True  # Appended bytes detected, but no signatures

    # 19. Malformed / corrupted binary input
    def test_malformed_input_graceful(self):
        corrupt_bytes = b"\x89PNG\r\n\x1a\n\xff\x00\x12\x34\xaa\xbb\xcc\xdd" * 10
        meta = {'detected_format': 'PNG'}
        # Must execute cleanly without unhandled exceptions
        res = FileForensicsAnalyzer.analyze(corrupt_bytes, meta)
        assert isinstance(res, dict)
        assert 'trailing_data' in res
        assert 'embedded_signatures' in res

    # 20. Large bounded input does not cause excessive processing
    def test_large_bounded_input_performance(self, clean_png_bytes):
        # 3 MB of synthetic image bytes
        large_bytes = clean_png_bytes + b"\x00" * (3 * 1024 * 1024)
        meta = MetadataAnalyzer.analyze(large_bytes, 'large.png')
        import time
        t0 = time.perf_counter()
        res = FileForensicsAnalyzer.analyze(large_bytes, meta)
        duration = time.perf_counter() - t0
        # Linear scan over 3 MB should complete in well under 1.0 second
        assert duration < 1.0, f"Scan took too long: {duration:.3f}s"
        assert res['trailing_data']['detected'] is True
