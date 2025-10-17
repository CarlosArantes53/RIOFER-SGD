# data/frota_repository.py

import os
import pandas as pd
import uuid

FROTA_PARQUET_PATH = os.getenv('RIOFER_FROTA_SGD')

def get_frota_data():
    if not FROTA_PARQUET_PATH or not os.path.exists(FROTA_PARQUET_PATH):
        return pd.DataFrame(columns=[
            'ID_Caminhao', 'Placa', 'Descricao', 'ID_Motorista', 'Nome_Motorista',
            'Capacidade_KG', 'Tolerancia', 'Status'
        ])
    try:
        return pd.read_parquet(FROTA_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo da frota: {e}")
        return pd.DataFrame()

def save_frota_data(df_frota):
    try:
        df_frota.to_parquet(FROTA_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo da frota: {e}")
        return False

def add_veiculo(veiculo_data):
    df_frota = get_frota_data()
    
    # Gera um ID único para o caminhão
    veiculo_data['ID_Caminhao'] = str(uuid.uuid4())
    
    novo_veiculo = pd.DataFrame([veiculo_data])
    df_frota = pd.concat([df_frota, novo_veiculo], ignore_index=True)
    
    return save_frota_data(df_frota)

def update_veiculo(veiculo_id, update_data):
    df_frota = get_frota_data()
    
    if veiculo_id not in df_frota['ID_Caminhao'].values:
        return False, "Veículo não encontrado."

    idx = df_frota[df_frota['ID_Caminhao'] == veiculo_id].index
    df_frota.loc[idx, update_data.keys()] = update_data.values()
    
    return save_frota_data(df_frota), "Dados atualizados."

def delete_veiculo(veiculo_id):
    df_frota = get_frota_data()
    
    if veiculo_id not in df_frota['ID_Caminhao'].values:
        return False
        
    df_frota = df_frota[df_frota['ID_Caminhao'] != veiculo_id]
    
    return save_frota_data(df_frota)