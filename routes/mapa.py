# routes/mapa.py

from flask import Blueprint, render_template, session, jsonify, request
from decorators import roles_required
from services import mapa_service
from data import geoloc_repository
from permissions import UserPermissions
import json

mapa_bp = Blueprint('mapa', __name__)

@mapa_bp.route('/mapa-entregas')
@roles_required(list(UserPermissions.ENTREGA_ROLES))
def mapa_entregas():
    pedidos_para_mapa = mapa_service.get_entregas_para_mapa()
    locations_json = json.dumps([p for p in pedidos_para_mapa if not p['GeoError']])

    cidades = sorted({p.get('Cidade') for p in pedidos_para_mapa if p.get('Cidade')})
    cities_json = json.dumps(cidades)
    
    regioes = mapa_service.get_regioes()
    regioes_json = json.dumps(regioes)

    return render_template(
        'mapa_entregas/mapa_entregas.html',
        pedidos=pedidos_para_mapa,
        locations_json=locations_json,
        cities_json=cities_json,
        regioes_json=regioes_json,
        cidades=cidades  # <-- LINHA ADICIONADA
    )


@mapa_bp.route('/mapa/find_geolocation/<int:abs_entry>', methods=['POST'])
@roles_required(list(UserPermissions.ENTREGA_ROLES))
def find_geolocation(abs_entry):
    result = mapa_service.find_and_save_geolocation(abs_entry)
    return jsonify(result)

@mapa_bp.route('/mapa/save_geolocation', methods=['POST'])
@roles_required(list(UserPermissions.ENTREGA_ROLES))
def save_geolocation():
    data = request.json
    abs_entry = data.get('abs_entry')
    lat = data.get('lat')
    lon = data.get('lon')

    if not all([abs_entry, lat, lon]):
        return jsonify({'status': 'error', 'message': 'Dados incompletos.'}), 400

    try:
        abs_entry = int(abs_entry)
        float(lat)
        float(lon)
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Valores inválidos.'}), 400

    if geoloc_repository.update_geolocation(abs_entry, lat, lon):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Falha ao salvar.'}), 500

@mapa_bp.route('/mapa/save_regioes', methods=['POST'])
@roles_required(list(UserPermissions.ENTREGA_ROLES))
def save_regioes():
    regioes = request.json.get('regioes', [])
    if mapa_service.save_regioes(regioes):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Falha ao salvar as regiões.'}), 500