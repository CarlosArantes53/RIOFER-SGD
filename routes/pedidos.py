import os
import pandas as pd
from flask import Blueprint, render_template, abort, session, redirect, url_for, flash, request
from decorators import login_required
from datetime import datetime
import unicodedata

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
    default_cols = ['AbsEntry', 'Localizacao', 'User', 'StartTime', 'EndTime', 'DiscrepancyLog', 'DiscrepancyReport']
    if not os.path.exists(SEPARACAO_PARQUET_PATH):
        return pd.DataFrame(columns=default_cols)
    try:
        df = pd.read_parquet(SEPARACAO_PARQUET_PATH)
        # Garantir compatibilidade com arquivos antigos
        if 'Localizacao' not in df.columns:
            df['Localizacao'] = ''
        if 'DiscrepancyLog' not in df.columns:
            df['DiscrepancyLog'] = ''
        if 'DiscrepancyReport' not in df.columns:
            df['DiscrepancyReport'] = ''
        return df
    except Exception as e:
        print(f"Erro ao ler o arquivo de separação parquet: {e}")
        return pd.DataFrame(columns=default_cols)


def get_packing_data():
    """Lê o arquivo parquet de packing."""
    if not os.path.exists(PACKING_PARQUET_PATH):
        return pd.DataFrame(columns=['AbsEntry', 'Localizacao'])
    try:
        return pd.read_parquet(PACKING_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de packing parquet: {e}")
        return pd.DataFrame(columns=['AbsEntry', 'Localizacao'])

def strip_accents(text):
    if text is None:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')

@pedidos_bp.route('/pedidos')
@login_required
def listar_pedidos():
    df_picking = get_pedidos_data()
    if df_picking is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    df_picking.dropna(subset=['Localizacao'], inplace=True)
    df_picking = df_picking[df_picking['Localizacao'].str.strip() != '']

    df_separacao = get_separacao_data()
    df_packing = get_packing_data()

    packing_finalizado_keys = set()
    if not df_packing.empty:
        packing_finalizado_keys = set(zip(df_packing['AbsEntry'], df_packing['Localizacao']))

    pedidos_agrupados_por_absentry = {}
    
    unique_pickings = df_picking.drop_duplicates(subset=['AbsEntry', 'Localizacao'])

    all_statuses = set()

    for _, row in unique_pickings.iterrows():
        abs_entry = row['AbsEntry']
        localizacao = row['Localizacao']

        separacao = df_separacao[(df_separacao['AbsEntry'] == abs_entry) & (df_separacao['Localizacao'] == localizacao)]
        status = 'Pendente'
        user = None
        
        if not separacao.empty:
            separacao_info = separacao.iloc[0]
            if pd.isna(separacao_info['EndTime']) or separacao_info['EndTime'] is None or separacao_info['EndTime'] == '':
                status = "Em separação"
                user = separacao_info['User']
            else:
                if (abs_entry, localizacao) in packing_finalizado_keys:
                    status = 'Packing Finalizado'
                else:
                    status = 'Aguardando Packing'
        
        all_statuses.add(status)

        location_info = {
            'Localizacao': localizacao,
            'Status': status,
            'StatusCompleto': f"Em separação por {user}" if status == "Em separação" else status,
            'UserInSeparation': user
        }

        if abs_entry not in pedidos_agrupados_por_absentry:
            pedidos_agrupados_por_absentry[abs_entry] = {
                'AbsEntry': abs_entry,
                'CardName': row['CardName'],
                'U_TU_QuemEntrega': row['U_TU_QuemEntrega'],
                'U_GI_Cidade': row['U_GI_Cidade'],
                'locations': [location_info]
            }
        else:
            pedidos_agrupados_por_absentry[abs_entry]['locations'].append(location_info)

    pedidos_finais = list(pedidos_agrupados_por_absentry.values())
    
    # Filtering logic
    filter_cliente = request.args.get('cliente', '').strip()
    filter_status = request.args.getlist('status')

    if filter_cliente:
        normalized_filter_cliente = strip_accents(filter_cliente.lower())
        pedidos_finais = [
            pedido for pedido in pedidos_finais
            if normalized_filter_cliente in strip_accents(pedido['CardName'].lower())
        ]

    if filter_status:
        pedidos_finais_filtrados = []
        for pedido in pedidos_finais:
            # Manter o pedido se alguma de suas localizações corresponder a um dos status filtrados
            if any(loc['Status'] in filter_status for loc in pedido['locations']):
                pedidos_finais_filtrados.append(pedido)
        pedidos_finais = pedidos_finais_filtrados

    return render_template('pedidos.html', 
                           pedidos_agrupados=pedidos_finais,
                           all_statuses=sorted(list(all_statuses)),
                           current_filters={'cliente': filter_cliente, 'status': filter_status})

@pedidos_bp.route('/picking/<int:abs_entry>')
@login_required
def visualizar_picking(abs_entry):
    df = get_pedidos_data()
    if df is None:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler o arquivo.")

    picking_items = df[df['AbsEntry'] == abs_entry]
    if picking_items.empty:
        abort(404, description="Picking não encontrado.")
        
    items_agrupados = picking_items.groupby('Localizacao')
    
    items_por_localizacao = {loc: group.to_dict(orient='records') for loc, group in items_agrupados}

    card_name = picking_items.iloc[0]['CardName']

    return render_template('picking_details.html', 
                           items_por_localizacao=items_por_localizacao, 
                           abs_entry=abs_entry,
                           card_name=card_name)


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
                'EndTime': None,
                'DiscrepancyLog': '',
                'DiscrepancyReport': ''
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
        # Validação para não separar mais do que o pedido
        for _, row in picking_items.iterrows():
            item_code = row['ItemCode']
            quantidade_str = request.form.get(f'quantidade_{item_code}')
            if quantidade_str:
                try:
                    quantidade_a_adicionar = float(quantidade_str)
                    if quantidade_a_adicionar > 0:
                        qtd_ja_separada = quantidades_separadas.get(item_code, 0)
                        qtd_total_pedido = row['RelQtty']
                        if (quantidade_a_adicionar + qtd_ja_separada) > qtd_total_pedido:
                            flash(f'Erro: A quantidade para o item {item_code} ({quantidade_a_adicionar + qtd_ja_separada}) excede a quantidade do pedido ({qtd_total_pedido}).', 'danger')
                            return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))
                except (ValueError, TypeError):
                    pass # Ignora valores inválidos que serão tratados depois

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

        for _, row in picking_items.iterrows():
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


