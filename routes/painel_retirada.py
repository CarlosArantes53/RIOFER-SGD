import os
import pandas as pd
from flask import Blueprint, render_template, jsonify
from decorators import roles_required
from permissions import UserPermissions

painel_retirada_bp = Blueprint('painel_retirada', __name__)

def get_picking_data():
    parquet_path = os.getenv('RIOFER_PICKING_SGD')
    if not parquet_path or not os.path.exists(parquet_path):
        return pd.DataFrame()
    return pd.read_parquet(parquet_path)

def get_separacao_data():
    path = os.getenv('RIOFER_SEPARACAO_SGD', 'separacao.parquet')
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)

def get_pacotes_data():
    path = os.getenv('RIOFER_PACOTES_SGD', 'pacotes.parquet')
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)

def get_packing_data():
    path = os.getenv('RIOFER_PACKING_SGD', 'packing.parquet')
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)

@painel_retirada_bp.route('/painel-retirada')
@roles_required(list(UserPermissions.RETIRA_ROLES))
def painel_retirada_view():
    return render_template('painel_retirada.html')

@painel_retirada_bp.route('/api/painel-retirada-data')
@roles_required(list(UserPermissions.RETIRA_ROLES))
def painel_retirada_data():
    df_picking = get_picking_data()
    df_separacao = get_separacao_data()
    df_pacotes = get_pacotes_data()
    df_packing = get_packing_data()

    if df_picking.empty:
        return jsonify({"pedidos": [], "error": "Arquivo de picking não encontrado."})

    df_retirada = df_picking[df_picking['U_TU_QuemEntrega'] == '02'].copy()

    packing_finalizado_ids = set(df_packing['AbsEntry'].unique())
    separacao_iniciada_ids = set(df_separacao['AbsEntry'].unique())
    separacao_finalizada_ids = set(df_separacao[df_separacao['EndTime'].notna() & (df_separacao['EndTime'] != '')]['AbsEntry'].unique())

    pedidos_status = []
    pedidos_agrupados = df_retirada.groupby('AbsEntry')

    for abs_entry, group in pedidos_agrupados:
        if abs_entry in packing_finalizado_ids:
            continue

        card_name = group['CardName'].iloc[0]
        status = 'Pendente'
        percentual = 0
        localizacao_retirada = ""

        if abs_entry in separacao_finalizada_ids:
            status = 'Aguardando Retirada'
            percentual = 100
            if not df_pacotes.empty:
                locais = df_pacotes[df_pacotes['AbsEntry'] == abs_entry]['Location'].unique()
                localizacao_retirada = ", ".join(filter(None, locais))

        elif abs_entry in separacao_iniciada_ids:
            status = 'Em Separação'
            total_qtd_pedido = group['RelQtty'].sum()
            if not df_pacotes.empty:
                qtd_separada = df_pacotes[df_pacotes['AbsEntry'] == abs_entry]['Quantity'].sum()
                if total_qtd_pedido > 0:
                    percentual = (qtd_separada / total_qtd_pedido) * 100
            
        pedidos_status.append({
            'AbsEntry': int(abs_entry),
            'CardName': card_name,
            'Status': status,
            'Percentual': int(round(percentual)),
            'Localizacao': localizacao_retirada
        })
    pedidos_status.sort(key=lambda x: x['CardName'])

    return jsonify({"pedidos": pedidos_status})