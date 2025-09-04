import os
from flask import Flask
from flask_minify import Minify

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('FLASK_SECRET_KEY')

    if not app.config['DEBUG']:
        Minify(app=app, html=True, js=True, cssless=True)

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)