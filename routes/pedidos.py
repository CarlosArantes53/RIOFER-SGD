import os
import pandas as pd
from flask import Blueprint, render_template, abort, session, redirect, url_for, flash, request
from decorators import login_required
from datetime import datetime

pedidos_bp = Blueprint('pedidos', __name__)

PACOTES_PARQUET_PATH = os.getenv('RIOFER_PACOTES_SGD', 'pacotes.parquet')
SEPARACAO_PARQUET_PATH = os.getenv('RIOFER_SEPARACAO_SGD', 'separacao.parquet')
PACKING_PARQUET_PATH = os.getenv('RIOFER_PACKING_SGD', 'packing.parquet')


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

def get_separacao_data():
    if not os.path.exists(SEPARACAO_PARQUET_PATH):
        return pd.DataFrame(columns=['AbsEntry', 'Localizacao', 'User', 'StartTime', 'EndTime'])
    try:
        df = pd.read_parquet(SEPARACAO_PARQUET_PATH)
        if 'Localizacao' not in df.columns:
            df['Localizacao'] = ''
        return df
    except Exception as e:
        print(f"Erro ao ler o arquivo de separação parquet: {e}")
        return pd.DataFrame(columns=['AbsEntry', 'Localizacao', 'User', 'StartTime', 'EndTime'])


def get_packing_data():
    """Lê o arquivo parquet de packing."""
    if not os.path.exists(PACKING_PARQUET_PATH):
        return pd.DataFrame(columns=['AbsEntry', 'Localizacao'])
    try:
        return pd.read_parquet(PACKING_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de packing parquet: {e}")
        return pd.DataFrame(columns=['AbsEntry', 'Localizacao'])


@pedidos_bp.route('/pedidos')
@login_required
def listar_pedidos():
    df_picking = get_pedidos_data()
    if df_picking is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    df_separacao = get_separacao_data()
    df_packing = get_packing_data()

    pedidos_agrupados = df_picking.groupby(['AbsEntry', 'Localizacao']).first().reset_index()

    packing_finalizado_keys = set()
    if not df_packing.empty:
        packing_finalizado_keys = set(zip(df_packing['AbsEntry'], df_packing['Localizacao']))

    pedidos_com_status = []
    for index, row in pedidos_agrupados.iterrows():
        separacao = df_separacao[(df_separacao['AbsEntry'] == row['AbsEntry']) & (df_separacao['Localizacao'] == row['Localizacao'])]
        status = 'Pendente'
        user = None
        
        if not separacao.empty:
            separacao_info = separacao.iloc[0]
            if pd.isna(separacao_info['EndTime']) or separacao_info['EndTime'] is None or separacao_info['EndTime'] == '':
                status = f"Em separação por {separacao_info['User']}"
                user = separacao_info['User']
            else:
                if (row['AbsEntry'], row['Localizacao']) in packing_finalizado_keys:
                    status = 'Packing Finalizado'
                else:
                    status = 'Aguardando Packing'
        
        row_dict = row.to_dict()
        row_dict['Status'] = status
        row_dict['UserInSeparation'] = user
        pedidos_com_status.append(row_dict)

    return render_template('pedidos.html', pedidos=pedidos_com_status)

@pedidos_bp.route('/picking/<int:abs_entry>/<localizacao>')
@login_required
def visualizar_picking(abs_entry, localizacao):
    df = get_pedidos_data()
    if df is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    picking_items = df[(df['AbsEntry'] == abs_entry) & (df['Localizacao'] == localizacao)]
    if picking_items.empty:
        abort(404, description="Picking não encontrado.")

    return render_template('picking_details.html', items=picking_items.to_dict(orient='records'), abs_entry=abs_entry, localizacao=localizacao)


@pedidos_bp.route('/picking/iniciar/<int:abs_entry>/<localizacao>')
@login_required
def iniciar_separacao(abs_entry, localizacao):
    df_separacao = get_separacao_data()
    separacao_existente = df_separacao[(df_separacao['AbsEntry'] == abs_entry) & (df_separacao['Localizacao'] == localizacao)]

    if not separacao_existente.empty:
        separacao_info = separacao_existente.iloc[0]
        if (pd.isna(separacao_info['EndTime']) or separacao_info['EndTime'] == '') and separacao_info['User'] != session['user']['email']:
            flash('Este picking já está em separação por outro usuário.', 'danger')
            return redirect(url_for('pedidos.listar_pedidos'))

    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session:
        session['pickings_in_progress'] = {}

    if picking_key not in session['pickings_in_progress']:
        session['pickings_in_progress'][picking_key] = {
            'abs_entry': abs_entry,
            'localizacao': localizacao,
            'start_time': datetime.now().isoformat(),
            'pacotes': []
        }
        session.modified = True

        if separacao_existente.empty:
            nova_separacao = pd.DataFrame([{
                'AbsEntry': abs_entry,
                'Localizacao': localizacao,
                'User': session['user']['email'],
                'StartTime': session['pickings_in_progress'][picking_key]['start_time'],
                'EndTime': None
            }])
            df_separacao = pd.concat([df_separacao, nova_separacao], ignore_index=True)
            df_separacao.to_parquet(SEPARACAO_PARQUET_PATH, index=False)

    return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))


