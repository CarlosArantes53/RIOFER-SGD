# permissions.py

from flask import session

class UserPermissions:
    """
    Uma classe para centralizar a verificação de permissões do usuário.
    """
    
    # Define os grupos de roles que têm acesso a cada recurso.
    # Isso torna a adição ou remoção de um setor uma tarefa simples.
    ENTREGA_ROLES = {'admin', 'expedicao', 'motorista', 'conferente', 'separador'}
    RETIRA_ROLES = {'admin', 'expedicao', 'retira'}
    GERENCIAL_ROLES = {'admin', 'expedicao'}
    PEDIDOS_VIEW_ROLES = ENTREGA_ROLES.union(RETIRA_ROLES)

    def __init__(self, user_session):
        self.roles = set(user_session.get('roles', {}).keys()) if user_session else set()

    def can_view_pedidos(self):
        """Verifica se o usuário pode ver a página de pedidos."""
        return not self.roles.isdisjoint(self.PEDIDOS_VIEW_ROLES)

    def can_view_entregas(self):
        """Verifica se o usuário pode ver a aba/dados de Entregas."""
        return not self.roles.isdisjoint(self.ENTREGA_ROLES)

    def can_view_retira(self):
        """Verifica se o usuário pode ver a aba/dados de Cliente Retira."""
        return not self.roles.isdisjoint(self.RETIRA_ROLES)

    def can_view_gerencial(self):
        """Verifica se o usuário pode ver a aba Gerencial."""
        return not self.roles.isdisjoint(self.GERENCIAL_ROLES)

def get_current_user_permissions():
    """Função auxiliar para obter as permissões do usuário logado."""
    user = session.get('user')
    return UserPermissions(user)