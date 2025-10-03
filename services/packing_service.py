# services/packing_service.py

import pandas as pd
from datetime import datetime
from data import packing_repository, pedidos_repository, separacao_repository

def get_pedidos_para_packing():
    """
    Identifica quais pedidos/localizações estão prontos para o packing.
    Um pedido está pronto se a separação foi finalizada e não foi marcada como incompleta.
    """
    df_pacotes = pedidos_repository.get_pacotes_data()
    df_packing_finalizado = packing_repository.get_packing_data()
    df_separacao = separacao_repository.get_separacao_data()

    if df_pacotes.empty:
        return []

    # Agrupa por pedido/localização para ter uma lista única
    pedidos_com_pacotes = df_pacotes.drop_duplicates(subset=['AbsEntry', 'Localizacao'])

    # Conjuntos para verificação rápida de status
    finalizados_keys = set(zip(df_packing_finalizado['AbsEntry'], df_packing_finalizado['Localizacao']))
    
    # Considera um picking incompleto se o log de discrepância não estiver vazio
    incompletos_keys = set()
    df_incompleto = df_separacao[df_separacao['DiscrepancyLog'].notna() & (df_separacao['DiscrepancyLog'] != '')]
    if not df_incompleto.empty:
        incompletos_keys = set(zip(df_incompleto['AbsEntry'], df_incompleto['Localizacao']))

    pedidos_para_packing = []
    for _, row in pedidos_com_pacotes.iterrows():
        key = (row['AbsEntry'], row['Localizacao'])

        # Regra de negócio: Não mostra na lista de packing se o picking foi incompleto
        if key in incompletos_keys:
            continue

        pedido_dict = row.to_dict()
        pedido_dict['Status'] = 'Finalizado' if key in finalizados_keys else 'Aguardando Início'
        pedidos_para_packing.append(pedido_dict)

    return pedidos_para_packing

def get_pacotes_para_conferencia(abs_entry, localizacao):
    """
    Busca e agrupa os itens dos pacotes de uma localização específica para a tela de conferência.
    """
    df_pacotes = pedidos_repository.get_pacotes_data()
    pacotes_pedido = df_pacotes[(df_pacotes['AbsEntry'] == abs_entry) & (df_pacotes['Localizacao'] == localizacao)]

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
    """
    Valida os dados do formulário de packing e, se tudo estiver correto,
    salva o registro de finalização.
    Retorna uma lista de erros de validação. Se a lista estiver vazia, o processo foi bem-sucedido.
    """
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
            tolerancia = 0.05  # 5% de tolerância

            # Regra de negócio: verifica a divergência de peso
            if abs(peso_conferido - peso_original) > (peso_original * tolerancia):
                anomalia_msg = f"Divergência de peso no Pacote {package_id}. Registrado: {peso_original:.2f} kg, Conferido: {peso_conferido:.2f} kg."
                anomalias.append(anomalia_msg)
                erros.append(anomalia_msg) # Também adiciona a erros para parar o processo

        except (ValueError, TypeError):
            erros.append(f'O peso informado para o Pacote {package_id} é inválido.')

    if erros:
        return erros # Retorna a lista de erros para a rota exibir

    # Se não houver erros, salva os dados
    df_packing = packing_repository.get_packing_data()
    now = datetime.now().isoformat()
    
    packing_records = [{
        'AbsEntry': abs_entry,
        'Localizacao': localizacao,
        'PackageID': pacote['id'],
        'User': user_email,
        'StartTime': now, # Simplificado, idealmente viria do início da interação
        'EndTime': now,
        'Anomalias': "; ".join(anomalias) # Anomalias são salvas mesmo se não bloquearem
    } for pacote in pacotes_info]
    
    nova_conferencia = pd.DataFrame(packing_records)
    df_packing_final = pd.concat([df_packing, nova_conferencia], ignore_index=True)
    
    packing_repository.save_packing_data(df_packing_final)
    
    return [] # Retorna lista vazia indicando sucesso