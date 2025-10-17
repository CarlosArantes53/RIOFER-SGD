# permissions.py

from flask import session

class UserPermissions:
    ENTREGA_ROLES = {'admin', 'expedicao', 'motorista', 'conferente', 'separador'}
    RETIRA_ROLES = {'admin', 'expedicao', 'retira'}
    EXPEDICA_GERENCIAL_ROLES = {'admin', 'expedicao'}
    FROTA_ROLES = {'admin', 'expedicao'}
    ROTA_ROLES = {'admin', 'expedicao'}
    PEDIDOS_VIEW_ROLES = ENTREGA_ROLES.union(RETIRA_ROLES)
    PACKING_ROLES = {'admin', 'expedicao', 'conferente'} 

    def __init__(self, user_session):
        self.roles = set(user_session.get('roles', {}).keys()) if user_session else set()

    def can_view_pedidos(self):
        return not self.roles.isdisjoint(self.PEDIDOS_VIEW_ROLES)
    
    def can_manage_frota(self):
        return not self.roles.isdisjoint(self.FROTA_ROLES)
    
    def can_manage_rotas(self): # <-- ADICIONE ESTA FUNÇÃO
        return not self.roles.isdisjoint(self.ROTA_ROLES)
    
    def can_view_entregas(self):
        return not self.roles.isdisjoint(self.ENTREGA_ROLES)

    def can_view_retira(self):
        return not self.roles.isdisjoint(self.RETIRA_ROLES)

    def can_view_gerencial(self):
        return not self.roles.isdisjoint(self.EXPEDICA_GERENCIAL_ROLES)

    def can_view_packing(self):
        return not self.roles.isdisjoint(self.PACKING_ROLES)

def get_current_user_permissions():
    user = session.get('user')
    return UserPermissions(user)