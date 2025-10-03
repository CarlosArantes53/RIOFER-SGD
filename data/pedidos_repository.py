# data/pedidos_repository.py

import os
import pandas as pd

# As variáveis de ambiente com os caminhos dos arquivos são a fonte da verdade.
PICKING_PARQUET_PATH = os.getenv('RIOFER_PICKING_SGD')
PACOTES_PARQUET_PATH = os.getenv('RIOFER_PACOTES_SGD', 'pacotes.parquet')

def get_picking_data():
    """
    Lê os dados brutos de picking do arquivo parquet.
    Retorna um DataFrame vazio se o arquivo não for encontrado.
    """
    if not PICKING_PARQUET_PATH or not os.path.exists(PICKING_PARQUET_PATH):
        print("Aviso: Arquivo de picking não encontrado.")
        return pd.DataFrame()
    try:
        return pd.read_parquet(PICKING_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de picking: {e}")
        return pd.DataFrame()

def get_pacotes_data():
    """
    Lê os dados de pacotes do arquivo parquet.
    Retorna um DataFrame vazio se o arquivo não existir.
    """
    if not os.path.exists(PACOTES_PARQUET_PATH):
        return pd.DataFrame()
    try:
        return pd.read_parquet(PACOTES_PARQUET_PATH)
    except Exception as e:
        print(f"Erro ao ler o arquivo de pacotes: {e}")
        return pd.DataFrame()

def save_pacotes_data(df_pacotes_final):
    """
    Salva o DataFrame final de pacotes no arquivo parquet.
    Substitui o conteúdo anterior.
    """
    try:
        df_pacotes_final.to_parquet(PACOTES_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo de pacotes: {e}")
        return False