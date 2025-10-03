# routes/packing.py

import os
import pandas as pd
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from decorators import login_required
from datetime import datetime

packing_bp = Blueprint('packing', __name__)

PACKING_PARQUET_PATH = os.getenv('RIOFER_PACKING_SGD', 'packing.parquet')
PACOTES_PARQUET_PATH = os.getenv('RIOFER_PACOTES_SGD', 'pacotes.parquet')
SEPARACAO_PARQUET_PATH = os.getenv('RIOFER_SEPARACAO_SGD', 'separacao.parquet')

def get_pacotes_data():
    if not os.path.exists(PACOTES_PARQUET_PATH):
        return pd.DataFrame()
    return pd.read_parquet(PACOTES_PARQUET_PATH)

def get_packing_data():
    if not os.path.exists(PACKING_PARQUET_PATH):
        return pd.DataFrame(columns=['AbsEntry', 'Localizacao'])
    return pd.read_parquet(PACKING_PARQUET_PATH)

def get_separacao_data():
    if not os.path.exists(SEPARACAO_PARQUET_PATH):
        return pd.DataFrame()
    return pd.read_parquet(SEPARACAO_PARQUET_PATH)


@packing_bp.route('/packing')
@login_required
def listar_packing():
    df_pacotes = get_pacotes_data()
    df_packing_finalizado = get_packing_data()
    df_separacao = get_separacao_data()

    pedidos_para_packing = pd.DataFrame()
    if not df_pacotes.empty:
        pedidos_para_packing = df_pacotes.groupby(['AbsEntry', 'Localizacao']).first().reset_index()
    
    # Cria um conjunto de chaves (pedido, localização) para os itens já finalizados
    finalizados_keys = set()
    if not df_packing_finalizado.empty:
        finalizados_keys = set(zip(df_packing_finalizado['AbsEntry'], df_packing_finalizado['Localizacao']))

    # Cria um conjunto de chaves para os pickings incompletos
    incompletos_keys = set()
    if not df_separacao.empty:
        df_incompleto = df_separacao[df_separacao['DiscrepancyLog'].notna() & (df_separacao['DiscrepancyLog'] != '')]
        if not df_incompleto.empty:
            incompletos_keys = set(zip(df_incompleto['AbsEntry'], df_incompleto['Localizacao']))

    pedidos_com_status = []
    for _, row in pedidos_para_packing.iterrows():
        abs_entry = row['AbsEntry']
        localizacao = row['Localizacao']

        if (abs_entry, localizacao) in incompletos_keys:
            continue

        pedido_dict = row.to_dict()
        if (abs_entry, localizacao) in finalizados_keys:
            pedido_dict['Status'] = 'Finalizado'
        else:
            pedido_dict['Status'] = 'Aguardando Início'
        pedidos_com_status.append(pedido_dict)

    return render_template('packing_status.html', pedidos=pedidos_com_status)

# A função iniciar_packing e o resto do arquivo permanecem os mesmos
@packing_bp.route('/packing/iniciar/<int:abs_entry>/<localizacao>', methods=['GET', 'POST'])
@login_required
def iniciar_packing(abs_entry, localizacao):
    df_pacotes = get_pacotes_data()
    pacotes_pedido = df_pacotes[(df_pacotes['AbsEntry'] == abs_entry) & (df_pacotes['Localizacao'] == localizacao)]

    if pacotes_pedido.empty:
        flash('Nenhum pacote encontrado para este pedido e localização.', 'warning')
        return redirect(url_for('packing.listar_packing'))

    pacotes_agrupados = {}
    for _, row in pacotes_pedido.iterrows():
        package_id = row['PackageID']
        if package_id not in pacotes_agrupados:
            pacotes_agrupados[package_id] = {
                'id': package_id,
                'peso_original': float(row['Weight']),
                'itens': []
            }
        pacotes_agrupados[package_id]['itens'].append(row.to_dict())

    if request.method == 'POST':
        anomalias = []
        has_error = False
        
        for package_id, pacote_info in pacotes_agrupados.items():
            peso_conferido_str = request.form.get(f'peso_pacote_{package_id}')
            confirmado = request.form.get(f'confirm_pacote_{package_id}')

            if not confirmado:
                flash(f'O Pacote {package_id} precisa ser confirmado.', 'danger')
                has_error = True
                continue

            try:
                peso_conferido = float(peso_conferido_str)
                peso_original = float(pacote_info['peso_original'])
                tolerancia = 0.05

                diferenca = abs(peso_conferido - peso_original)
                if diferenca > (peso_original * tolerancia):
                    anomalia = f"Divergência de peso no Pacote {package_id}. Registrado: {peso_original:.2f} kg, Conferido: {peso_conferido:.2f} kg."
                    anomalias.append(anomalia)
                    flash(anomalia, 'danger')
                    has_error = True

            except (ValueError, TypeError):
                flash(f'O peso informado para o Pacote {package_id} é inválido.', 'danger')
                has_error = True

        if has_error:
            return render_template('packing_details.html',
                                   pacotes=list(pacotes_agrupados.values()),
                                   abs_entry=abs_entry,
                                   localizacao=localizacao)
        
        df_packing = get_packing_data()
        packing_records = []
        for package_id in pacotes_agrupados.keys():
            packing_records.append({
                'AbsEntry': abs_entry,
                'Localizacao': localizacao,
                'PackageID': package_id,
                'User': session['user']['email'],
                'StartTime': datetime.now().isoformat(),
                'EndTime': datetime.now().isoformat(),
                'Anomalias': "; ".join(anomalias)
            })
        
        nova_conferencia = pd.DataFrame(packing_records)
        df_packing = pd.concat([df_packing, nova_conferencia], ignore_index=True)
        df_packing.to_parquet(PACKING_PARQUET_PATH, index=False)
        
        flash('Packing da localização finalizado com sucesso!', 'success')
        return redirect(url_for('packing.listar_packing'))

    return render_template('packing_details.html',
                           pacotes=list(pacotes_agrupados.values()),
                           abs_entry=abs_entry,
                           localizacao=localizacao)