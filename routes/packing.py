# routes/packing.py

from flask import Blueprint, flash, redirect, render_template, session, url_for, request
from decorators import roles_required, order_type_required
from services import packing_service
from permissions import UserPermissions, get_current_user_permissions

packing_bp = Blueprint('packing', __name__)

@packing_bp.route('/packing')
@roles_required(list(UserPermissions.PACKING_ROLES))
def listar_packing():
    user_perms = get_current_user_permissions()
    pedidos = packing_service.get_pedidos_para_packing(user_perms)
    
    return render_template('templates/pedidos/paking/packing_list.html', 
                           pedidos_para_packing=pedidos)


@packing_bp.route('/packing/iniciar/<int:abs_entry>/<localizacao>', methods=['GET', 'POST'])
@order_type_required
def iniciar_packing(abs_entry, localizacao):
    pacotes = packing_service.get_pacotes_para_conferencia(abs_entry, localizacao)
    if pacotes is None:
        flash('Nenhum pacote encontrado para este pedido e localização.', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))

    if request.method == 'POST':
        erros = packing_service.finalizar_processo_packing(
            abs_entry=abs_entry,
            localizacao=localizacao,
            form_data=request.form,
            pacotes_info=pacotes,
            user_email=session['user']['email']
        )

        if not erros:
            flash('Packing da localização finalizado com sucesso!', 'success')
            return redirect(url_for('pedidos.listar_pedidos'))
        else:
            for erro in erros:
                flash(erro, 'danger')

    return render_template('templates/pedidos/paking/packing_details.html',
                           pacotes=pacotes,
                           abs_entry=abs_entry,
                           localizacao=localizacao)