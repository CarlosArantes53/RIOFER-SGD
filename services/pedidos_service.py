import pandas as pd
from datetime import datetime
from data import pedidos_repository, separacao_repository, packing_repository


def get_pedidos_para_listar():

    df_picking = pedidos_repository.get_picking_data()
    df_separacao = separacao_repository.get_separacao_data()
    df_packing = packing_repository.get_packing_data()
    sync_time = pedidos_repository.get_picking_file_mtime()

    if df_picking.empty:
        return [], set(), sync_time

    df_picking.dropna(subset=['Localizacao'], inplace=True)
    df_picking = df_picking[df_picking['Localizacao'].str.strip() != '']

    packing_finalizado_keys = set()
    if not df_packing.empty:
        packing_finalizado_keys = set(zip(df_packing['AbsEntry'], df_packing['Localizacao']))

    df_separacao_indexed = df_separacao.set_index(['AbsEntry', 'Localizacao'])

    pedidos_agrupados = {}
    all_statuses = set()

    for _, row in df_picking.drop_duplicates(subset=['AbsEntry', 'Localizacao']).iterrows():
        abs_entry = row['AbsEntry']
        localizacao = row['Localizacao']
        key = (abs_entry, localizacao)

        status = 'Pendente'
        user = None

        if key in df_separacao_indexed.index:
            separacao_info = df_separacao_indexed.loc[key]
            end_time = separacao_info.get('EndTime')
            
            if pd.isna(end_time) or end_time is None or end_time == '':
                status = "Em separação"
                user = separacao_info['User']
            else:
                if separacao_info.get('DiscrepancyLog'):
                    status = 'Picking Incompleto'
                elif key in packing_finalizado_keys:
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

        if abs_entry not in pedidos_agrupados:
            pedidos_agrupados[abs_entry] = row.to_dict()
            pedidos_agrupados[abs_entry]['locations'] = []
        
        pedidos_agrupados[abs_entry]['locations'].append(location_info)

    return list(pedidos_agrupados.values()), sorted(list(all_statuses)), sync_time


def iniciar_nova_separacao(abs_entry, localizacao, user_email):
    df_separacao = separacao_repository.get_separacao_data()
    condition = (df_separacao['AbsEntry'] == abs_entry) & (df_separacao['Localizacao'] == localizacao)
    separacao_existente = df_separacao[condition]

    start_time = datetime.now().isoformat()

    if separacao_existente.empty:
        nova_separacao = pd.DataFrame([{
            'AbsEntry': abs_entry, 'Localizacao': localizacao, 'User': user_email,
            'StartTime': start_time, 'EndTime': None, 'DiscrepancyLog': '', 'DiscrepancyReport': ''
        }])
        df_separacao = pd.concat([df_separacao, nova_separacao], ignore_index=True)
    else:
        df_separacao.loc[condition, 'User'] = user_email
        df_separacao.loc[condition, 'StartTime'] = start_time
        df_separacao.loc[condition, 'EndTime'] = None
        df_separacao.loc[condition, 'DiscrepancyLog'] = ''
        df_separacao.loc[condition, 'DiscrepancyReport'] = ''

    separacao_repository.save_separacao_data(df_separacao)
    return start_time


def finalizar_processo_separacao(abs_entry, localizacao, pacotes_sessao, discrepancy_report_text):
    df_original = pedidos_repository.get_picking_data()
    itens_originais = df_original[(df_original['AbsEntry'] == abs_entry) & (df_original['Localizacao'] == localizacao)]
    
    quantidades_separadas = {}
    for pacote in pacotes_sessao:
        for item in pacote['itens']:
            item_code = item['ItemCode']
            quantidades_separadas[item_code] = quantidades_separadas.get(item_code, 0) + item['Quantity']

    discrepancy_log = []
    for _, item_original in itens_originais.iterrows():
        item_code = item_original['ItemCode']
        qtd_pedido = item_original['RelQtty']
        qtd_separada = quantidades_separadas.get(item_code, 0)
        if qtd_pedido != qtd_separada:
            log_entry = f"Item {item_code}: Pedido={qtd_pedido}, Separado={qtd_separada}"
            discrepancy_log.append(log_entry)
            
    log_string = " | ".join(discrepancy_log)

    pacotes_data = []
    for pacote in pacotes_sessao:
        for item in pacote['itens']:
            pacotes_data.append({
                'AbsEntry': abs_entry, 'Localizacao': localizacao,
                'PackageID': pacote['id'], 'Weight': pacote['peso'],
                'ItemCode': item['ItemCode'], 
                'ItemName': item['ItemName'],
                'Quantity': item['Quantity'],
                'Report': pacote.get('report', ''), 
                'Location': pacote.get('localizacao', '')
            })
    
    if pacotes_data:
        df_pacotes_novos = pd.DataFrame(pacotes_data)
        df_existente = pedidos_repository.get_pacotes_data()
        df_existente = df_existente[~((df_existente['AbsEntry'] == abs_entry) & (df_existente['Localizacao'] == localizacao))]
        df_pacotes_final = pd.concat([df_existente, df_pacotes_novos], ignore_index=True)
        pedidos_repository.save_pacotes_data(df_pacotes_final)

    df_separacao = separacao_repository.get_separacao_data()
    condition = (df_separacao['AbsEntry'] == abs_entry) & (df_separacao['Localizacao'] == localizacao)
    df_separacao.loc[condition, 'EndTime'] = datetime.now().isoformat()
    df_separacao.loc[condition, 'DiscrepancyLog'] = log_string
    df_separacao.loc[condition, 'DiscrepancyReport'] = discrepancy_report_text
    
    return separacao_repository.save_separacao_data(df_separacao)
