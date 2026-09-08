import io
from typing import Dict, Any, Optional, List, Tuple
from werkzeug.utils import secure_filename
from PIL import Image

class ImageValidator:
    """
    Authoritative, multi-layer image ingestion and security validation engine.
    
    Provides defense-in-depth checks:
    - Input extraction (FileStorage, BytesIO, raw bytes)
    - Path traversal and filename sanitation
    - Extension whitelist verification
    - Payload size boundary enforcement
    - Strict magic-byte / file-signature verification
    - Format and MIME consistency analysis (spoofing detection)
    - Image dimension and pixel-flood / decompression bomb prevention
    - Stream integrity and corruption verification
    """

    MAGIC_SIGNATURES: Dict[str, bytes] = {
        'PNG': b'\x89PNG\r\n\x1a\n',
        'JPEG': b'\xff\xd8\xff',
        'BMP': b'BM',
        'WEBP_RIFF': b'RIFF',
        'WEBP_TAG': b'WEBP'
    }

    FORMAT_EXTENSIONS: Dict[str, List[str]] = {
        'PNG': ['png'],
        'JPEG': ['jpg', 'jpeg'],
        'BMP': ['bmp'],
        'WEBP': ['webp']
    }

    FORMAT_MIMETYPES: Dict[str, str] = {
        'PNG': 'image/png',
        'JPEG': 'image/jpeg',
        'BMP': 'image/bmp',
        'WEBP': 'image/webp'
    }

    DEFAULT_ALLOWED_EXTENSIONS = {'png', 'bmp', 'jpg', 'jpeg', 'webp'}
    DEFAULT_MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    DEFAULT_MAX_IMAGE_PIXELS = 25_000_000          # 25 MP ceiling
    DEFAULT_MAX_IMAGE_DIMENSION = 4096             # Max width or height

    @classmethod
    def identify_magic_format(cls, file_bytes: bytes) -> Tuple[bool, str, str]:
        """
        Inspects leading file bytes against authoritative image format signatures.
        Returns: (is_valid, detected_format, mime_type)
        """
        if len(file_bytes) < 12:
            return False, 'unknown', 'application/octet-stream'

        if file_bytes.startswith(cls.MAGIC_SIGNATURES['PNG']):
            return True, 'PNG', cls.FORMAT_MIMETYPES['PNG']

        if file_bytes.startswith(cls.MAGIC_SIGNATURES['JPEG']):
            return True, 'JPEG', cls.FORMAT_MIMETYPES['JPEG']

        if file_bytes.startswith(cls.MAGIC_SIGNATURES['BMP']):
            return True, 'BMP', cls.FORMAT_MIMETYPES['BMP']

        if file_bytes.startswith(cls.MAGIC_SIGNATURES['WEBP_RIFF']) and file_bytes[8:12] == cls.MAGIC_SIGNATURES['WEBP_TAG']:
            return True, 'WEBP', cls.FORMAT_MIMETYPES['WEBP']

        return False, 'unknown', 'application/octet-stream'

    @classmethod
    def validate(
        cls,
        file_source: Any,
        filename: Optional[str] = None,
        client_mimetype: Optional[str] = None,
        config: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Validates an incoming image file across all security layers.

        Args:
            file_source: Werkzeug FileStorage, io.BytesIO, or bytes.
            filename: Optional filename override.
            client_mimetype: Optional client-reported Content-Type header.
            config: Flask application config dictionary or mapping.

        Returns:
            Dict containing validation status, metadata, PIL image, and error/warning details.
        """
        # Resolve configuration boundaries
        if config is not None:
            allowed_exts = set(config.get('ALLOWED_EXTENSIONS', cls.DEFAULT_ALLOWED_EXTENSIONS))
            max_size = int(config.get('MAX_CONTENT_LENGTH', cls.DEFAULT_MAX_CONTENT_LENGTH))
            max_pixels = int(config.get('MAX_IMAGE_PIXELS', cls.DEFAULT_MAX_IMAGE_PIXELS))
            max_dim = int(config.get('MAX_IMAGE_DIMENSION', cls.DEFAULT_MAX_IMAGE_DIMENSION))
        else:
            allowed_exts = cls.DEFAULT_ALLOWED_EXTENSIONS
            max_size = cls.DEFAULT_MAX_CONTENT_LENGTH
            max_pixels = cls.DEFAULT_MAX_IMAGE_PIXELS
            max_dim = cls.DEFAULT_MAX_IMAGE_DIMENSION

        warnings: List[str] = []
        format_consistency: Dict[str, Any] = {
            'extension_mismatch': False,
            'mime_mismatch': False,
            'expected_extensions': [],
            'actual_extension': '',
            'detected_format': 'unknown',
            'client_mimetype': client_mimetype
        }

        # 1. Input source verification and byte extraction
        if file_source is None:
            return cls._failure_dict(
                error_code='MISSING_FILE',
                error_msg='No image file selected. Please choose a file to analyze.',
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        raw_name = filename
        if raw_name is None and hasattr(file_source, 'filename'):
            raw_name = file_source.filename

        if client_mimetype is None and hasattr(file_source, 'mimetype'):
            client_mimetype = file_source.mimetype
        format_consistency['client_mimetype'] = client_mimetype

        file_bytes: bytes = b''
        try:
            if hasattr(file_source, 'read'):
                if hasattr(file_source, 'seek'):
                    file_source.seek(0)
                file_bytes = file_source.read()
                if hasattr(file_source, 'seek'):
                    file_source.seek(0)
            elif isinstance(file_source, (bytes, bytearray)):
                file_bytes = bytes(file_source)
            else:
                return cls._failure_dict(
                    error_code='MISSING_FILE',
                    error_msg='Invalid image input stream type.',
                    client_mime=client_mimetype,
                    warnings=warnings,
                    consistency=format_consistency
                )
        except Exception as e:
            return cls._failure_dict(
                error_code='CORRUPT_IMAGE',
                error_msg=f'Failed to read image stream: {str(e)}',
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        # 2. Filename and extension checks
        if raw_name is None or str(raw_name).strip() == '':
            return cls._failure_dict(
                error_code='EMPTY_FILENAME',
                error_msg='No image file selected. Please select a valid file.',
                file_bytes=file_bytes,
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        safe_name = secure_filename(str(raw_name))
        if not safe_name:
            return cls._failure_dict(
                error_code='INVALID_FILENAME',
                error_msg='Filename contains invalid or prohibited characters.',
                file_bytes=file_bytes,
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        if '.' not in safe_name:
            return cls._failure_dict(
                error_code='UNSUPPORTED_EXTENSION',
                error_msg=f"Unsupported file extension. Allowed formats: {', '.join(sorted(allowed_exts)).upper()}",
                safe_filename=safe_name,
                file_bytes=file_bytes,
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        file_ext = safe_name.rsplit('.', 1)[1].lower()
        format_consistency['actual_extension'] = file_ext

        if file_ext not in allowed_exts:
            return cls._failure_dict(
                error_code='UNSUPPORTED_EXTENSION',
                error_msg=f"Unsupported file extension. Allowed formats: {', '.join(sorted(allowed_exts)).upper()}",
                extension=file_ext,
                safe_filename=safe_name,
                file_bytes=file_bytes,
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        # 3. Payload size constraints
        file_size = len(file_bytes)
        if file_size == 0:
            return cls._failure_dict(
                error_code='EMPTY_FILE',
                error_msg='The uploaded file is completely empty (0 bytes).',
                extension=file_ext,
                safe_filename=safe_name,
                file_bytes=file_bytes,
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        if file_size > max_size:
            max_mb = max_size // (1024 * 1024)
            return cls._failure_dict(
                error_code='FILE_TOO_LARGE',
                error_msg=f"File exceeds maximum allowed size of {max_mb} MB.",
                extension=file_ext,
                safe_filename=safe_name,
                file_bytes=file_bytes,
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        # 4. Strict magic byte verification
        is_valid_magic, detected_fmt, detected_mime = cls.identify_magic_format(file_bytes)
        format_consistency['detected_format'] = detected_fmt

        if not is_valid_magic:
            return cls._failure_dict(
                error_code='INVALID_MAGIC_BYTES',
                error_msg='Security Alert: Magic byte verification failed! File signature does not match any accepted image format (PNG, JPEG, BMP, WebP).',
                extension=file_ext,
                safe_filename=safe_name,
                file_bytes=file_bytes,
                client_mime=client_mimetype,
                warnings=warnings,
                consistency=format_consistency
            )

        # 5. Format and MIME consistency analysis (Non-blocking anomaly detection)
        expected_extensions = cls.FORMAT_EXTENSIONS.get(detected_fmt, [])
        format_consistency['expected_extensions'] = expected_extensions

        if file_ext not in expected_extensions:
            format_consistency['extension_mismatch'] = True
            warnings.append(
                f"Format spoofing warning: Extension is '.{file_ext}' but magic bytes identify '{detected_fmt}' format."
            )

        if client_mimetype and client_mimetype.lower() != detected_mime:
            format_consistency['mime_mismatch'] = True
            warnings.append(
                f"MIME mismatch warning: Client sent '{client_mimetype}' Content-Type but magic bytes indicate '{detected_mime}'."
            )

        # 6. Pillow image decoding and decompression bomb safety enforcement
        # Localize pixel ceiling to prevent DoS via massive allocations
        Image.MAX_IMAGE_PIXELS = max_pixels

        try:
            bio = io.BytesIO(file_bytes)
            pil_img = Image.open(bio)
            w, h = pil_img.size
            pixel_count = w * h

            # Verify individual dimension boundaries
            if w > max_dim or h > max_dim:
                return cls._failure_dict(
                    error_code='IMAGE_DIMENSION_LIMIT',
                    error_msg=f"Image dimensions ({w}x{h}) exceed maximum allowed dimension of {max_dim}px.",
                    format_name=detected_fmt,
                    extension=file_ext,
                    mime=detected_mime,
                    client_mime=client_mimetype,
                    safe_filename=safe_name,
                    file_bytes=file_bytes,
                    width=w,
                    height=h,
                    pixel_count=pixel_count,
                    warnings=warnings,
                    consistency=format_consistency
                )

            # Verify total pixel count boundary
            if pixel_count > max_pixels:
                return cls._failure_dict(
                    error_code='PIXEL_COUNT_LIMIT',
                    error_msg=f"Image pixel count ({pixel_count:,}) exceeds safety ceiling of {max_pixels:,} pixels.",
                    format_name=detected_fmt,
                    extension=file_ext,
                    mime=detected_mime,
                    client_mime=client_mimetype,
                    safe_filename=safe_name,
                    file_bytes=file_bytes,
                    width=w,
                    height=h,
                    pixel_count=pixel_count,
                    warnings=warnings,
                    consistency=format_consistency
                )

            # Force load raster data to catch corrupt chunks, truncated streams, or decompression attacks
            pil_img.load()

        except Image.DecompressionBombError:
            return cls._failure_dict(
                error_code='DECOMPRESSION_BOMB',
                error_msg='Security Alert: Potential decompression bomb / pixel flood attack detected.',
                format_name=detected_fmt,
                extension=file_ext,
                mime=detected_mime,
                client_mime=client_mimetype,
                safe_filename=safe_name,
                file_bytes=file_bytes,
                warnings=warnings,
                consistency=format_consistency
            )
        except Exception as e:
            return cls._failure_dict(
                error_code='CORRUPT_IMAGE',
                error_msg=f'Malformed or corrupt image structure: {str(e)}',
                format_name=detected_fmt,
                extension=file_ext,
                mime=detected_mime,
                client_mime=client_mimetype,
                safe_filename=safe_name,
                file_bytes=file_bytes,
                warnings=warnings,
                consistency=format_consistency
            )

        # 7. Successful validation return
        return {
            'valid': True,
            'format': detected_fmt,
            'extension': file_ext,
            'mime': detected_mime,
            'client_mime': client_mimetype,
            'size': file_size,
            'width': w,
            'height': h,
            'pixel_count': pixel_count,
            'safe_filename': safe_name,
            'file_bytes': file_bytes,
            'pil_image': pil_img,
            'errors': [],
            'error_code': None,
            'warnings': warnings,
            'format_consistency': format_consistency
        }

    @classmethod
    def _failure_dict(
        cls,
        error_code: str,
        error_msg: str,
        format_name: str = 'unknown',
        extension: str = '',
        mime: str = 'application/octet-stream',
        client_mime: Optional[str] = None,
        safe_filename: str = '',
        file_bytes: bytes = b'',
        width: int = 0,
        height: int = 0,
        pixel_count: int = 0,
        warnings: Optional[List[str]] = None,
        consistency: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Constructs a standardized validation failure payload."""
        return {
            'valid': False,
            'format': format_name,
            'extension': extension,
            'mime': mime,
            'client_mime': client_mime,
            'size': len(file_bytes),
            'width': width,
            'height': height,
            'pixel_count': pixel_count,
            'safe_filename': safe_filename,
            'file_bytes': file_bytes,
            'pil_image': None,
            'errors': [error_msg],
            'error_code': error_code,
            'warnings': warnings or [],
            'format_consistency': consistency or {}
        }
