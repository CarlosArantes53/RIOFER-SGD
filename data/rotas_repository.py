# data/rotas_repository.py

import os
import pandas as pd
from datetime import datetime

ROTAS_PARQUET_PATH = os.getenv('RIOFER_ROTAS_SGD')
PARADAS_PARQUET_PATH = os.getenv('RIOFER_PARADAS_SGD')

def get_rotas_data():
    """Carrega os dados das rotas."""
    if not ROTAS_PARQUET_PATH or not os.path.exists(ROTAS_PARQUET_PATH):
        return pd.DataFrame(columns=[
            'ID_Rota', 'ID_Caminhao', 'Placa_Caminhao', 'Nome_Motorista', 'Data_Rota', 
            'Status', 'Meta_KG', 'Data_Limite', 'Observacoes', 'Tipo'
        ])
    return pd.read_parquet(ROTAS_PARQUET_PATH)

def get_paradas_data():
    """Carrega os dados das paradas das rotas."""
    if not PARADAS_PARQUET_PATH or not os.path.exists(PARADAS_PARQUET_PATH):
        return pd.DataFrame(columns=[
            'ID_Rota', 'AbsEntry', 'CardName', 'Ordem_Visita', 'Status_Parada'
        ])
    return pd.read_parquet(PARADAS_PARQUET_PATH)

def save_rotas_data(df_rotas):
    """Salva os dados das rotas."""
    try:
        df_rotas.to_parquet(ROTAS_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar arquivo de rotas: {e}")
        return False

def save_paradas_data(df_paradas):
    """Salva os dados das paradas."""
    try:
        df_paradas.to_parquet(PARADAS_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar arquivo de paradas: {e}")
        return False

def get_next_rota_id():
    """Gera um novo ID sequencial para a rota."""
    df_rotas = get_rotas_data()
    if df_rotas.empty:
        return 1
    return df_rotas['ID_Rota'].max() + 1