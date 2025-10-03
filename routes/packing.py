# routes/packing.py

from flask import (Blueprint, render_template, request, flash, redirect,
                   url_for, session, abort)
from decorators import login_required
from services import packing_service # <-- Importa o serviço

packing_bp = Blueprint('packing', __name__)

@packing_bp.route('/packing')
@login_required
def listar_packing():
    """
    Exibe a lista de pedidos que estão aguardando o processo de packing.
    """
    pedidos = packing_service.get_pedidos_para_packing()
    
    # Valores padrão para as variáveis que o template 'pedidos.html' espera
    all_statuses = ['Aguardando Início', 'Finalizado']
    current_filters = {'cliente': '', 'status': ['Aguardando Início']}

    return render_template('pedidos.html', 
                           pedidos_agrupados=pedidos,
                           all_statuses=all_statuses,
                           current_filters=current_filters)


@packing_bp.route('/packing/iniciar/<int:abs_entry>/<localizacao>', methods=['GET', 'POST'])
@login_required
def iniciar_packing(abs_entry, localizacao):
    """
    Controla a tela de conferência e finalização do packing para uma localização.
    """
    # Busca os pacotes formatados para exibição na tela
    pacotes = packing_service.get_pacotes_para_conferencia(abs_entry, localizacao)
    if pacotes is None:
        flash('Nenhum pacote encontrado para este pedido e localização.', 'warning')
        return redirect(url_for('packing.listar_packing'))

    if request.method == 'POST':
        # Envia os dados do formulário e dos pacotes para o serviço validar e salvar
        erros = packing_service.finalizar_processo_packing(
            abs_entry=abs_entry,
            localizacao=localizacao,
            form_data=request.form,
            pacotes_info=pacotes,
            user_email=session['user']['email']
        )

        if not erros:
            flash('Packing da localização finalizado com sucesso!', 'success')
            return redirect(url_for('packing.listar_packing'))
        else:
            # Se o serviço retornar erros de validação, exibe-os
            for erro in erros:
                flash(erro, 'danger')

    return render_template('packing_details.html',
                           pacotes=pacotes,
                           abs_entry=abs_entry,
                           localizacao=localizacao)