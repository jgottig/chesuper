import requests
import pandas as pd
import time
import os
import unicodedata # Librería para manejar caracteres Unicode (acentos)

# --- Configuración ---
API_URL = "https://d3e6htiiul5ek9.cloudfront.net/prod/productos"
OUTPUT_FILE = "base_de_productos_rosario.xlsx"
BASE_CHARS = 'abcdefghijklmnopqrstuvwxyz0123456789'
SLEEP_TIME = 1.5 
LATITUD = -32.9478
LONGITUD = -60.6305
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

# --- ¡NUEVO! Función para Normalizar Texto (quitar acentos y convertir a minúsculas) ---
def normalizar_texto(texto):
    """
    Convierte un texto a minúsculas y elimina los acentos.
    Ej: "Azúcar" -> "azucar"
    """
    if not isinstance(texto, str):
        return ""
    # Descompone los caracteres en su forma base y un modificador (ej. 'á' -> 'a' + ´)
    # y luego filtra los que no son 'Spacing Mark' (los acentos)
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

# --- ¡MODIFICADO! Diccionario de Reglas con Palabras Clave Normalizadas ---
# Añadimos sinónimos y nos aseguramos de que no tengan acentos.
CATEGORIAS_PALABRAS_CLAVE = {
    "Almacén": ['aceite', 'vinagre', 'arroz', 'fideo', 'harina', 'azucar', 'sal', 'yerba', 'mate', 'te', 'cafe', 'cacao', 'mermelada', 'dulce de leche', 'galletita', 'legumbre', 'lenteja', 'garbanzo', 'poroto', 'enlatado', 'atun', 'sardina', 'choclo', 'arveja', 'salsa', 'pure de tomate', 'mayonesa', 'ketchup', 'mostaza'],
    "Lácteos y Frescos": ['leche', 'yogur', 'queso', 'crema', 'manteca', 'postre', 'flan', 'ricota', 'fiambre', 'jamon', 'salame', 'pascualina', 'tapa empanada'],
    "Panificados": ['pan', 'pan lactal', 'budin', 'magdalena', 'factura', 'bizcocho'],
    "Bebidas": ['gaseosa', 'agua', 'jugo', 'bebida', 'cerveza', 'vino', 'fernet', 'aperitivo', 'isotonica'],
    "Limpieza": ['lavandina', 'detergente', 'limpiador', 'desengrasante', 'jabon en polvo', 'jabon liquido', 'suavizante', 'lustramuebles', 'insecticida', 'papel higienico', 'rollo de cocina', 'servilleta', 'bolsa de residuo'],
    "Higiene y Cuidado Personal": ['jabon de tocador', 'shampoo', 'acondicionador', 'crema de enjuague', 'desodorante', 'talco', 'protector solar', 'repelente', 'toalla femenina', 'pañal', 'crema dental', 'pasta dental', 'dentifrico', 'cepillo de diente', 'enjuague bucal', 'maquina de afeitar', 'espuma de afeitar', 'preservativo'],
    "Snacks y Golosinas": ['papas fritas', 'snack', 'mani', 'palitos salados', 'chupetin', 'caramelo', 'chocolate', 'alfajor', 'turron', 'chicle'],
    "Electrodomésticos": ['tv', 'televisor', 'smart', 'heladera', 'lavarropas', 'cocina', 'horno', 'microondas', 'pava', 'cafetera', 'licuadora', 'plancha', 'secarropas', 'calefon', 'termotanque', 'a.a', 'aire acondicionado'],
}

def asignar_categoria(nombre_producto):
    """
    Asigna una categoría a un producto usando normalización de texto.
    """
    # Normalizamos el nombre del producto UNA SOLA VEZ
    nombre_normalizado = normalizar_texto(nombre_producto)
    
    for categoria, palabras in CATEGORIAS_PALABRAS_CLAVE.items():
        # Comparamos el nombre normalizado con las palabras clave (que ya están normalizadas)
        if any(palabra in nombre_normalizado for palabra in palabras):
            return categoria
    return "Otros" 

# --------------------------------------------------------------------

def build_product_database():
    productos_unicos = {}
    if os.path.exists(OUTPUT_FILE):
        # ... (el código de carga de archivo no cambia) ...
        print(f"Encontrado archivo existente '{OUTPUT_FILE}'. Cargando datos...")
        try:
            df_existente = pd.read_excel(OUTPUT_FILE)
            for index, row in df_existente.iterrows():
                ean = str(row['ean'])
                productos_unicos[ean] = {
                    'nombre': row['nombre'],
                    'marca': row['marca'],
                    'imagen_url': row['imagen_url'],
                    'Categoria': row.get('Categoria', '')
                }
            print(f"Cargados {len(productos_unicos)} productos. Reanudando...")
        except Exception as e:
            print(f"Error al cargar: {e}. Empezando de cero.")

    for char1 in BASE_CHARS:
        for char2 in BASE_CHARS:
            # ... (el resto del bucle principal no cambia) ...
            combo = char1 + char2
            offset = 0
            has_more_pages = True
            
            print(f"\n--- Buscando productos con '{combo.upper()}' en Rosario ---")
            while has_more_pages:
                params = {'string': combo, 'lat': LATITUD, 'lng': LONGITUD, 'limit': 50, 'offset': offset}
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
                                nombre_prod = producto.get('nombre', '')
                                imagen_url = f"https://imagenes.preciosclaros.gob.ar/productos/{ean}.jpg"
                                # --- ¡Llamada a la nueva función de categorización! ---
                                categoria_asignada = asignar_categoria(nombre_prod)
                                # --------------------------------------------------
                                productos_unicos[ean] = {
                                    'nombre': nombre_prod,
                                    'marca': producto.get('marca'),
                                    'imagen_url': imagen_url,
                                    'Categoria': categoria_asignada
                                }
                        
                        print(f"'{combo.upper()}' | Pág: {offset // 50 + 1} | Prods: {len(productos_unicos)}")
                        offset += 50
                        save_to_excel(productos_unicos)
                except requests.exceptions.RequestException as e:
                    print(f"Error de red: {e}. Reintentando...")
                    time.sleep(5)
                    continue
                time.sleep(SLEEP_TIME)
    print("\n--- Proceso completado ---")

def save_to_excel(productos_dict):
    lista_para_df = []
    for ean, detalles in productos_dict.items():
        lista_para_df.append({
            'ean': ean,
            'nombre': detalles['nombre'],
            'marca': detalles['marca'],
            'imagen_url': detalles['imagen_url'],
            'Categoria': detalles.get('Categoria', 'Otros')
        })
    df = pd.DataFrame(lista_para_df)
    df = df[['ean', 'nombre', 'marca', 'imagen_url', 'Categoria']]
    df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')

if __name__ == "__main__":
    build_product_database()