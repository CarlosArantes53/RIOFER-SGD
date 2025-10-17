# routes/frota.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from decorators import roles_required
from permissions import UserPermissions
from data import frota_repository
from models.user import get_all_users
import pandas as pd

frota_bp = Blueprint('frota', __name__, url_prefix='/frota')

@frota_bp.route('/')
@roles_required(list(UserPermissions.FROTA_ROLES))
def manage_frota():
    """Exibe a lista de veículos da frota."""
    veiculos_df = frota_repository.get_frota_data()
    veiculos = veiculos_df.to_dict(orient='records')
    return render_template('frota/manage_frota.html', veiculos=veiculos)

def get_motoristas_disponiveis(token, id_veiculo_atual=None):
    """Busca usuários com a role 'motorista'."""
    all_users = get_all_users(token)
    motoristas = {
        uid: data for uid, data in all_users.items()
        if 'motorista' in data.get('roles', {})
    }
    
    df_frota = frota_repository.get_frota_data()
    
    # Se estiver editando, o motorista atual do veículo é sempre uma opção válida
    if id_veiculo_atual:
        veiculo_atual = df_frota[df_frota['ID_Caminhao'] == id_veiculo_atual]
        if not veiculo_atual.empty:
            motorista_atual_id = veiculo_atual.iloc[0]['ID_Motorista']
            # O motorista atual pode ser selecionado
            motoristas_alocados = set(df_frota[df_frota['ID_Caminhao'] != id_veiculo_atual]['ID_Motorista'])
        else:
             motoristas_alocados = set(df_frota['ID_Motorista'])
    else:
        motoristas_alocados = set(df_frota['ID_Motorista'])

    motoristas_disponiveis = {
        uid: data for uid, data in motoristas.items()
        if uid not in motoristas_alocados or (id_veiculo_atual and uid == motorista_atual_id)
    }
    
    return motoristas_disponiveis

@frota_bp.route('/novo', methods=['GET', 'POST'])
@roles_required(list(UserPermissions.FROTA_ROLES))
def create_veiculo():
    """Página para criar um novo veículo."""
    token = session['user']['idToken']
    motoristas = get_motoristas_disponiveis(token)

    if request.method == 'POST':
        motorista_id = request.form.get('motorista')
        motorista_info = motoristas.get(motorista_id, {})
        
        novo_veiculo = {
            'Placa': request.form.get('placa').upper(),
            'Descricao': request.form.get('descricao'),
            'ID_Motorista': motorista_id,
            'Nome_Motorista': motorista_info.get('nome_sap', motorista_info.get('email', '')),
            'Capacidade_KG': float(request.form.get('capacidade_kg')),
            'Tolerancia': float(request.form.get('tolerancia')),
            'Status': 'Disponível'
        }
        
        if frota_repository.add_veiculo(novo_veiculo):
            flash(f"Veículo {novo_veiculo['Placa']} adicionado com sucesso!", 'success')
            return redirect(url_for('frota.manage_frota'))
        else:
            flash("Erro ao adicionar o veículo.", 'danger')

    return render_template('frota/frota_form.html', action='create', motoristas=motoristas, veiculo={})

@frota_bp.route('/editar/<veiculo_id>', methods=['GET', 'POST'])
@roles_required(list(UserPermissions.FROTA_ROLES))
def edit_veiculo(veiculo_id):
    """Página para editar um veículo existente."""
    df_frota = frota_repository.get_frota_data()
    veiculo = df_frota[df_frota['ID_Caminhao'] == veiculo_id].to_dict('records')
    
    if not veiculo:
        flash("Veículo não encontrado.", 'danger')
        return redirect(url_for('frota.manage_frota'))
    
    veiculo = veiculo[0]
    token = session['user']['idToken']
    motoristas = get_motoristas_disponiveis(token, veiculo_id)

    if request.method == 'POST':
        motorista_id = request.form.get('motorista')
        motorista_info = motoristas.get(motorista_id, {})
        
        update_data = {
            'Placa': request.form.get('placa').upper(),
            'Descricao': request.form.get('descricao'),
            'ID_Motorista': motorista_id,
            'Nome_Motorista': motorista_info.get('nome_sap', motorista_info.get('email', '')),
            'Capacidade_KG': float(request.form.get('capacidade_kg')),
            'Tolerancia': float(request.form.get('tolerancia'))
        }
        
        success, message = frota_repository.update_veiculo(veiculo_id, update_data)
        
        if success:
            flash(f"Veículo {update_data['Placa']} atualizado com sucesso!", 'success')
            return redirect(url_for('frota.manage_frota'))
        else:
            flash(f"Erro ao atualizar: {message}", 'danger')

    return render_template('frota/frota_form.html', action='edit', veiculo=veiculo, motoristas=motoristas)

@frota_bp.route('/deletar/<veiculo_id>', methods=['POST'])
@roles_required(list(UserPermissions.FROTA_ROLES))
def delete_veiculo(veiculo_id):
    """Rota para deletar um veículo."""
    if frota_repository.delete_veiculo(veiculo_id):
        flash("Veículo removido com sucesso.", 'success')
    else:
        flash("Erro ao remover o veículo.", 'danger')
    return redirect(url_for('frota.manage_frota'))