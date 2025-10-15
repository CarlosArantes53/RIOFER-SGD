# data/sequencia_repository.py

import os
import pandas as pd

SEQUENCIA_PARQUET_PATH = os.getenv('RIOFER_SEQUENCIA_SGD', 'sequencia_separacao.parquet')

def get_sequencia_data():
    """
    Lê os dados de sequência de separação do arquivo parquet.
    Retorna um DataFrame vazio se o arquivo não for encontrado.
    """
    if not os.path.exists(SEQUENCIA_PARQUET_PATH):
        return pd.DataFrame(columns=['AbsEntry', 'Tipo', 'Ordem'])
    try:
        return pd.read_parquet(SEQUENCIA_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de sequência: {e}")
        return pd.DataFrame(columns=['AbsEntry', 'Tipo', 'Ordem'])

def save_sequencia_data(df_sequencia):
    """
    Salva o DataFrame de sequência de separação no arquivo Parquet.
    """
    try:
        df_sequencia.to_parquet(SEQUENCIA_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo de sequência: {e}")
        return False