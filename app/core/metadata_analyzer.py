import hashlib
import struct
from io import BytesIO
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ExifTags

class MetadataAnalyzer:
    """
    Performs structural, metadata, signature, and EOF/trailing-data forensic analysis on image files.
    """

    MAGIC_SIGNATURES = {
        'png': b'\x89PNG\r\n\x1a\n',
        'jpeg': (b'\xff\xd8\xff',),
        'bmp': b'BM',
        'webp': b'RIFF'  # and WEBP at offset 8
    }

    JPEG_EOF_MARKER = b'\xff\xd9'
    PNG_IEND_MARKER = b'IEND\xaeB`\x82'

    KNOWN_STEGO_SIGNATURES = [
        b'openstego',
        b'steghide',
        b'outguess',
        b'camouflage',
        b'jsteg',
        b'stegdetect'
    ]

    @classmethod
    def calculate_hashes(cls, file_bytes: bytes) -> Dict[str, str]:
        """Calculates cryptographic MD5 and SHA-256 integrity hashes."""
        md5_hash = hashlib.md5(file_bytes).hexdigest()
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        return {
            'md5': md5_hash,
            'sha256': sha256_hash
        }

    @classmethod
    def verify_magic_bytes(cls, file_bytes: bytes, filename: str) -> Tuple[bool, str, str]:
        """
        Verifies whether file magic bytes match legitimate image formats.
        Returns: (is_valid, detected_format, message)
        """
        if len(file_bytes) < 16:
            return False, 'unknown', 'File too small to be a valid image header.'

        if file_bytes.startswith(cls.MAGIC_SIGNATURES['png']):
            return True, 'PNG', 'Valid PNG magic header verified.'
        
        if file_bytes.startswith(b'\xff\xd8\xff'):
            return True, 'JPEG', 'Valid JPEG magic header verified.'
        
        if file_bytes.startswith(cls.MAGIC_SIGNATURES['bmp']):
            return True, 'BMP', 'Valid BMP magic header verified.'
        
        if file_bytes.startswith(b'RIFF') and len(file_bytes) >= 12 and file_bytes[8:12] == b'WEBP':
            return True, 'WEBP', 'Valid WebP magic header verified.'

        return False, 'unknown', 'File signature does not match any accepted image format (PNG, JPEG, BMP, WebP).'

    @classmethod
    def detect_trailing_data(cls, file_bytes: bytes, image_format: str) -> Dict[str, Any]:
        """
        Detects appended/trailing data past the legitimate End-of-File marker.
        Common in naive append steganography (e.g. CTF challenges, simple file binders).
        """
        total_len = len(file_bytes)
        trailing_data = b''
        eof_index = -1
        status = 'Normal'

        if image_format == 'JPEG':
            # Search for the last occurrence of JPEG EOI marker (0xFF, 0xD9)
            eof_pos = file_bytes.rfind(cls.JPEG_EOF_MARKER)
            if eof_pos != -1:
                eof_index = eof_pos + 2
                if eof_index < total_len:
                    trailing_data = file_bytes[eof_index:]

        elif image_format == 'PNG':
            # Search for the standard IEND chunk: length (0), 'IEND', and 4-byte CRC
            # The chunk data itself is 00 00 00 00 49 45 4E 44 AE 42 60 82
            iend_full = b'\x00\x00\x00\x00' + cls.PNG_IEND_MARKER
            eof_pos = file_bytes.rfind(iend_full)
            if eof_pos != -1:
                eof_index = eof_pos + len(iend_full)
                if eof_index < total_len:
                    trailing_data = file_bytes[eof_index:]
            else:
                # Fallback to standard IEND + CRC
                alt_pos = file_bytes.rfind(cls.PNG_IEND_MARKER)
                if alt_pos != -1:
                    eof_index = alt_pos + len(cls.PNG_IEND_MARKER)
                    if eof_index < total_len:
                        trailing_data = file_bytes[eof_index:]

        elif image_format == 'BMP':
            # In BMP, bytes 2-5 contain the total file size in little-endian uint32
            if total_len >= 6:
                declared_size = struct.unpack('<I', file_bytes[2:6])[0]
                if 0 < declared_size < total_len:
                    eof_index = declared_size
                    trailing_data = file_bytes[declared_size:]

        has_trailing = len(trailing_data) > 0
        trailing_len = len(trailing_data)

        # Analyze trailing content if present
        preview_hex = ''
        preview_ascii = ''
        if has_trailing:
            status = 'Anomaly Detected: Appended data found beyond EOF'
            sample = trailing_data[:64]
            preview_hex = sample.hex(' ')
            preview_ascii = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in sample)

        return {
            'has_trailing_data': has_trailing,
            'trailing_bytes_count': trailing_len,
            'trailing_percentage': round((trailing_len / total_len) * 100, 2) if total_len > 0 else 0.0,
            'status': status,
            'preview_hex': preview_hex,
            'preview_ascii': preview_ascii,
            'eof_offset': eof_index if eof_index != -1 else total_len
        }

    @classmethod
    def extract_metadata_and_exif(cls, file_bytes: bytes) -> Dict[str, Any]:
        """
        Parses image properties and EXIF headers, checking for stego software signatures.
        """
        metadata: Dict[str, Any] = {
            'exif_data': {},
            'suspicious_signatures': [],
            'dimensions': (0, 0),
            'color_mode': 'Unknown',
            'format_description': ''
        }

        # Check raw bytes for known stego signatures
        lower_bytes = file_bytes.lower()
        for sig in cls.KNOWN_STEGO_SIGNATURES:
            if sig in lower_bytes:
                metadata['suspicious_signatures'].append(sig.decode('ascii', errors='ignore'))

        try:
            with Image.open(BytesIO(file_bytes)) as img:
                metadata['dimensions'] = img.size
                metadata['color_mode'] = img.mode
                metadata['format_description'] = img.format_description or img.format or 'Unknown'

                # Extract EXIF if available
                exif = img.getexif()
                if exif:
                    for tag_id, val in exif.items():
                        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                        # Sanitize value representation
                        val_str = str(val)
                        if len(val_str) > 120:
                            val_str = val_str[:120] + '... [truncated]'
                        metadata['exif_data'][tag_name] = val_str

                        # Check for stego strings in text tags
                        if isinstance(val, (str, bytes)):
                            str_val = val.decode('utf-8', errors='ignore') if isinstance(val, bytes) else val
                            for sig in cls.KNOWN_STEGO_SIGNATURES:
                                if sig.decode('ascii') in str_val.lower():
                                    if sig.decode('ascii') not in metadata['suspicious_signatures']:
                                        metadata['suspicious_signatures'].append(sig.decode('ascii'))
        except Exception as e:
            metadata['error'] = f'Partial metadata parsing error: {str(e)}'

        return metadata

    @classmethod
    def analyze(cls, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Executes full Layer 1 forensic analysis."""
        hashes = cls.calculate_hashes(file_bytes)
        is_valid, detected_format, sig_msg = cls.verify_magic_bytes(file_bytes, filename)
        trailing_info = cls.detect_trailing_data(file_bytes, detected_format)
        metadata_info = cls.extract_metadata_and_exif(file_bytes)

        return {
            'is_valid_format': is_valid,
            'detected_format': detected_format,
            'signature_verification': sig_msg,
            'file_size_bytes': len(file_bytes),
            'hashes': hashes,
            'trailing_data': trailing_info,
            'metadata': metadata_info
        }
