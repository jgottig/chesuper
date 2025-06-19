import requests
import pandas as pd
import time
import os
from datetime import datetime

# --- Configuración ---
PRODUCTOS_FILE = "base_de_productos_rosario.xlsx"
PRECIOS_FILE = "precios_obtenidos_rosario.xlsx"
PRODUCTO_API_URL = "https://d3e6htiiul5ek9.cloudfront.net/prod/producto"

# --- STRING DE SUCURSALES (YA CONFIGURADO) ---
ARRAY_SUCURSALES_ROSARIO = "2002-1-38,22-1-31,22-1-3,2002-1-67,22-1-17,22-1-20,12-1-97,22-1-18,12-1-99,22-1-6,23-1-6260,22-1-16,22-1-24,22-1-1,10-1-268,10-1-33,23-1-6262,10-1-32,2002-1-101,12-1-95,12-1-165,23-1-6256,22-1-26,2002-1-166,2002-1-6,9-3-5218,10-1-41,16-1-1202,23-1-6264,22-1-5"
# ---------------------------------------------

SLEEP_TIME = 1.0
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def get_prices_for_all_products():
    """
    Script final y corregido que obtiene los precios para una lista de EANs.
    """
    # Cargar la lista de EANs
    try:
        df_productos = pd.read_excel(PRODUCTOS_FILE)
        eans_a_procesar = df_productos['ean'].astype(str).tolist()
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{PRODUCTOS_FILE}'.")
        return

    # Preparar para reanudar
    lista_de_precios = []
    eans_ya_procesados = set()
    if os.path.exists(PRECIOS_FILE):
        print(f"Cargando precios existentes desde '{PRECIOS_FILE}'...")
        df_precios_existente = pd.read_excel(PRECIOS_FILE)
        eans_ya_procesados = set(df_precios_existente['ean'].astype(str).unique())
        lista_de_precios = df_precios_existente.to_dict('records')
        print(f"Reanudando. {len(eans_ya_procesados)} EANs ya procesados.")

    # Iterar sobre cada EAN
    total_eans = len(eans_a_procesar)
    for i, ean in enumerate(eans_a_procesar):
        if ean in eans_ya_procesados:
            continue
            
        print(f"Procesando EAN {i+1}/{total_eans}: {ean}...")
        
        params = {
            'id_producto': ean,
            'array_sucursales': ARRAY_SUCURSALES_ROSARIO
        }
        
        try:
            response = requests.get(PRODUCTO_API_URL, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if 'sucursales' in data and data['sucursales']:
                sucursales_con_precio = 0
                for sucursal in data['sucursales']:
                    # --- ¡CORRECCIÓN CLAVE! ---
                    # 1. Verificamos que la sucursal tenga la clave 'preciosProducto'
                    # 2. Apuntamos a 'preciosProducto' para obtener los precios
                    if 'preciosProducto' in sucursal:
                        precios = sucursal['preciosProducto']
                        precio_info = {
                            'ean': data.get('producto', {}).get('id', ean),
                            'fecha_actualizacion': fecha_actual,
                            'supermercado': sucursal.get('comercioRazonSocial'),
                            'sucursal': f"{sucursal.get('banderaDescripcion')} - {sucursal.get('sucursalNombre')}",
                            'precio_lista': precios.get('precioLista'),
                            'precio_promo_a': precios.get('promo1', {}).get('precio'),
                            'precio_promo_b': precios.get('promo2', {}).get('precio')
                        }
                        lista_de_precios.append(precio_info)
                        sucursales_con_precio += 1
                
                if sucursales_con_precio > 0:
                    print(f"  -> ¡Éxito! Se encontraron precios en {sucursales_con_precio} sucursales.")
                else:
                    print(f"  -> Respuesta OK, pero el producto no está disponible en estas sucursales.")
            
            # Guardamos el progreso
            df_a_guardar = pd.DataFrame(lista_de_precios)
            if not df_a_guardar.empty:
                # Nos aseguramos de que no haya filas completamente duplicadas
                df_a_guardar.drop_duplicates(inplace=True)
                df_a_guardar.to_excel(PRECIOS_FILE, index=False, engine='openpyxl')

        except requests.exceptions.RequestException as e:
            print(f"  -> Error al procesar EAN {ean}: {e}. Continuando...")
        
        time.sleep(SLEEP_TIME)

    print("\n--- Proceso de obtención de precios completado ---")

if __name__ == "__main__":
    get_prices_for_all_products()