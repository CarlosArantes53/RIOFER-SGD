# data/sequencia_repository.py

import os
import pandas as pd

SEQUENCIA_PARQUET_PATH = os.getenv('RIOFER_SEQUENCIA_SGD')

def get_sequencia_data():
    if not os.path.exists(SEQUENCIA_PARQUET_PATH):
        return pd.DataFrame(columns=['AbsEntry', 'Tipo', 'Ordem'])
    try:
        return pd.read_parquet(SEQUENCIA_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de sequência: {e}")
        return pd.DataFrame(columns=['AbsEntry', 'Tipo', 'Ordem'])

def save_sequencia_data(df_sequencia):
    try:
        df_sequencia.to_parquet(SEQUENCIA_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo de sequência: {e}")
        return False