@pedidos_bp.route('/picking/finalizar/<int:abs_entry>/<localizacao>', methods=['POST'])
@login_required
def finalizar_separacao(abs_entry, localizacao):
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session or picking_key not in session['pickings_in_progress']:
        flash('Nenhuma separação em andamento para este picking.', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))

    # Coleta de dados do formulário e da sessão
    discrepancy_report_text = request.form.get('discrepancy_report', '')
    df_original = get_pedidos_data()
    itens_originais = df_original[(df_original['AbsEntry'] == abs_entry) & (df_original['Localizacao'] == localizacao)]
    
    quantidades_separadas = {}
    for pacote in session['pickings_in_progress'][picking_key]['pacotes']:
        for item in pacote['itens']:
            item_code = item['ItemCode']
            quantidades_separadas[item_code] = quantidades_separadas.get(item_code, 0) + item['Quantity']

    # Lógica de divergência
    discrepancy_log = []
    for _, item_original in itens_originais.iterrows():
        item_code = item_original['ItemCode']
        qtd_pedido = item_original['RelQtty']
        qtd_separada = quantidades_separadas.get(item_code, 0)
        if qtd_pedido != qtd_separada:
            log_entry = f"Item {item_code}: Pedido={qtd_pedido}, Separado={qtd_separada}"
            discrepancy_log.append(log_entry)
            
    log_string = " | ".join(discrepancy_log)

    # Salvar pacotes
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
    
    if pacotes_data:
        df_pacotes = pd.DataFrame(pacotes_data)
        if os.path.exists(PACOTES_PARQUET_PATH):
            df_existente = pd.read_parquet(PACOTES_PARQUET_PATH)
            df_pacotes = pd.concat([df_existente, df_pacotes])
        df_pacotes.to_parquet(PACOTES_PARQUET_PATH, index=False)

    # Atualizar dados da separação com logs de divergência
    df_separacao = get_separacao_data()
    condition = (df_separacao['AbsEntry'] == abs_entry) & (df_separacao['Localizacao'] == localizacao)
    df_separacao.loc[condition, 'EndTime'] = datetime.now().isoformat()
    df_separacao.loc[condition, 'DiscrepancyLog'] = log_string
    df_separacao.loc[condition, 'DiscrepancyReport'] = discrepancy_report_text
    df_separacao.to_parquet(SEPARACAO_PARQUET_PATH, index=False)

    # Limpar sessão e redirecionar
    session['pickings_in_progress'].pop(picking_key, None)
    session.modified = True
    flash('Separação finalizada e salva com sucesso!', 'success')
    return redirect(url_for('pedidos.listar_pedidos'))