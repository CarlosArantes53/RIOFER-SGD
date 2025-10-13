import pandas as pd
from datetime import datetime
from data import packing_repository, pedidos_repository, separacao_repository

def get_pedidos_para_packing(user_perms):
    df_pacotes = pedidos_repository.get_pacotes_data()
    df_picking = pedidos_repository.get_picking_data()
    df_packing_finalizado = packing_repository.get_packing_data()
    df_separacao = separacao_repository.get_separacao_data()

    if df_pacotes.empty or df_picking.empty:
        return []

    df_pacotes.dropna(subset=['Localizacao'], inplace=True)
    df_pacotes = df_pacotes[df_pacotes['Localizacao'].str.strip() != '']

    df_picking_info = df_picking.drop_duplicates(subset=['AbsEntry'])[['AbsEntry', 'CardName', 'U_TU_QuemEntrega']]

    df_pacotes_com_tipo = pd.merge(df_pacotes, df_picking_info[['AbsEntry', 'U_TU_QuemEntrega']], on='AbsEntry', how='left')
    
    pedidos_visiveis = []
    if user_perms.can_view_entregas():
        pedidos_visiveis.append(df_pacotes_com_tipo[df_pacotes_com_tipo['U_TU_QuemEntrega'] != '02'])
    if user_perms.can_view_retira():
        pedidos_visiveis.append(df_pacotes_com_tipo[df_pacotes_com_tipo['U_TU_QuemEntrega'] == '02'])
    
    if not pedidos_visiveis:
        return []
    df_pacotes_filtrados = pd.concat(pedidos_visiveis)

    pedidos_para_packing_base = df_pacotes_filtrados.drop_duplicates(subset=['AbsEntry', 'Localizacao'])
    
    pedidos_para_packing_com_nome = pd.merge(pedidos_para_packing_base, df_picking_info[['AbsEntry', 'CardName']], on='AbsEntry', how='left')

    finalizados_keys = set(zip(df_packing_finalizado['AbsEntry'], df_packing_finalizado['Localizacao']))
    incompletos_keys = set()
    df_incompleto = df_separacao[df_separacao['DiscrepancyLog'].notna() & (df_separacao['DiscrepancyLog'] != '')]
    if not df_incompleto.empty:
        incompletos_keys = set(zip(df_incompleto['AbsEntry'], df_incompleto['Localizacao']))

    pedidos_para_packing_final = []
    for _, row in pedidos_para_packing_com_nome.iterrows():
        key = (row['AbsEntry'], row['Localizacao'])

        if key in incompletos_keys:
            continue

        pedido_dict = row.to_dict()
        pedido_dict['Status'] = 'Finalizado' if key in finalizados_keys else 'Aguardando Início'
        pedidos_para_packing_final.append(pedido_dict)

    return pedidos_para_packing_final

def get_pacotes_para_conferencia(abs_entry, localizacao):

    df_pacotes = pedidos_repository.get_pacotes_data()
    
    if df_pacotes.empty:
        return None

    df_pacotes['AbsEntry'] = pd.to_numeric(df_pacotes['AbsEntry'], errors='coerce').fillna(0).astype(int)

    pacotes_pedido = df_pacotes[
        (df_pacotes['AbsEntry'] == abs_entry) & 
        (df_pacotes['Localizacao'] == localizacao)
    ]

    if pacotes_pedido.empty:
        return None

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
    
    return list(pacotes_agrupados.values())


def finalizar_processo_packing(abs_entry, localizacao, form_data, pacotes_info, user_email):

    erros = []
    anomalias = []

    for pacote in pacotes_info:
        package_id = pacote['id']
        peso_conferido_str = form_data.get(f'peso_pacote_{package_id}')
        confirmado = form_data.get(f'confirm_pacote_{package_id}')

        if not confirmado:
            erros.append(f'O Pacote {package_id} precisa ser marcado como confirmado.')
            continue

        try:
            peso_conferido = float(peso_conferido_str)
            peso_original = float(pacote['peso_original'])
            tolerancia = 0.05

            if abs(peso_conferido - peso_original) > (peso_original * tolerancia):
                anomalia_msg = f"Divergência de peso no Pacote {package_id}. Registrado: {peso_original:.2f} kg, Conferido: {peso_conferido:.2f} kg."
                anomalias.append(anomalia_msg)

        except (ValueError, TypeError):
            erros.append(f'O peso informado para o Pacote {package_id} é inválido.')

    if erros:
        return erros
    
    df_packing = packing_repository.get_packing_data()
    now = datetime.now().isoformat()
    
    packing_records = [{
        'AbsEntry': abs_entry,
        'Localizacao': localizacao,
        'PackageID': pacote['id'],
        'User': user_email,
        'StartTime': now,
        'EndTime': now,
        'Anomalias': "; ".join(anomalias) 
    } for pacote in pacotes_info]
    
    nova_conferencia = pd.DataFrame(packing_records)

    df_packing = df_packing[~((df_packing['AbsEntry'] == abs_entry) & (df_packing['Localizacao'] == localizacao))]
    
    df_packing_final = pd.concat([df_packing, nova_conferencia], ignore_index=True)
    
    packing_repository.save_packing_data(df_packing_final)
    
    return []