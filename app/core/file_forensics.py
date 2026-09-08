import struct
from typing import Dict, Any, List, Tuple, Optional

class FileForensicsAnalyzer:
    """
    Performs static, safe, non-destructive file and container forensics on image byte streams.

    Capabilities:
    - Detects embedded container/payload signatures (ZIP, PDF, RAR, 7z, Windows PE, ELF, GZIP, TAR, Java class, SQLite)
    - Distinguishes carrier headers (offset 0) from embedded or trailing signatures
    - Applies structural heuristics to suppress false positives from short byte sequences in compressed raster data
    - Identifies trailing appended data past authoritative image EOF boundaries (PNG, JPEG, BMP, WebP)
    - Assesses potential polyglot structures where an image coexists with a secondary file format
    - Operates purely through static byte inspection without executing or extracting untrusted payloads
    """

    # Primary container and executable signature definitions
    # Format: (type_name, signature_bytes, description)
    CONTAINER_SIGNATURES: List[Tuple[str, bytes, str]] = [
        ('ZIP', b'PK\x03\x04', 'ZIP archive local file header'),
        ('PDF', b'%PDF-', 'Adobe Portable Document Format (PDF) header'),
        ('RAR', b'Rar!\x1a\x07', 'RAR archive container header'),
        ('7-Zip', b'7z\xbc\xaf\x27\x1c', '7-Zip archive container header'),
        ('Windows PE', b'MZ', 'Microsoft Windows DOS/PE executable header'),
        ('ELF', b'\x7fELF', 'Executable and Linkable Format (ELF) binary header'),
        ('GZIP', b'\x1f\x8b', 'GZIP compressed stream header'),
        ('TAR', b'ustar', 'POSIX TAR archive UStar header'),
        ('Java Class', b'\xca\xfe\xba\xbe', 'Java bytecode compiled class header'),
        ('SQLite', b'SQLite format 3\x00', 'SQLite database file header'),
        # Secondary image signatures occurring at offset > 0
        ('Embedded PNG', b'\x89PNG\r\n\x1a\n', 'Embedded PNG image container'),
        ('Embedded JPEG', b'\xff\xd8\xff', 'Embedded JPEG image container'),
        ('Embedded WebP', b'RIFF', 'Embedded RIFF/WebP container')
    ]

    JPEG_EOF_MARKER = b'\xff\xd9'
    PNG_IEND_CHUNK = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    PNG_IEND_ALT = b'IEND\xaeB`\x82'

    @classmethod
    def analyze_trailing_data(cls, file_bytes: bytes, image_format: str) -> Dict[str, Any]:
        """
        Calculates legitimate image termination boundaries and inspects appended trailing data.
        Supports PNG, JPEG, BMP, and WebP.
        """
        total_len = len(file_bytes)
        eof_index = total_len
        trailing_data = b''
        norm_fmt = (image_format or '').upper()

        if norm_fmt == 'JPEG':
            eof_pos = file_bytes.rfind(cls.JPEG_EOF_MARKER)
            if eof_pos != -1:
                eof_index = eof_pos + 2
                if eof_index < total_len:
                    trailing_data = file_bytes[eof_index:]

        elif norm_fmt == 'PNG':
            eof_pos = file_bytes.rfind(cls.PNG_IEND_CHUNK)
            if eof_pos != -1:
                eof_index = eof_pos + len(cls.PNG_IEND_CHUNK)
                if eof_index < total_len:
                    trailing_data = file_bytes[eof_index:]
            else:
                alt_pos = file_bytes.rfind(cls.PNG_IEND_ALT)
                if alt_pos != -1:
                    eof_index = alt_pos + len(cls.PNG_IEND_ALT)
                    if eof_index < total_len:
                        trailing_data = file_bytes[eof_index:]

        elif norm_fmt == 'BMP':
            if total_len >= 6:
                declared_size = struct.unpack('<I', file_bytes[2:6])[0]
                if 0 < declared_size < total_len:
                    eof_index = declared_size
                    trailing_data = file_bytes[declared_size:]

        elif norm_fmt == 'WEBP':
            if total_len >= 8 and file_bytes.startswith(b'RIFF'):
                riff_size = struct.unpack('<I', file_bytes[4:8])[0]
                expected_size = riff_size + 8
                if 0 < expected_size < total_len:
                    eof_index = expected_size
                    trailing_data = file_bytes[expected_size:]

        has_trailing = len(trailing_data) > 0
        trailing_len = len(trailing_data)

        preview_hex = ''
        preview_ascii = ''
        if has_trailing:
            sample = trailing_data[:64]
            preview_hex = sample.hex(' ')
            preview_ascii = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in sample)
            description = f"Found {trailing_len:,} appended bytes past expected {norm_fmt} termination (offset {eof_index})."
        else:
            description = f"No trailing bytes detected beyond expected {norm_fmt} termination."

        return {
            'detected': has_trailing,
            'size': trailing_len,
            'offset': eof_index if has_trailing else total_len,
            'description': description,
            'preview_hex': preview_hex,
            'preview_ascii': preview_ascii,
            'has_trailing_data': has_trailing,
            'trailing_bytes_count': trailing_len,
            'trailing_percentage': round((trailing_len / total_len) * 100, 2) if total_len > 0 else 0.0,
            'eof_offset': eof_index
        }

    @classmethod
    def _validate_pe_signature(cls, file_bytes: bytes, offset: int, after_eof: bool) -> Tuple[Optional[str], Optional[str]]:
        """Validates Windows PE / DOS executable structure at the given offset."""
        # Check DOS header e_lfanew pointer to PE header (offset 0x3C)
        if offset + 0x40 <= len(file_bytes):
            pe_ptr = struct.unpack('<I', file_bytes[offset + 0x3c : offset + 0x40])[0]
            if 0 < pe_ptr < 1024 and offset + pe_ptr + 4 <= len(file_bytes):
                if file_bytes[offset + pe_ptr : offset + pe_ptr + 4] == b'PE\x00\x00':
                    return 'high', 'Confirmed Windows PE executable header with verified PE signature.'
        # Check for classic DOS stub banner
        snippet = file_bytes[offset : min(len(file_bytes), offset + 256)]
        if b'This program cannot be run in DOS mode' in snippet or b'!This program' in snippet:
            return 'high', 'Windows DOS executable stub with standard banner message detected.'
        if after_eof:
            return 'medium', 'Windows DOS executable header marker (MZ) located in trailing appended data.'
        # Suppress coincidental 2-byte MZ in compressed raster stream
        return None, None

    @classmethod
    def _validate_gzip_signature(cls, file_bytes: bytes, offset: int, after_eof: bool) -> Tuple[Optional[str], Optional[str]]:
        """Validates GZIP structure at the given offset."""
        if offset + 4 <= len(file_bytes):
            compression_method = file_bytes[offset + 2]
            flags = file_bytes[offset + 3]
            # Standard GZIP uses DEFLATE (8) and reserved bits 5,6,7 in flags must be 0
            if compression_method == 8 and (flags & 0xE0) == 0:
                strength = 'high' if after_eof else 'medium'
                return strength, 'Recognizable GZIP stream with valid DEFLATE compression method.'
        if after_eof:
            return 'medium', 'GZIP header marker (0x1F8B) located in trailing appended data.'
        # Suppress coincidental 2-byte 0x1F8B in compressed raster stream
        return None, None

    @classmethod
    def _validate_tar_signature(cls, file_bytes: bytes, offset: int, after_eof: bool) -> Tuple[Optional[str], Optional[str]]:
        """Validates TAR archive structure at the given offset."""
        # Check for ustar\0 or ustar  \0
        if offset + 8 <= len(file_bytes):
            ver = file_bytes[offset + 5 : offset + 8]
            if ver in (b'\x0000', b' \x00', b'00\x00', b'\x00\x00\x00'):
                return 'high', 'POSIX UStar archive header with valid version field.'
        if after_eof:
            return 'medium', 'TAR UStar signature identified in trailing appended data.'
        return 'medium', 'TAR UStar signature found within carrier byte stream.'

    @classmethod
    def _validate_java_signature(cls, file_bytes: bytes, offset: int, after_eof: bool) -> Tuple[Optional[str], Optional[str]]:
        """Validates Java class bytecode header at the given offset."""
        if offset + 8 <= len(file_bytes):
            major_version = struct.unpack('>H', file_bytes[offset + 6 : offset + 8])[0]
            # Java class major versions range from 45 (Java 1.1) to 70 (modern Java)
            if 45 <= major_version <= 70:
                return 'high', f'Java class bytecode header with valid format version (major={major_version}).'
        if after_eof:
            return 'medium', 'Java bytecode magic marker (0xCAFEBABE) in trailing data.'
        return None, None

    @classmethod
    def _validate_pdf_signature(cls, file_bytes: bytes, offset: int, after_eof: bool) -> Tuple[Optional[str], Optional[str]]:
        """Validates PDF header at the given offset."""
        snippet = file_bytes[offset : min(len(file_bytes), offset + 16)]
        if len(snippet) >= 8 and snippet.startswith(b'%PDF-'):
            version_char = chr(snippet[5]) if snippet[5:6].isdigit() else ''
            strength = 'high'
            return strength, f'Recognizable PDF document header (version %PDF-{version_char}x) found.'
        return 'medium', 'PDF header marker (%PDF-) identified.'

    @classmethod
    def _validate_zip_signature(cls, file_bytes: bytes, offset: int, after_eof: bool) -> Tuple[Optional[str], Optional[str]]:
        """Validates ZIP archive local file header."""
        if offset + 30 <= len(file_bytes):
            # Inspect local file header structure
            version_needed = struct.unpack('<H', file_bytes[offset + 4 : offset + 6])[0]
            if version_needed <= 100:  # Sensible ZIP version
                return 'high', 'Recognizable ZIP archive local file header with valid header fields.'
        if after_eof:
            return 'high', 'ZIP archive header identified in trailing appended data.'
        return 'medium', 'ZIP archive local file header marker found.'

    @classmethod
    def scan_signatures(
        cls,
        file_bytes: bytes,
        image_format: str,
        eof_offset: int
    ) -> List[Dict[str, Any]]:
        """
        Performs bounded static linear signature scanning over image bytes.
        Suppresses carrier headers at offset 0.
        """
        findings: List[Dict[str, Any]] = []
        total_len = len(file_bytes)
        norm_fmt = (image_format or '').upper()

        for type_name, sig_bytes, desc in cls.CONTAINER_SIGNATURES:
            sig_len = len(sig_bytes)
            start_pos = 0

            while True:
                pos = file_bytes.find(sig_bytes, start_pos)
                if pos == -1:
                    break

                start_pos = pos + 1  # Advance for subsequent matches

                # FALSE-POSITIVE CONTROL: Exclude carrier image headers at offset 0
                if pos == 0:
                    if norm_fmt == 'PNG' and sig_bytes.startswith(b'\x89PNG'):
                        continue
                    if norm_fmt == 'JPEG' and sig_bytes.startswith(b'\xff\xd8\xff'):
                        continue
                    if norm_fmt == 'BMP' and sig_bytes == b'BM':
                        continue
                    if norm_fmt == 'WEBP' and sig_bytes == b'RIFF':
                        continue

                # For embedded image checks, skip if format doesn't match full image header
                if type_name == 'Embedded WebP':
                    if pos + 12 > total_len or file_bytes[pos + 8 : pos + 12] != b'WEBP':
                        continue
                    if pos == 0 and norm_fmt == 'WEBP':
                        continue

                after_eof = pos >= eof_offset
                in_payload = not after_eof

                location = 'trailing' if after_eof else ('header' if pos < 128 else 'embedded')

                # Secondary structural validation for short / heuristic signatures
                if type_name == 'Windows PE':
                    strength, reason = cls._validate_pe_signature(file_bytes, pos, after_eof)
                elif type_name == 'GZIP':
                    strength, reason = cls._validate_gzip_signature(file_bytes, pos, after_eof)
                elif type_name == 'TAR':
                    strength, reason = cls._validate_tar_signature(file_bytes, pos, after_eof)
                elif type_name == 'Java Class':
                    strength, reason = cls._validate_java_signature(file_bytes, pos, after_eof)
                elif type_name == 'PDF':
                    strength, reason = cls._validate_pdf_signature(file_bytes, pos, after_eof)
                elif type_name == 'ZIP':
                    strength, reason = cls._validate_zip_signature(file_bytes, pos, after_eof)
                else:
                    strength = 'high' if after_eof else 'medium'
                    reason = f"Recognizable {desc} identified in byte stream."

                # If false-positive suppression indicated rejection, skip
                if strength is None:
                    continue

                # Format signature representation safely
                sig_repr = sig_bytes.decode('ascii', errors='backslashreplace')

                findings.append({
                    'type': type_name,
                    'signature': sig_repr,
                    'offset': pos,
                    'distance_from_start': pos,
                    'is_at_start': (pos == 0),
                    'after_image_eof': after_eof,
                    'in_image_payload': in_payload,
                    'evidence_strength': strength,
                    'location': location,
                    'reason': reason
                })

                # Cap max signature findings per scan to avoid unbounded memory
                if len(findings) >= 50:
                    break

            if len(findings) >= 50:
                break

        # Sort findings by offset
        findings.sort(key=lambda x: x['offset'])
        return findings

    @classmethod
    def evaluate_polyglot(
        cls,
        image_format: str,
        embedded_signatures: List[Dict[str, Any]],
        trailing_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Conservative polyglot assessment heuristic.
        Flags suspected polyglots when a valid image structure coexists with a recognizable
        secondary container signature of medium or high evidence strength.
        """
        norm_fmt = (image_format or '').upper()
        if not norm_fmt or norm_fmt == 'UNKNOWN':
            return False, 'Carrier image format is unverified; polyglot condition cannot be determined.'

        # Look for medium or high strength signatures of foreign container formats
        qualified_sigs = [
            s for s in embedded_signatures
            if s['evidence_strength'] in ('high', 'medium')
            and s['type'] not in ('Embedded PNG', 'Embedded JPEG', 'Embedded WebP')
        ]

        if not qualified_sigs:
            return False, 'No verified secondary container signatures detected.'

        # Highest priority: signature located in trailing appended data
        trailing_sigs = [s for s in qualified_sigs if s['after_image_eof']]
        if trailing_sigs:
            primary_sig = trailing_sigs[0]
            return True, (
                f"Valid {norm_fmt} image coexists with a recognizable {primary_sig['type']} "
                f"container appended after EOF (offset {primary_sig['offset']:,})."
            )

        # Secondary: high strength signature embedded inside payload
        high_strength = [s for s in qualified_sigs if s['evidence_strength'] == 'high']
        if high_strength:
            primary_sig = high_strength[0]
            return True, (
                f"Valid {norm_fmt} image coexists with an embedded {primary_sig['type']} "
                f"container signature at offset {primary_sig['offset']:,}."
            )

        return False, 'Secondary signatures lack sufficient structural evidence to confirm a polyglot container.'

    @classmethod
    def analyze(cls, file_bytes: bytes, meta_res: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes full file and container forensic inspection.

        Args:
            file_bytes: Authoritatively validated image byte stream.
            meta_res: Optional Layer 1 metadata results dictionary.

        Returns:
            Structured forensic analysis dictionary.
        """
        image_format = 'unknown'
        if meta_res:
            image_format = meta_res.get('detected_format', 'unknown')

        # 1. Trailing data boundary analysis
        trailing_info = cls.analyze_trailing_data(file_bytes, image_format)
        eof_offset = trailing_info['offset']

        # 2. Signature scan across byte stream
        embedded_sigs = cls.scan_signatures(file_bytes, image_format, eof_offset)

        # 3. Polyglot heuristic assessment
        is_polyglot, polyglot_reason = cls.evaluate_polyglot(
            image_format,
            embedded_sigs,
            trailing_info
        )

        # 4. Compute structural anomaly indicator in [0.0, 1.0]
        # Trailing bytes contribution
        trailing_bytes = trailing_info['size']
        if trailing_bytes > 512:
            i_trailing = 1.0
        elif trailing_bytes > 64:
            i_trailing = 0.70
        elif trailing_bytes > 0:
            i_trailing = 0.40
        else:
            i_trailing = 0.0

        # Embedded signature contribution
        i_sig = 0.0
        for s in embedded_sigs:
            if s['after_image_eof'] and s['evidence_strength'] in ('high', 'medium'):
                i_sig = max(i_sig, 1.0)
            elif s['evidence_strength'] == 'high':
                i_sig = max(i_sig, 0.85)
            elif s['evidence_strength'] == 'medium':
                i_sig = max(i_sig, 0.60)
            elif s['evidence_strength'] == 'low':
                i_sig = max(i_sig, 0.30)

        # Polyglot contribution
        i_poly = 1.0 if is_polyglot else 0.0

        structural_indicator = min(1.0, max(i_trailing, i_sig, i_poly))

        # Human-readable forensic summary
        if is_polyglot:
            summary = f"Polyglot container suspected: {polyglot_reason}"
        elif embedded_sigs:
            summary = f"Detected {len(embedded_sigs)} embedded signature(s) within image byte stream."
        elif trailing_info['detected']:
            summary = f"Appended trailing data detected ({trailing_bytes:,} bytes past EOF)."
        else:
            summary = "File structure strictly adheres to standard container boundaries with zero foreign signatures."

        return {
            'trailing_data': trailing_info,
            'embedded_signatures': embedded_sigs,
            'embedded_signature_count': len(embedded_sigs),
            'polyglot_suspected': is_polyglot,
            'polyglot_reason': polyglot_reason,
            'structural_anomaly_indicator': round(structural_indicator, 2),
            'summary': summary
        }
