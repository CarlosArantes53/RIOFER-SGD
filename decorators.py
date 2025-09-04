from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Você precisa estar logado para ver esta página.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash('Você precisa estar logado para ver esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            user_roles = session.get('user', {}).get('roles', {})
            if not any(role in user_roles for role in allowed_roles):
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('main.home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return roles_required(['admin'])(f)