import requests
import pandas as pd
import time
import os

# --- Configuración ---
API_URL = "https://d3e6htiiul5ek9.cloudfront.net/prod/productos"
OUTPUT_FILE = "base_de_productos.xlsx"
# Ahora los caracteres base para generar combinaciones
BASE_CHARS = 'abcdefghijklmnopqrstuvwxyz0123456789'
SLEEP_TIME = 1.5 
LATITUD = -34.6037
LONGITUD = -58.3816
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def build_product_database():
    """
    Función principal para scrapear la API de Precios Claros y construir
    una base de datos de productos en un archivo Excel, usando combinaciones de 2 caracteres.
    """
    
    productos_unicos = {}

    if os.path.exists(OUTPUT_FILE):
        print(f"Encontrado archivo existente '{OUTPUT_FILE}'. Cargando datos para continuar...")
        try:
            df_existente = pd.read_excel(OUTPUT_FILE)
            for index, row in df_existente.iterrows():
                ean = str(row['ean'])
                productos_unicos[ean] = {
                    'nombre': row['nombre'],
                    'marca': row['marca'],
                    'imagen_url': row['imagen_url']
                }
            print(f"Cargados {len(productos_unicos)} productos únicos. Reanudando el proceso...")
        except Exception as e:
            print(f"Error al cargar el archivo existente: {e}. Empezando desde cero.")

    # --- BUCLE MODIFICADO: AHORA ITERAMOS SOBRE COMBINACIONES DE DOS CARACTERES ---
    for char1 in BASE_CHARS:
        for char2 in BASE_CHARS:
            combo = char1 + char2
            offset = 0
            has_more_pages = True
            
            print(f"\n--- Buscando productos que contienen la combinación '{combo.upper()}' ---")

            while has_more_pages:
                params = {
                    'string': combo,
                    'lat': LATITUD,
                    'lng': LONGITUD,
                    'limit': 50,
                    'offset': offset
                }
                
                try:
                    response = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
                    response.raise_for_status() 
                    
                    data = response.json()
                    
                    if 'productos' not in data or not data['productos']:
                        has_more_pages = False
                    else:
                        for producto in data['productos']:
                            ean = str(producto.get('id'))
                            
                            if ean not in productos_unicos:
                                productos_unicos[ean] = {
                                    'nombre': producto.get('nombre'),
                                    'marca': producto.get('marca'),
                                    'imagen_url': producto.get('presentacion')
                                }
                        
                        print(f"Combinación '{combo.upper()}' | Página: {offset // 50 + 1} | Productos únicos totales: {len(productos_unicos)}")
                        
                        offset += 50
                        
                        save_to_excel(productos_unicos)

                except requests.exceptions.RequestException as e:
                    print(f"Error de red: {e}. Reintentando en 5 segundos...")
                    time.sleep(5)
                    continue

                time.sleep(SLEEP_TIME)

    print("\n--- Proceso completado ---")
    print(f"Se ha creado el archivo '{OUTPUT_FILE}' con {len(productos_unicos)} productos únicos.")

def save_to_excel(productos_dict):
    """
    Convierte el diccionario de productos a un DataFrame de pandas y lo guarda en un archivo Excel.
    """
    lista_para_df = []
    for ean, detalles in productos_dict.items():
        lista_para_df.append({
            'ean': ean,
            'nombre': detalles['nombre'],
            'marca': detalles['marca'],
            'imagen_url': detalles['imagen_url']
        })
        
    df = pd.DataFrame(lista_para_df)
    df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')

if __name__ == "__main__":
    build_product_database()