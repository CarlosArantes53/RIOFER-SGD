# routes/pedidos.py

import unicodedata
from flask import (Blueprint, render_template, abort, session, redirect,
                   url_for, flash, request)
from decorators import login_required
from services import pedidos_service
from data import pedidos_repository

pedidos_bp = Blueprint('pedidos', __name__)

def strip_accents(text):
    """Função utilitária para normalizar texto para filtros."""
    if text is None:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')

@pedidos_bp.route('/pedidos')
@login_required
def listar_pedidos():
    """
    Rota para listar os pedidos. A lógica de negócio foi movida para o serviço.
    """
    pedidos_finais, _, sync_time = pedidos_service.get_pedidos_para_listar()

    ALL_POSSIBLE_STATUSES = [
        'Pendente', 'Em separação', 'Picking Incompleto',
        'Aguardando Packing', 'Packing Finalizado'
    ]

    filter_cliente = request.args.get('cliente', '').strip()
    filter_status = request.args.getlist('status') or [s for s in ALL_POSSIBLE_STATUSES if s != 'Packing Finalizado']

    if filter_cliente:
        normalized_filter = strip_accents(filter_cliente.lower())
        pedidos_finais = [p for p in pedidos_finais if normalized_filter in strip_accents(p['CardName'].lower())]

    if filter_status:
        pedidos_finais = [
            p for p in pedidos_finais
            if any(loc['Status'] in filter_status for loc in p['locations'])
        ]

    # Separa os pedidos por tipo de entrega
    pedidos_entrega = [p for p in pedidos_finais if p.get('U_TU_QuemEntrega') != '02']
    pedidos_retira = [p for p in pedidos_finais if p.get('U_TU_QuemEntrega') == '02']

    return render_template('pedidos.html',
                           pedidos_entrega=pedidos_entrega,
                           pedidos_retira=pedidos_retira,
                           all_statuses=ALL_POSSIBLE_STATUSES,
                           current_filters={'cliente': filter_cliente, 'status': filter_status},
                           sync_time=sync_time)


# --- O restante do arquivo continua o mesmo ---

@pedidos_bp.route('/picking/<int:abs_entry>')
@login_required
def visualizar_picking(abs_entry):
    """
    Exibe os detalhes de todos os itens de um picking, agrupados por localização.
    """
    df = pedidos_repository.get_picking_data()
    if df.empty:
        abort(500, description="Arquivo de picking não encontrado ou erro ao ler.")

    picking_items = df[df['AbsEntry'] == abs_entry]
    if picking_items.empty:
        abort(404, description="Picking não encontrado.")

    # Agrupa os itens por localização para exibição no template
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
    """
    Inicia a separação, atualizando o log via serviço e preparando a sessão do usuário.
    """
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session:
        session['pickings_in_progress'] = {}

    start_time = pedidos_service.iniciar_nova_separacao(abs_entry, localizacao, session['user']['email'])

    session['pickings_in_progress'][picking_key] = {
        'abs_entry': abs_entry,
        'localizacao': localizacao,
        'start_time': start_time,
        'pacotes': []
    }
    session.modified = True
    
    flash('Separação iniciada!', 'success')
    return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))


