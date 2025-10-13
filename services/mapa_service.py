# mapa_service.py (apenas a função atualizada, mantenha o resto do arquivo)
import pandas as pd
import requests
import time
from data import pedidos_repository, separacao_repository, geoloc_repository
from flask import current_app

def get_entregas_para_mapa():
    df_picking = pedidos_repository.get_picking_data()
    df_separacao = separacao_repository.get_separacao_data()
    df_geoloc = geoloc_repository.get_geoloc_data()

    if df_picking.empty:
        return []

    df_entregas = df_picking[df_picking['U_TU_QuemEntrega'] != '02'].copy()

    # Sobrescreve as geolocalizações originais com as personalizadas/encontradas
    if not df_geoloc.empty:
        df_entregas.set_index('AbsEntry', inplace=True)
        df_geoloc.set_index('AbsEntry', inplace=True)
        df_entregas.update(df_geoloc)
        df_entregas.reset_index(inplace=True)

    pedidos_mapa = []
    pedidos_agrupados = df_entregas.groupby('AbsEntry')

    def clean_value(v):
        if pd.isna(v):
            return ''
        s = str(v).strip()
        return '' if s.lower() == 'nan' else s

    for abs_entry, group in pedidos_agrupados:
        pedido_info = group.iloc[0]
        lat = pd.to_numeric(pedido_info.get('U_SPS_Latitude'), errors='coerce')
        lon = pd.to_numeric(pedido_info.get('U_SPS_Longitude'), errors='coerce')
        has_valid_coords = pd.notna(lat) and pd.notna(lon) and lat != 0 and lon != 0

        status = 'Pendente'
        # ... (lógica de status que você já tinha)

        endereco_parts = [
            clean_value(pedido_info.get('U_GI_Rua', '')),
            clean_value(pedido_info.get('U_GI_NumRua', '')),
            clean_value(pedido_info.get('U_GI_Bairro', '')),
            clean_value(pedido_info.get('U_GI_Cidade', '')),
            clean_value(pedido_info.get('U_GI_Estado', ''))
        ]
        
        endereco = ", ".join([p for p in endereco_parts if p])

        # extrai cidade limpa
        cidade = clean_value(pedido_info.get('U_GI_Cidade', ''))

        pedidos_mapa.append({
            'AbsEntry': int(abs_entry),
            'CardName': pedido_info['CardName'],
            'Status': status,
            'Latitude': lat if has_valid_coords else None,
            'Longitude': lon if has_valid_coords else None,
            'Endereco': endereco,
            'GeoError': not has_valid_coords,
            'Cidade': cidade
        })
        
    return sorted(pedidos_mapa, key=lambda x: x['CardName'])


def find_and_save_geolocation(abs_entry):
    """Busca a geolocalização de um pedido usando a API Nominatim e salva o resultado."""
    df_picking = pedidos_repository.get_picking_data()
    pedido = df_picking[df_picking['AbsEntry'] == abs_entry].iloc[0]

    # Constrói a query de busca a partir do endereço
    # Formato "Rua, Cidade, Estado" é eficaz para o Nominatim
    query = f"{pedido.get('U_GI_Rua', '')}, {pedido.get('U_GI_Cidade', '')}, {pedido.get('U_GI_Estado', '')}"
    
    headers = {
        'User-Agent': 'RioferSGD/1.0 (seu-email@exemplo.com)' # É boa prática identificar sua aplicação
    }
    url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query)}&format=json&limit=1"

    # Respeita a política de uso da API (1 requisição por segundo)
    time.sleep(1) 

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data:
            lat = data[0]['lat']
            lon = data[0]['lon']
            # Salva no nosso arquivo parquet personalizado
            geoloc_repository.update_geolocation(abs_entry, lat, lon)
            return {'status': 'success', 'lat': lat, 'lon': lon}
        else:
            return {'status': 'not_found'}

    except requests.RequestException as e:
        current_app.logger.error(f"Erro na API Nominatim para AbsEntry {abs_entry}: {e}")
        return {'status': 'error', 'message': str(e)}