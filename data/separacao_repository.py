# data/separacao_repository.py

import os
import pandas as pd

SEPARACAO_PARQUET_PATH = os.getenv('RIOFER_SEPARACAO_SGD', 'separacao.parquet')

def get_separacao_data():
    """
    Lê os dados de log de separação do arquivo parquet.
    Cria e retorna um DataFrame com a estrutura padrão se o arquivo não existir.
    """
    default_cols = ['AbsEntry', 'Localizacao', 'User', 'StartTime', 'EndTime', 'DiscrepancyLog', 'DiscrepancyReport']
    
    if not os.path.exists(SEPARACAO_PARQUET_PATH):
        return pd.DataFrame(columns=default_cols)
    
    try:
        df = pd.read_parquet(SEPARACAO_PARQUET_PATH)
        # Garante que colunas adicionadas em versões mais recentes existam
        for col in default_cols:
            if col not in df.columns:
                df[col] = '' if col != 'AbsEntry' else 0 # Garante tipo correto para AbsEntry se precisar
        return df
    except Exception as e:
        print(f"Erro ao ler o arquivo de separação: {e}")
        return pd.DataFrame(columns=default_cols)

def save_separacao_data(df_separacao_final):
    """
    Salva o DataFrame final de separação no arquivo parquet.
    Substitui o conteúdo anterior.
    """
    try:
        df_separacao_final.to_parquet(SEPARACAO_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo de separação: {e}")
        return False