@pedidos_bp.route('/picking/separar/<int:abs_entry>/<localizacao>', methods=['GET', 'POST'])
@login_required
def separar_picking(abs_entry, localizacao):
    """
    Tela principal da separação, onde pacotes são criados e gerenciados na sessão.
    """
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session or picking_key not in session['pickings_in_progress']:
        flash('Nenhuma separação em andamento. Inicie a separação primeiro.', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))

    df = pedidos_repository.get_picking_data()
    picking_items_df = df[(df['AbsEntry'] == abs_entry) & (df['Localizacao'] == localizacao)]
    if picking_items_df.empty:
        abort(404, description="Itens do Picking não encontrados.")

    quantidades_separadas = {}
    for pacote in session['pickings_in_progress'][picking_key]['pacotes']:
        for item in pacote['itens']:
            item_code = item['ItemCode']
            quantidades_separadas[item_code] = quantidades_separadas.get(item_code, 0) + item['Quantity']

    if request.method == 'POST':
        itens_pacote = []
        has_error = False
        for _, item_pedido in picking_items_df.iterrows():
            item_code = item_pedido['ItemCode']
            try:
                quantidade_str = request.form.get(f'quantidade_{item_code}', '0').replace(',', '.')
                quantidade = float(quantidade_str) if quantidade_str else 0
                
                if quantidade > 0:
                    # Validação da quantidade
                    total_pedido = item_pedido['RelQtty']
                    ja_separado = quantidades_separadas.get(item_code, 0)
                    if (ja_separado + quantidade) > total_pedido:
                        flash(f"Quantidade para o item {item_code} excede o solicitado no pedido.", 'danger')
                        has_error = True
                        break 
                    
                    itens_pacote.append({
                        "ItemCode": item_code,
                        "ItemName": item_pedido['ItemName'],
                        "Quantity": quantidade
                    })
            except (ValueError, TypeError):
                flash(f"Valor inválido para a quantidade do item {item_code}.", 'danger')
                has_error = True
                break

        if has_error:
            return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))

        if not itens_pacote:
            flash("Nenhum item foi adicionado ao pacote. Preencha as quantidades.", 'warning')
        else:
            try:
                novo_pacote = {
                    "id": len(session['pickings_in_progress'][picking_key]['pacotes']) + 1,
                    "peso": float(request.form.get('peso_pacote')),
                    "localizacao": request.form.get('localizacao'),
                    "report": request.form.get('report', ''),
                    "itens": itens_pacote
                }
                session['pickings_in_progress'][picking_key]['pacotes'].append(novo_pacote)
                session.modified = True
                flash('Pacote criado com sucesso!', 'success')
            except (ValueError, TypeError):
                flash('O peso do pacote deve ser um número válido.', 'danger')

        return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))
        
    return render_template('separacao_picking.html',
                           items=picking_items_df.to_dict(orient='records'),
                           abs_entry=abs_entry,
                           localizacao=localizacao,
                           pacotes=session['pickings_in_progress'][picking_key]['pacotes'],
                           quantidades_separadas=quantidades_separadas)

@pedidos_bp.route('/picking/finalizar/<int:abs_entry>/<localizacao>', methods=['POST'])
@login_required
def finalizar_separacao(abs_entry, localizacao):
    """
    Finaliza o processo, enviando os dados da sessão para o serviço.
    """
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session or picking_key not in session['pickings_in_progress']:
        flash('Nenhuma separação em andamento para este picking.', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))

    pacotes_sessao = session['pickings_in_progress'][picking_key]['pacotes']
    discrepancy_report = request.form.get('discrepancy_report', '')

    success = pedidos_service.finalizar_processo_separacao(
        abs_entry, localizacao, pacotes_sessao, discrepancy_report
    )

    if success:
        flash('Separação finalizada e salva com sucesso!', 'success')
    else:
        flash('Ocorreu um erro ao finalizar a separação.', 'danger')

    session['pickings_in_progress'].pop(picking_key, None)
    session.modified = True
    return redirect(url_for('pedidos.listar_pedidos'))

@pedidos_bp.route('/picking/pacote/excluir/<int:abs_entry>/<localizacao>/<int:pacote_id>')
@login_required
def excluir_pacote_sessao(abs_entry, localizacao, pacote_id):
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' in session and picking_key in session['pickings_in_progress']:
        pacotes = session['pickings_in_progress'][picking_key]['pacotes']
        
        pacote_encontrado = next((p for p in pacotes if p['id'] == pacote_id), None)
        
        if pacote_encontrado:
            pacotes.remove(pacote_encontrado)
            # Re-indexar IDs
            for i, p in enumerate(pacotes):
                p['id'] = i + 1
            session.modified = True
            flash(f'Pacote {pacote_id} excluído.', 'success')
        else:
            flash(f'Pacote {pacote_id} não encontrado.', 'danger')
    else:
        flash('Nenhuma separação encontrada na sessão.', 'danger')
        
    return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))

