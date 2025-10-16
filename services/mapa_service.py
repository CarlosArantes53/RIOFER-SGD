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

        endereco_parts = [
            clean_value(pedido_info.get('U_GI_Rua', '')),
            clean_value(pedido_info.get('U_GI_NumRua', '')),
            clean_value(pedido_info.get('U_GI_Bairro', '')),
            clean_value(pedido_info.get('U_GI_Cidade', '')),
            clean_value(pedido_info.get('U_GI_Estado', ''))
        ]
        
        endereco = ", ".join([p for p in endereco_parts if p])

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
    df_picking = pedidos_repository.get_picking_data()
    pedido = df_picking[df_picking['AbsEntry'] == abs_entry].iloc[0]
    
    rua = str(pedido.get('U_GI_Rua', '')).strip()
    numero = str(pedido.get('U_GI_NumRua', '')).strip()
    bairro = str(pedido.get('U_GI_Bairro', '')).strip()
    cidade = str(pedido.get('U_GI_Cidade', '')).strip()
    estado = str(pedido.get('U_GI_Estado', '')).strip().upper()
    
    rua = '' if rua.lower() == 'nan' else rua
    numero = '' if numero.lower() == 'nan' else numero
    bairro = '' if bairro.lower() == 'nan' else bairro
    cidade = '' if cidade.lower() == 'nan' else cidade
    estado = '' if estado.lower() == 'nan' else estado
    
    headers = {
        'User-Agent': 'RioferSGD/1.0 tecnologia@riofer.com.br'
    }
    
    search_strategies = []
    
    if rua and numero and cidade and estado:
        params = {'street': f"{numero} {rua}", 'city': cidade, 'state': estado}
        if bairro:
            params['county'] = bairro
        search_strategies.append({
            'params': params,
            'description': 'endereço completo com número'
        })
    
    if rua and bairro and cidade and estado:
        search_strategies.append({
            'params': {'street': rua, 'county': bairro, 'city': cidade, 'state': estado},
            'description': 'endereço com bairro sem número'
        })
    
    if rua and cidade and estado:
        search_strategies.append({
            'params': {'street': rua, 'city': cidade, 'state': estado},
            'description': 'rua e cidade'
        })
    
    if bairro and cidade and estado:
        search_strategies.append({
            'params': {'county': bairro, 'city': cidade, 'state': estado},
            'description': 'bairro e cidade'
        })
    
    if cidade and estado:
        search_strategies.append({
            'params': {'city': cidade, 'state': estado},
            'description': 'cidade e estado'
        })
    
    for strategy in search_strategies:
        request_params = strategy['params'].copy()
        description = strategy['description']

        request_params.update({
            'format': 'json',
            'limit': 1,
            'countrycodes': 'br',
            'addressdetails': 1
        })
        
        url = "https://nominatim.openstreetmap.org/search"
        
        query_log = "; ".join([f"{k}: {v}" for k, v in strategy['params'].items()])
        current_app.logger.info(f"Tentando geolocalização para AbsEntry {abs_entry} - {description}: {query_log}")
        
        try:
            time.sleep(1)
            
            response = requests.get(url, params=request_params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                result = data[0]
                lat = result['lat']
                lon = result['lon']
                display_name = result.get('display_name', '')
                
                current_app.logger.info(
                    f"Geolocalização encontrada para AbsEntry {abs_entry} "
                    f"usando {description}: {display_name}"
                )
                
                geoloc_repository.update_geolocation(abs_entry, lat, lon)
                
                return {
                    'status': 'success',
                    'lat': lat,
                    'lon': lon,
                    'display_name': display_name,
                    'strategy': description
                }
        
        except requests.RequestException as e:
            current_app.logger.error(
                f"Erro na API Nominatim para AbsEntry {abs_entry} "
                f"usando {description}: {e}"
            )
            continue
    
    current_app.logger.warning(
        f"Não foi possível encontrar geolocalização para AbsEntry {abs_entry} "
        f"após tentar todas as estratégias"
    )
    
    return {
        'status': 'not_found',
        'message': 'Localização não encontrada após tentar múltiplas estratégias de busca'
    }