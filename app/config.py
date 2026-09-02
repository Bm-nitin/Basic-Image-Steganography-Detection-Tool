import os
import tempfile

class Config:
    """Application configuration settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'cybersec-stego-detection-secret-key-2026')
    
    # 10 MB upload ceiling to prevent memory exhaustion and DoS
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
    
    # Allowed image extensions
    ALLOWED_EXTENSIONS = {'png', 'bmp', 'jpg', 'jpeg', 'webp'}
    
    # Allowed MIME types for strict magic byte / content verification
    ALLOWED_MIMETYPES = {
        'image/png',
        'image/jpeg',
        'image/bmp',
        'image/webp'
    }
    
    # Decompression bomb safety limits (prevent pixel floods)
    MAX_IMAGE_PIXELS = int(os.environ.get('MAX_IMAGE_PIXELS', 25_000_000))
    MAX_IMAGE_DIMENSION = 4096  # Max width or height in pixels
    
    # Base temporary working directory for file processing
    TEMP_STORAGE_DIR = os.path.join(tempfile.gettempdir(), 'stego_detector_temp')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = True


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}