@pedidos_bp.route('/picking/separar/<int:abs_entry>/<localizacao>', methods=['GET', 'POST'])
@login_required
def separar_picking(abs_entry, localizacao):
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session or picking_key not in session['pickings_in_progress']:
        flash('Nenhuma separação em andamento para este picking. Inicie a separação primeiro.', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))

    df = get_pedidos_data()
    if df is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    picking_items = df[(df['AbsEntry'] == abs_entry) & (df['Localizacao'] == localizacao)]
    if picking_items.empty:
        abort(404, description="Picking não encontrado.")

    quantidades_separadas = {}
    for pacote in session['pickings_in_progress'][picking_key]['pacotes']:
        for item in pacote['itens']:
            item_code = item['ItemCode']
            quantidades_separadas[item_code] = quantidades_separadas.get(item_code, 0) + item['Quantity']

    if request.method == 'POST':
        peso_pacote = request.form.get('peso_pacote')
        report_pacote = request.form.get('report')
        localizacao_pacote = request.form.get('localizacao')
        
        novo_pacote = {
            'id': len(session['pickings_in_progress'][picking_key]['pacotes']) + 1,
            'peso': peso_pacote,
            'report': report_pacote,
            'localizacao': localizacao_pacote,
            'itens': []
        }

        for index, row in picking_items.iterrows():
            item_code = row['ItemCode']
            quantidade_str = request.form.get(f'quantidade_{item_code}')
            if quantidade_str:
                try:
                    quantidade = float(quantidade_str)
                    if quantidade > 0:
                        novo_pacote['itens'].append({
                            'ItemCode': item_code,
                            'ItemName': row['ItemName'],
                            'Quantity': quantidade,
                            'SWeight1': row['SWeight1']
                        })
                except (ValueError, TypeError):
                    pass

        if not novo_pacote['itens']:
            flash('Um pacote não pode ser vazio.', 'warning')
        else:
            session['pickings_in_progress'][picking_key]['pacotes'].append(novo_pacote)
            session.modified = True
            flash('Pacote criado com sucesso!', 'success')
        
        return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))

    return render_template('separacao_picking.html', 
                           items=picking_items.to_dict(orient='records'), 
                           abs_entry=abs_entry,
                           localizacao=localizacao,
                           pacotes=session['pickings_in_progress'][picking_key]['pacotes'],
                           quantidades_separadas=quantidades_separadas)


@pedidos_bp.route('/picking/finalizar/<int:abs_entry>/<localizacao>')
@login_required
def finalizar_separacao(abs_entry, localizacao):
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session or picking_key not in session['pickings_in_progress']:
        flash('Nenhuma separação em andamento para este picking.', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))

    df_original = get_pedidos_data()
    itens_originais = df_original[(df_original['AbsEntry'] == abs_entry) & (df_original['Localizacao'] == localizacao)]
    
    quantidades_separadas = {}
    for pacote in session['pickings_in_progress'][picking_key]['pacotes']:
        for item in pacote['itens']:
            item_code = item['ItemCode']
            quantidades_separadas[item_code] = quantidades_separadas.get(item_code, 0) + item['Quantity']
            
    for _, item_original in itens_originais.iterrows():
        item_code = item_original['ItemCode']
        if item_original['RelQtty'] != quantidades_separadas.get(item_code, 0):
            flash(f'A quantidade do item {item_code} não corresponde à do pedido original.', 'danger')
            return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))

    pacotes_data = []
    for pacote in session['pickings_in_progress'][picking_key]['pacotes']:
        for item in pacote['itens']:
            pacotes_data.append({
                'AbsEntry': abs_entry,
                'Localizacao': localizacao,
                'PackageID': pacote['id'],
                'Weight': pacote['peso'],
                'ItemCode': item['ItemCode'],
                'Quantity': item['Quantity'],
                'Report': pacote.get('report', ''),
                'Location': pacote.get('localizacao', '')
            })
    
    df_pacotes = pd.DataFrame(pacotes_data)
    if os.path.exists(PACOTES_PARQUET_PATH):
        df_existente = pd.read_parquet(PACOTES_PARQUET_PATH)
        df_pacotes = pd.concat([df_existente, df_pacotes])
    df_pacotes.to_parquet(PACOTES_PARQUET_PATH, index=False)

    df_separacao = get_separacao_data()
    # Define o EndTime para a separação atual
    df_separacao.loc[(df_separacao['AbsEntry'] == abs_entry) & (df_separacao['Localizacao'] == localizacao), 'EndTime'] = datetime.now().isoformat()
    df_separacao.to_parquet(SEPARACAO_PARQUET_PATH, index=False)

    session['pickings_in_progress'].pop(picking_key, None)
    session.modified = True
    flash('Separação finalizada e salva com sucesso!', 'success')
    return redirect(url_for('pedidos.listar_pedidos'))