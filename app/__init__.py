import os
from flask import Flask, render_template, request, jsonify
from app.config import config_by_name

def create_app(config_name: str = None) -> Flask:
    """
    Application Factory for Basic Image Steganography Detection Tool.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    config_obj = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(config_obj)

    # Ensure secure temporary directories exist
    os.makedirs(app.config.get('TEMP_STORAGE_DIR', '/tmp'), exist_ok=True)

    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    # Custom Error Handlers
    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Bad Request',
                'code': 'BAD_REQUEST',
                'details': str(error)
            }), 400
        return render_template('errors/400.html', error=error), 400

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Not Found',
                'code': 'NOT_FOUND',
                'details': 'The requested API endpoint was not found.'
            }), 404
        return render_template('errors/404.html', error=error), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        if request.path.startswith('/api/'):
            max_bytes = app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024)
            max_mb = max(1, max_bytes // (1024 * 1024))
            return jsonify({
                'error': 'Image validation failed',
                'code': 'FILE_TOO_LARGE',
                'details': f"File exceeds maximum allowed size of {max_mb} MB."
            }), 413
        return render_template('errors/413.html', error=error), 413

    @app.errorhandler(500)
    def internal_server_error(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal Server Error',
                'code': 'SERVER_ERROR',
                'details': 'An internal server error occurred.'
            }), 500
        return render_template('errors/500.html', error=error), 500

    return app
