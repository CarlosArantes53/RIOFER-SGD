import os
import pandas as pd

# Define o caminho para o novo arquivo Parquet
GEOLOC_PARQUET_PATH = os.getenv('RIOFER_GEOLOC_SGD', 'geolocations.parquet')

def get_geoloc_data():
    """Lê os dados de geolocalização personalizados."""
    if not os.path.exists(GEOLOC_PARQUET_PATH):
        return pd.DataFrame(columns=['AbsEntry', 'U_SPS_Latitude', 'U_SPS_Longitude'])
    try:
        return pd.read_parquet(GEOLOC_PARQUET_PATH)
    except Exception:
        return pd.DataFrame(columns=['AbsEntry', 'U_SPS_Latitude', 'U_SPS_Longitude'])

def save_geoloc_data(df_geoloc):
    """Salva o DataFrame de geolocalizações no arquivo Parquet."""
    try:
        df_geoloc.to_parquet(GEOLOC_PARQUET_PATH, index=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo de geolocalização: {e}")
        return False

def update_geolocation(abs_entry, latitude, longitude):
    """Adiciona ou atualiza a geolocalização para um pedido específico."""
    df_geoloc = get_geoloc_data()
    
    # Remove qualquer entrada antiga para este AbsEntry para evitar duplicatas
    df_geoloc = df_geoloc[df_geoloc['AbsEntry'] != abs_entry]
    
    # Cria um novo DataFrame com os novos dados
    new_data = pd.DataFrame([{
        'AbsEntry': abs_entry,
        'U_SPS_Latitude': latitude,
        'U_SPS_Longitude': longitude
    }])
    
    # Concatena o DataFrame existente com os novos dados
    df_final = pd.concat([df_geoloc, new_data], ignore_index=True)
    
    return save_geoloc_data(df_final)