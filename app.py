import os
from flask import Flask, request, url_for, session, flash, redirect, render_template
from flask_minify import Minify
from markupsafe import escape, Markup
import re
from urllib.parse import urlencode

from pytz import timezone
from config import auth
from datetime import datetime, timedelta, timezone
from permissions import get_current_user_permissions
import logging
from logging.handlers import RotatingFileHandler

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('FLASK_SECRET_KEY')
    
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
    app.jinja_env.add_extension('jinja2.ext.do')

    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/riofer_sgd.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Riofer SGD startup')

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Erro interno do servidor: {error}", exc_info=True)
        return render_template('500.html'), 500

    @app.context_processor
    def inject_permissions():
        return dict(permissions=get_current_user_permissions())

    @app.context_processor
    def inject_permissions():
        return dict(permissions=get_current_user_permissions())
    
    @app.before_request
    def refresh_firebase_token():
        if 'user' in session and 'refreshToken' in session['user'] and 'expires_at' in session['user']:
            
            expires_at = datetime.fromisoformat(session['user']['expires_at']).replace(tzinfo=None)
            
            # agora timezone existe
            if expires_at < datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5):
                try:
                    user_auth_data = auth.refresh(session['user']['refreshToken'])
                    
                    session['user']['idToken'] = user_auth_data['idToken']
                    session['user']['refreshToken'] = user_auth_data['refreshToken']
                    
                    new_expires_in = int(user_auth_data.get('expiresIn', 3600))
                    session['user']['expires_at'] = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=new_expires_in)).isoformat()
                    
                    session.modified = True 
                    
                except Exception as e:
                    flash('Sua sessão expirou. Por favor, faça login novamente.', 'warning')
                    session.pop('user', None)
                    if request.endpoint and 'login' not in request.endpoint and 'static' not in request.endpoint:
                        return redirect(url_for('auth.login'))
                
    def autolink(value):
        if not value:
            return ''
        url_pattern = re.compile(r'((?:https?://|www\.)[^\s<]+[^<.,:;"\'\]\s])')
        html = url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', escape(value))
        return Markup(html)

    def nl2br(value):
        if value is None:
            return ''
        linked_text = autolink(value)
        html = linked_text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>')
        return Markup(html)
    
    def url_for_with_query(endpoint, **overrides):
        args = request.args.to_dict(flat=False)
        for k, v in overrides.items():
            args[k] = v if isinstance(v, (list, tuple)) else [v]
        query = urlencode(args, doseq=True)
        base = url_for(endpoint)
        return base + ('?' + query if query else '')

    app.jinja_env.globals['url_for_with_query'] = url_for_with_query

    app.jinja_env.filters['nl2br'] = nl2br
    app.jinja_env.filters['autolink'] = autolink

    if not app.config.get('DEBUG', False):
        Minify(app=app, html=True, js=True, cssless=True)

        from routes.auth import auth_bp
        from routes.main import main_bp
        from routes.admin import admin_bp
        from routes.pedidos import pedidos_bp
        from routes.packing import packing_bp
        from routes.painel_retirada import painel_retirada_bp 
        from routes.mapa import mapa_bp 

        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(pedidos_bp)
        app.register_blueprint(packing_bp)
        app.register_blueprint(painel_retirada_bp)
        app.register_blueprint(mapa_bp)

        return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)