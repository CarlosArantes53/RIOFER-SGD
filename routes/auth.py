from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from config import auth
from models.user import get_user_data
from decorators import login_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('main.home'))

    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            user_auth_data = auth.sign_in_with_email_and_password(email, password)
            uid = user_auth_data['localId']
            id_token = user_auth_data['idToken']
            
            user_db_data = get_user_data(uid, id_token)
            
            session['user'] = {
                'uid': uid,
                'email': user_auth_data['email'],
                'idToken': id_token,
                'roles': user_db_data.get('roles', {}) if user_db_data else {}
            }
            return redirect(url_for('main.home'))
        except Exception as e:
            error = 'Falha na autenticação. Verifique suas credenciais.'
            
    return render_template('login.html', error=error)

@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('user', None)
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('auth.login'))