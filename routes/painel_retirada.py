# routes/painel_retirada.py
import os
import pandas as pd
from flask import Blueprint, render_template, jsonify

painel_retirada_bp = Blueprint('painel_retirada', __name__)

def get_picking_data():
    """Lê os dados de picking do arquivo parquet."""
    parquet_path = os.getenv('RIOFER_PICKING_SGD')
    if not parquet_path or not os.path.exists(parquet_path):
        return pd.DataFrame()
    return pd.read_parquet(parquet_path)

def get_separacao_data():
    """Lê os dados de separação do arquivo parquet."""
    path = os.getenv('RIOFER_SEPARACAO_SGD', 'separacao.parquet')
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)

def get_pacotes_data():
    """Lê os dados dos pacotes do arquivo parquet."""
    path = os.getenv('RIOFER_PACOTES_SGD', 'pacotes.parquet')
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)

def get_packing_data():
    """Lê os dados de packing finalizado do arquivo parquet."""
    path = os.getenv('RIOFER_PACKING_SGD', 'packing.parquet')
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)

@painel_retirada_bp.route('/painel-retirada')
def painel_retirada_view():
    """Renderiza a página inicial do painel."""
    return render_template('painel_retirada.html')

@painel_retirada_bp.route('/api/painel-retirada-data')
def painel_retirada_data():
    """Fornece os dados para o painel em formato JSON."""
    df_picking = get_picking_data()
    df_separacao = get_separacao_data()
    df_pacotes = get_pacotes_data()
    df_packing = get_packing_data()

    if df_picking.empty:
        return jsonify({"pedidos": [], "error": "Arquivo de picking não encontrado."})

    # Filtra pedidos do tipo "Retirada"
    df_retirada = df_picking[df_picking['U_TU_QuemEntrega'] == '02'].copy()

    # Cria conjuntos de IDs para consulta rápida de status
    packing_finalizado_ids = set(df_packing['AbsEntry'].unique())
    separacao_iniciada_ids = set(df_separacao['AbsEntry'].unique())
    separacao_finalizada_ids = set(df_separacao[df_separacao['EndTime'].notna() & (df_separacao['EndTime'] != '')]['AbsEntry'].unique())

    pedidos_status = []
    pedidos_agrupados = df_retirada.groupby('AbsEntry')

    for abs_entry, group in pedidos_agrupados:
        # O pedido só sai da tela após o packing finalizado
        if abs_entry in packing_finalizado_ids:
            continue

        card_name = group['CardName'].iloc[0]
        status = 'Pendente'
        percentual = 0
        localizacao_retirada = ""

        if abs_entry in separacao_finalizada_ids:
            status = 'Aguardando Retirada'
            percentual = 100
            # Busca os locais de retirada nos pacotes criados
            if not df_pacotes.empty:
                locais = df_pacotes[df_pacotes['AbsEntry'] == abs_entry]['Location'].unique()
                localizacao_retirada = ", ".join(filter(None, locais))

        elif abs_entry in separacao_iniciada_ids:
            status = 'Em Separação'
            # Calcula o progresso com base nos itens
            total_qtd_pedido = group['RelQtty'].sum()
            if not df_pacotes.empty:
                qtd_separada = df_pacotes[df_pacotes['AbsEntry'] == abs_entry]['Quantity'].sum()
                if total_qtd_pedido > 0:
                    percentual = (qtd_separada / total_qtd_pedido) * 100
            
        # --- INÍCIO DA CORREÇÃO ---
        pedidos_status.append({
            'AbsEntry': int(abs_entry), # Convertido para int
            'CardName': card_name,
            'Status': status,
            'Percentual': int(round(percentual)), # Convertido para int
            'Localizacao': localizacao_retirada
        })
        # --- FIM DA CORREÇÃO ---
            
    # Ordena os pedidos por nome do cliente
    pedidos_status.sort(key=lambda x: x['CardName'])

    return jsonify({"pedidos": pedidos_status})