# data/packing_repository.py

import os
import pandas as pd

PACKING_PARQUET_PATH = os.getenv('RIOFER_PACKING_SGD', 'packing.parquet')

def get_packing_data():
    """
    Lê os dados de packing finalizado do arquivo parquet.
    Retorna um DataFrame com a estrutura mínima se o arquivo não existir.
    """
    default_cols = ['AbsEntry', 'Localizacao'] # Adicione outras colunas se houver um padrão
    
    if not os.path.exists(PACKING_PARQUET_PATH):
        return pd.DataFrame(columns=default_cols)
    try:
        return pd.read_parquet(PACKING_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de packing: {e}")
        return pd.DataFrame(columns=default_cols)

def save_packing_data(df_packing_final):
    """
    Salva o DataFrame final de packing no arquivo parquet.
    Substitui o conteúdo anterior.
    """
    try:
        df_packing_final.to_parquet(PACKING_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo de packing: {e}")
        return False