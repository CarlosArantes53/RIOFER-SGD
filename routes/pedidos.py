import os
import pandas as pd
from flask import Blueprint, render_template, abort, session, redirect, url_for, flash, request
from decorators import login_required
from datetime import datetime

pedidos_bp = Blueprint('pedidos', __name__)

PACOTES_PARQUET_PATH = os.getenv('RIOFER_PACOTES_SGD', 'pacotes.parquet')
SEPARACAO_PARQUET_PATH = os.getenv('RIOFER_SEPARACAO_SGD', 'separacao.parquet')


def get_pedidos_data():
    parquet_path = os.getenv('RIOFER_PICKING_SGD')
    if not parquet_path or not os.path.exists(parquet_path):
        return None
    try:
        df = pd.read_parquet(parquet_path)
        return df
    except Exception as e:
        print(f"Erro ao ler o arquivo parquet: {e}")
        return None

@pedidos_bp.route('/pedidos')
@login_required
def listar_pedidos():
    df = get_pedidos_data()
    if df is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    pedidos_agrupados = df.groupby('AbsEntry').first().reset_index()
    return render_template('pedidos.html', pedidos=pedidos_agrupados.to_dict(orient='records'))

@pedidos_bp.route('/picking/<int:abs_entry>')
@login_required
def visualizar_picking(abs_entry):
    df = get_pedidos_data()
    if df is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    picking_items = df[df['AbsEntry'] == abs_entry]
    if picking_items.empty:
        abort(404, description="Picking não encontrado.")

    return render_template('picking_details.html', items=picking_items.to_dict(orient='records'), abs_entry=abs_entry)


@pedidos_bp.route('/picking/iniciar/<int:abs_entry>')
@login_required
def iniciar_separacao(abs_entry):
    if 'picking_in_progress' in session:
        flash('Você já tem uma separação em andamento. Finalize-a antes de iniciar uma nova.', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))

    session['picking_in_progress'] = {
        'abs_entry': abs_entry,
        'start_time': datetime.now().isoformat(),
        'pacotes': []
    }
    return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry))


@pedidos_bp.route('/picking/separar/<int:abs_entry>', methods=['GET', 'POST'])
@login_required
def separar_picking(abs_entry):
    if 'picking_in_progress' not in session or session['picking_in_progress']['abs_entry'] != abs_entry:
        flash('Nenhuma separação em andamento para este pedido. Inicie a separação primeiro.', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))

    df = get_pedidos_data()
    if df is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    picking_items = df[df['AbsEntry'] == abs_entry]
    if picking_items.empty:
        abort(404, description="Picking não encontrado.")

    if request.method == 'POST':
        peso_pacote = request.form.get('peso_pacote')
        itens_selecionados = request.form.getlist('itens_pacote')
        
        novo_pacote = {
            'id': len(session['picking_in_progress']['pacotes']) + 1,
            'peso': peso_pacote,
            'itens': []
        }

        for item_selecionado in itens_selecionados:
            item_code, item_name = item_selecionado.split('|')
            quantidade = request.form.get(f'quantidade_{item_code}')
            if quantidade and float(quantidade) > 0:
                novo_pacote['itens'].append({
                    'ItemCode': item_code,
                    'ItemName': item_name,
                    'Quantity': float(quantidade)
                })
        
        session['picking_in_progress']['pacotes'].append(novo_pacote)
        session.modified = True
        flash('Pacote criado com sucesso!', 'success')
        return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry))

    return render_template('separacao_picking.html', 
                           items=picking_items.to_dict(orient='records'), 
                           abs_entry=abs_entry,
                           pacotes=session['picking_in_progress']['pacotes'])


@pedidos_bp.route('/picking/finalizar/<int:abs_entry>')
@login_required
def finalizar_separacao(abs_entry):
    if 'picking_in_progress' not in session or session['picking_in_progress']['abs_entry'] != abs_entry:
        flash('Nenhuma separação em andamento para este pedido.', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))

    # Validação da quantidade total de itens
    df_original = get_pedidos_data()
    itens_originais = df_original[df_original['AbsEntry'] == abs_entry]
    
    quantidades_separadas = {}
    for pacote in session['picking_in_progress']['pacotes']:
        for item in pacote['itens']:
            item_code = item['ItemCode']
            quantidades_separadas[item_code] = quantidades_separadas.get(item_code, 0) + item['Quantity']
            
    for _, item_original in itens_originais.iterrows():
        item_code = item_original['ItemCode']
        if item_original['RelQtty'] != quantidades_separadas.get(item_code, 0):
            flash(f'A quantidade do item {item_code} não corresponde à do pedido original.', 'danger')
            return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry))

    # Salvar dados nos arquivos Parquet
    # 1. Pacotes
    pacotes_data = []
    for pacote in session['picking_in_progress']['pacotes']:
        for item in pacote['itens']:
            pacotes_data.append({
                'AbsEntry': abs_entry,
                'PackageID': pacote['id'],
                'Weight': pacote['peso'],
                'ItemCode': item['ItemCode'],
                'Quantity': item['Quantity']
            })
    
    df_pacotes = pd.DataFrame(pacotes_data)
    if os.path.exists(PACOTES_PARQUET_PATH):
        df_existente = pd.read_parquet(PACOTES_PARQUET_PATH)
        df_pacotes = pd.concat([df_existente, df_pacotes])
    df_pacotes.to_parquet(PACOTES_PARQUET_PATH, index=False)

    # 2. Informações da separação
    separacao_data = {
        'AbsEntry': abs_entry,
        'User': session['user']['email'],
        'StartTime': session['picking_in_progress']['start_time'],
        'EndTime': datetime.now().isoformat()
    }
    
    df_separacao = pd.DataFrame([separacao_data])
    if os.path.exists(SEPARACAO_PARQUET_PATH):
        df_existente = pd.read_parquet(SEPARACAO_PARQUET_PATH)
        df_separacao = pd.concat([df_existente, df_separacao])
    df_separacao.to_parquet(SEPARACAO_PARQUET_PATH, index=False)

    session.pop('picking_in_progress', None)
    flash('Separação finalizada e salva com sucesso!', 'success')
    return redirect(url_for('pedidos.listar_pedidos'))