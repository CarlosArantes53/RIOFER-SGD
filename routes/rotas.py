# routes/rotas.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from decorators import roles_required
from permissions import UserPermissions
from services import rotas_service, mapa_service
from data import frota_repository
import json

rotas_bp = Blueprint('rotas', __name__, url_prefix='/rotas')

@rotas_bp.route('/')
@roles_required(list(UserPermissions.ROTA_ROLES))
def manage_rotas():
    """Página para listar todas as rotas criadas."""
    rotas = rotas_service.get_rotas_com_detalhes()
    return render_template('rotas/manage_rotas.html', rotas=rotas)

@rotas_bp.route('/planejamento')
@roles_required(list(UserPermissions.ROTA_ROLES))
def planejamento_mapa():
    """Página de planejamento de rotas, baseada no mapa."""
    pedidos_disponiveis = mapa_service.get_entregas_para_mapa() # Reutiliza o serviço do mapa
    locations_json = json.dumps([p for p in pedidos_disponiveis if not p['GeoError']])
    
    df_frota = frota_repository.get_frota_data()
    caminhoes_disponiveis = df_frota[df_frota['Status'] == 'Disponível'].to_dict('records')
    
    # Adicionar peso a cada pedido para o frontend
    df_picking = rotas_service.get_pedidos_disponiveis()
    pesos_map = df_picking.set_index('AbsEntry')['PesoTotal'].to_dict()
    for pedido in pedidos_disponiveis:
        pedido['Peso'] = pesos_map.get(pedido['AbsEntry'], 0)
        
    return render_template(
        'rotas/planejamento_mapa.html',
        pedidos=pedidos_disponiveis,
        locations_json=locations_json,
        caminhoes=caminhoes_disponiveis
    )

@rotas_bp.route('/api/criar', methods=['POST'])
@roles_required(list(UserPermissions.ROTA_ROLES))
def api_create_rota():
    """API endpoint para criar uma nova rota."""
    data = request.json
    
    if not all(k in data for k in ['pedidos', 'id_caminhao', 'data_rota', 'tipo']):
        return jsonify({'status': 'error', 'message': 'Dados incompletos.'}), 400

    if not data['pedidos']:
        return jsonify({'status': 'error', 'message': 'Selecione ao menos um pedido.'}), 400
        
    success, new_id = rotas_service.create_nova_rota(data)
    
    if success:
        flash(f"Rota #{new_id} criada com sucesso!", 'success')
        return jsonify({'status': 'success', 'id_rota': new_id})
    else:
        return jsonify({'status': 'error', 'message': 'Falha ao salvar a rota.'}), 500