# services/rotas_service.py

import pandas as pd
from datetime import datetime
from data import rotas_repository, pedidos_repository, frota_repository

def get_pedidos_disponiveis():
    """
    Retorna um DataFrame com pedidos que ainda não foram alocados a uma rota.
    """
    df_picking = pedidos_repository.get_picking_data()
    df_paradas = rotas_repository.get_paradas_data()
    
    # Consideramos apenas entregas, não retiradas
    df_entregas = df_picking[df_picking['U_TU_QuemEntrega'] != '02'].copy()
    
    pedidos_alocados = set(df_paradas['AbsEntry'])
    
    # Filtra pedidos que ainda não estão em nenhuma parada
    df_disponiveis = df_entregas[~df_entregas['AbsEntry'].isin(pedidos_alocados)]
    
    # Agrupa para ter um pedido por linha, e calcula o peso total
    df_agg = df_disponiveis.groupby('AbsEntry').agg(
        CardName=('CardName', 'first'),
        PesoTotal=('SWeight1', lambda x: (x * df_disponiveis.loc[x.index, 'RelQtty']).sum())
    ).reset_index()

    return df_agg

def get_rotas_com_detalhes():
    """
    Lista todas as rotas com informações agregadas como peso total e número de paradas.
    """
    df_rotas = rotas_repository.get_rotas_data()
    df_paradas = rotas_repository.get_paradas_data()
    df_picking = pedidos_repository.get_picking_data()
    
    if df_rotas.empty:
        return []

    # Calcula o peso de cada item no picking
    df_picking['PesoItem'] = df_picking['SWeight1'] * df_picking['RelQtty']
    peso_por_pedido = df_picking.groupby('AbsEntry')['PesoItem'].sum()

    # Agrega dados das paradas
    paradas_agg = df_paradas.groupby('ID_Rota').agg(
        Num_Paradas=('AbsEntry', 'count'),
        Pedidos=('AbsEntry', list)
    ).reset_index()
    
    # Calcula o peso total da rota
    paradas_agg['Peso_Total_KG'] = paradas_agg['Pedidos'].apply(
        lambda pedidos: sum(peso_por_pedido.get(p, 0) for p in pedidos)
    )
    
    # Junta com os dados da rota
    df_merged = pd.merge(df_rotas, paradas_agg, on='ID_Rota', how='left')
    df_merged['Num_Paradas'] = df_merged['Num_Paradas'].fillna(0).astype(int)
    df_merged['Peso_Total_KG'] = df_merged['Peso_Total_KG'].fillna(0)
    
    return df_merged.sort_values(by='Data_Rota', ascending=False).to_dict('records')


def create_nova_rota(dados_rota):
    """
    Cria uma nova rota e suas respectivas paradas.
    'dados_rota' é um dicionário contendo:
    - id_caminhao, data_rota, tipo, meta_kg, data_limite, observacoes
    - pedidos: uma lista de dicionários {'AbsEntry': id, 'CardName': nome}
    """
    df_rotas = rotas_repository.get_rotas_data()
    df_paradas = rotas_repository.get_paradas_data()
    df_frota = frota_repository.get_frota_data()

    id_rota = rotas_repository.get_next_rota_id()
    
    caminhao = df_frota[df_frota['ID_Caminhao'] == dados_rota['id_caminhao']].iloc[0]

    # Cria a nova rota
    nova_rota_df = pd.DataFrame([{
        'ID_Rota': id_rota,
        'ID_Caminhao': dados_rota['id_caminhao'],
        'Placa_Caminhao': caminhao['Placa'],
        'Nome_Motorista': caminhao['Nome_Motorista'],
        'Data_Rota': pd.to_datetime(dados_rota['data_rota']),
        'Status': 'Pendente' if dados_rota['tipo'] == 'Pendente' else 'Planejada',
        'Meta_KG': float(dados_rota.get('meta_kg') or 0),
        'Data_Limite': pd.to_datetime(dados_rota.get('data_limite')) if dados_rota.get('data_limite') else None,
        'Observacoes': dados_rota.get('observacoes', ''),
        'Tipo': dados_rota['tipo']
    }])
    df_rotas = pd.concat([df_rotas, nova_rota_df], ignore_index=True)

    # Cria as paradas
    novas_paradas = []
    for i, pedido in enumerate(dados_rota['pedidos']):
        novas_paradas.append({
            'ID_Rota': id_rota,
            'AbsEntry': int(pedido['AbsEntry']),
            'CardName': pedido['CardName'],
            'Ordem_Visita': i + 1, # Ordem inicial, pode ser otimizada depois
            'Status_Parada': 'Pendente'
        })
    
    if novas_paradas:
        paradas_df = pd.DataFrame(novas_paradas)
        df_paradas = pd.concat([df_paradas, paradas_df], ignore_index=True)

    # Salva ambos os dataframes
    if rotas_repository.save_rotas_data(df_rotas) and rotas_repository.save_paradas_data(df_paradas):
        return True, id_rota
    
    return False, None