@pedidos_bp.route('/picking/pacote/editar/<int:abs_entry>/<localizacao>/<int:pacote_id>', methods=['GET', 'POST'])
@login_required
def editar_pacote_sessao(abs_entry, localizacao, pacote_id):
    picking_key = f"{abs_entry}_{localizacao}"
    if 'pickings_in_progress' not in session or picking_key not in session['pickings_in_progress']:
        flash('Nenhuma separação em andamento para este picking.', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))

    pacotes = session['pickings_in_progress'][picking_key]['pacotes']
    pacote_para_editar = next((p for p in pacotes if p['id'] == pacote_id), None)

    if not pacote_para_editar:
        flash('Pacote não encontrado.', 'danger')
        return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))

    # --- LINHA CORRIGIDA ---
    df = pedidos_repository.get_picking_data() # Busca os dados do repositório
    itens_do_pedido = df[(df['AbsEntry'] == abs_entry) & (df['Localizacao'] == localizacao)]

    if request.method == 'POST':
        # Calcula a quantidade já separada em OUTROS pacotes
        quantidades_outros_pacotes = {}
        for pacote in pacotes:
            if pacote['id'] != pacote_id:
                for item in pacote['itens']:
                    item_code = item['ItemCode']
                    quantidades_outros_pacotes[item_code] = quantidades_outros_pacotes.get(item_code, 0) + item['Quantity']
        
        has_error = False
        novos_itens = []
        for item_no_pacote in pacote_para_editar['itens']:
            item_code = item_no_pacote['ItemCode']
            try:
                nova_quantidade = float(request.form.get(f'quantidade_{item_code}', 0))

                if nova_quantidade <= 0:
                    continue # Item será removido

                total_pedido_item = itens_do_pedido[itens_do_pedido['ItemCode'] == item_code]['RelQtty'].iloc[0]
                separado_outros = quantidades_outros_pacotes.get(item_code, 0)

                if (nova_quantidade + separado_outros) > total_pedido_item:
                    flash(f'Erro no item {item_code}: A quantidade total separada ({nova_quantidade + separado_outros}) não pode exceder a quantidade do pedido ({total_pedido_item}).', 'danger')
                    has_error = True
                else:
                    item_no_pacote['Quantity'] = nova_quantidade
                    novos_itens.append(item_no_pacote)

            except (ValueError, TypeError):
                flash(f'Quantidade inválida para o item {item_code}. Mantendo valor original.', 'warning')
                novos_itens.append(item_no_pacote) # Mantém o item com a quantidade antiga
        
        if has_error:
            return render_template('editar_pacote_sessao.html',
                           pacote=pacote_para_editar,
                           abs_entry=abs_entry,
                           localizacao=localizacao)
        
        pacote_para_editar['itens'] = novos_itens
        pacote_para_editar['peso'] = request.form.get('peso_pacote')
        pacote_para_editar['report'] = request.form.get('report')
        pacote_para_editar['localizacao'] = request.form.get('localizacao')

        if not pacote_para_editar['itens']:
            pacotes.remove(pacote_para_editar)
            for i, p in enumerate(pacotes):
                p['id'] = i + 1
            session.modified = True
            flash(f'Pacote {pacote_id} foi removido por estar vazio.', 'success')
        else:
            session.modified = True
            flash('Pacote atualizado com sucesso!', 'success')
            
        return redirect(url_for('pedidos.separar_picking', abs_entry=abs_entry, localizacao=localizacao))

    return render_template('editar_pacote_sessao.html',
                           pacote=pacote_para_editar,
                           abs_entry=abs_entry,
                           localizacao=localizacao)