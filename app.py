import os
from flask import Flask
from flask_minify import Minify
from flask_wtf.csrf import CSRFProtect  # <-- 1. IMPORTAR A CLASSE

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('FLASK_SECRET_KEY')

    CSRFProtect(app) # 2. Inicialize

    if not app.config['DEBUG']:
        Minify(app=app, html=True, js=True, cssless=True)

        from routes.auth import auth_bp
        from routes.main import main_bp
        from routes.admin import admin_bp
        from routes.pedidos import pedidos_bp
        from routes.packing import packing_bp
        # 1. Importe o novo blueprint
        from routes.painel_retirada import painel_retirada_bp 

        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(pedidos_bp)
        app.register_blueprint(packing_bp)
        # 2. Registre o novo blueprint
        app.register_blueprint(painel_retirada_bp)

        return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)