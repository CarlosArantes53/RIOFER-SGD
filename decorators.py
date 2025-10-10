from functools import wraps
from flask import session, redirect, url_for, flash, abort
from requests import request
from permissions import UserPermissions
from data import pedidos_repository

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

def order_type_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Você precisa estar logado para ver esta página.', 'warning')
            return redirect(url_for('auth.login'))

        abs_entry = kwargs.get('abs_entry')
        if not abs_entry:
            return abort(400, description="Número do pedido (AbsEntry) não encontrado na requisição.")

        df_picking = pedidos_repository.get_picking_data()
        pedido_info = df_picking[df_picking['AbsEntry'] == abs_entry]

        if pedido_info.empty:
            return abort(404, description="Pedido não encontrado.")

        tipo_entrega = pedido_info.iloc[0]['U_TU_QuemEntrega']
        perms = UserPermissions(session.get('user'))

        is_retira = (tipo_entrega == '02')
        
        if is_retira and not perms.can_view_retira():
            flash('Você não tem permissão para acessar pedidos do tipo "Cliente Retira".', 'danger')
            return redirect(request.referrer or url_for('pedidos.listar_pedidos'))
            
        if not is_retira and not perms.can_view_entregas():
            flash('Você não tem permissão para acessar pedidos do tipo "Entrega".', 'danger')
            return redirect(request.referrer or url_for('pedidos.listar_pedidos'))

        return f(*args, **kwargs)
    return decorated_function