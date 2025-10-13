from config import db, auth

def get_user_data(uid, token):
    try:
        user_data = db.child("users").child(uid).get(token=token)
        return user_data.val()
    except Exception as e:
        print(f"Erro ao buscar dados do usuário {uid}: {e}")
        return None

def get_all_users(token):
    try:
        users = db.child("users").get(token=token)
        return {user.key(): user.val() for user in users.each()} if users.val() else {}
    except Exception as e:
        print(f"Erro ao buscar todos os usuários: {e}")
        return {}

def create_user_with_data(email, password, roles, admin_token, **kwargs):
    try:
        user = auth.create_user_with_email_and_password(email, password)
        uid = user['localId']
        
        roles_map = {role: True for role in roles}
        
        user_data = {
            "email": email, 
            "roles": roles_map,
            "codigo_vendedor": kwargs.get("codigo_vendedor", ""),
            "nome_vendedor": kwargs.get("nome_vendedor", ""),
            "codigo_sap": kwargs.get("codigo_sap", ""),
            "nome_sap": kwargs.get("nome_sap", "")
        }
        db.child("users").child(uid).set(user_data, token=admin_token)
        return user
    except Exception as e:
        raise e

def create_simple_user(email, password, nome, role, admin_token):
    try:
        if role not in ['separador', 'conferente', 'motorista']:
            raise ValueError("O setor deve ser 'separador', 'conferente' ou 'motorista'.")

        user = auth.create_user_with_email_and_password(email, password)
        uid = user['localId']

        user_data = {
            "email": email,
            "roles": {role: True},
            "nome_sap": nome,
            "codigo_vendedor": "",
            "nome_vendedor": "",
            "codigo_sap": ""
        }
        db.child("users").child(uid).set(user_data, token=admin_token)
        return user
    except Exception as e:
        raise e

def deactivate_user(uid, token):
    """Inativa um usuário definindo seu setor como 'default'."""
    try:
        # O setor 'default' não possui permissões.
        data = {'roles': {'default': True}}
        db.child("users").child(uid).update(data, token=token)
        return True
    except Exception as e:
        print(f"Erro ao inativar o usuário {uid}: {e}")
        return False

def update_user_data(uid, data, token):
    try:
        if 'roles' in data:
            data['roles'] = {role: True for role in data['roles']}
            
        db.child("users").child(uid).update(data, token=token)
        return True
    except Exception as e:
        print(f"Erro ao atualizar os dados do usuário {uid}: {e}")
        return False