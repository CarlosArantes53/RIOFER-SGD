# data/regioes_repository.py

import os
import pandas as pd

REGIOES_PARQUET_PATH = os.getenv('RIOFER_REGIOES_SGD')

def get_regioes_data():
    if not REGIOES_PARQUET_PATH or not os.path.exists(REGIOES_PARQUET_PATH):
        return pd.DataFrame(columns=['Nome', 'Cidades'])
    try:
        return pd.read_parquet(REGIOES_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de regiões: {e}")
        return pd.DataFrame(columns=['Nome', 'Cidades'])

def save_regioes_data(df_regioes):
    try:
        df_regioes.to_parquet(REGIOES_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo de regiões: {e}")
        return False