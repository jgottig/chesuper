# backend/main.py (Versión Final Completa y Verificada)

import pandas as pd
import math
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# --- INICIALIZACIÓN Y CARGA DE DATOS ---
app = FastAPI(
    title="API de Che Súper!",
    description="El cerebro que alimenta nuestro ecommerce de comparación."
)
database = {"productos_df": None, "precios_df": None}

@app.on_event("startup")
def load_data():
    """Carga los datos de los archivos Excel al iniciar el servidor."""
    try:
        print("Cargando base de datos de productos...")
        productos_df = pd.read_excel("base_de_productos_rosario.xlsx")
        productos_df['ean'] = productos_df['ean'].astype(str)
        productos_df.fillna({'Categoria': 'Otros', 'marca': 'Sin Marca', 'nombre': 'Sin Nombre'}, inplace=True)
        database["productos_df"] = productos_df
        
        print("Cargando base de datos de precios...")
        precios_df = pd.read_excel("precios_obtenidos_rosario.xlsx")
        precios_df['ean'] = precios_df['ean'].astype(str)
        precios_df['bandera'] = precios_df['sucursal'].apply(lambda x: x.split(' - ')[0] if isinstance(x, str) and ' - ' in x else x)
        database["precios_df"] = precios_df
        
        print("¡Bases de datos cargadas con éxito!")
    except FileNotFoundError as e:
        print(f"¡ERROR CRÍTICO! No se encontró el archivo: {e.filename}. El servidor fallará.")

# --- MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class CartItem(BaseModel):
    ean: str
    quantity: int

class ComparisonRequest(BaseModel):
    items: List[CartItem]
    use_promos: bool

# --- FUNCIONES DE AYUDA ---
def check_db_loaded():
    if database["productos_df"] is None or database["precios_df"] is None:
        raise HTTPException(status_code=503, detail="Los datos del servidor no están listos.")

# --- ENDPOINTS ---

@app.get("/api/categorias", summary="Obtiene la lista de categorías únicas")
def get_categorias():
    check_db_loaded()
    categorias = database["productos_df"]['Categoria'].dropna().unique().tolist()
    if 'Otros' in categorias:
        categorias.remove('Otros')
        return sorted(categorias) + ['Otros']
    return sorted(categorias)

@app.get("/api/productos", summary="Obtiene una lista paginada de productos")
def get_productos(
    q: str = None, categoria: str = None, min_supermercados: int = 1, page: int = 1, limit: int = 24
):
    check_db_loaded()
    productos_df = database["productos_df"].copy()
    precios_df = database["precios_df"].copy()
    if min_supermercados > 1:
        conteo_banderas_por_ean = precios_df.groupby('ean')['bandera'].nunique()
        eans_filtrados = conteo_banderas_por_ean[conteo_banderas_por_ean >= min_supermercados].index.tolist()
        productos_df = productos_df[productos_df['ean'].isin(eans_filtrados)]
    
    total_productos_disponibles = len(productos_df)

    if categoria:
        productos_df = productos_df[productos_df['Categoria'].str.lower() == categoria.lower()]
        total_productos_disponibles = len(productos_df)
    
    if q:
        q_lower = q.lower()
        df_filtrado_por_busqueda = productos_df[productos_df.apply(lambda row: q_lower in str(row['nombre']).lower() or q_lower in str(row['marca']).lower(), axis=1)]
        total_productos_disponibles = len(df_filtrado_por_busqueda)
        productos_df = df_filtrado_por_busqueda
    
    total_paginas = math.ceil(total_productos_disponibles / limit)
    start_index = (page - 1) * limit
    end_index = start_index + limit
    paginated_products = productos_df.iloc[start_index:end_index]
    
    return {
        "productos": paginated_products.to_dict('records'),
        "pagina_actual": page,
        "total_paginas": total_paginas,
        "total_productos_disponibles": total_productos_disponibles
    }

@app.post("/api/comparar", summary="Compara un carrito y devuelve los totales y detalles de precios")
def comparar_carrito(request: ComparisonRequest):
    check_db_loaded()
    precios_df = database["precios_df"]
    productos_df = database["productos_df"]
    banderas_unicas = precios_df['bandera'].dropna().unique()
    resultados_finales = []
    todos_los_eans_del_carrito = {item.ean for item in request.items}
    
    for bandera in banderas_unicas:
        total_inicial, items_encontrados, detalle_productos, productos_no_encontrados = 0.0, 0, [], []
        eans_encontrados_en_bandera = set()
        
        for item in request.items:
            precios_producto = precios_df[(precios_df['ean'] == item.ean) & (precios_df['bandera'] == bandera)]
            if precios_producto.empty: continue
            
            eans_encontrados_en_bandera.add(item.ean)
            precio_lista_final = precios_producto['precio_lista'].min()
            precio_promo_a_final = precios_producto['precio_promo_a'].min()
            
            if not pd.notna(precio_lista_final): continue
            if not pd.notna(precio_promo_a_final): precio_promo_a_final = None
            
            precio_a_usar = precio_lista_final
            if request.use_promos and precio_promo_a_final is not None:
                precio_a_usar = precio_promo_a_final
            
            items_encontrados += 1
            total_inicial += precio_a_usar * item.quantity
            producto_info = productos_df.loc[productos_df['ean'] == item.ean].iloc[0]
            detalle_productos.append({
                'nombre': producto_info['nombre'], 'ean': item.ean, 'quantity': item.quantity,
                'precio_lista': precio_lista_final, 'precio_promo_a': precio_promo_a_final
            })
        
        eans_faltantes = todos_los_eans_del_carrito - eans_encontrados_en_bandera
        for ean_faltante in eans_faltantes:
            producto_info = productos_df.loc[productos_df['ean'] == ean_faltante].iloc[0]
            productos_no_encontrados.append({'nombre': producto_info['nombre']})
        
        if items_encontrados > 0:
            resultados_finales.append({
                'bandera': bandera, 'total_inicial': round(total_inicial, 2),
                'items_encontrados': items_encontrados, 'items_faltantes': len(eans_faltantes),
                'detalle': detalle_productos, 'no_encontrados': productos_no_encontrados
            })
            
    resultados_finales.sort(key=lambda x: x['total_inicial'])
    resultados_limitados = resultados_finales[:4]
    
    return {"comparativa": resultados_limitados, "promo_inicial_activada": request.use_promos}

@app.post("/api/optimizar", summary="Calcula la mejor combinación de compra en dos supermercados")
def optimizar_carrito(request: ComparisonRequest):
    check_db_loaded()
    precios_df = database["precios_df"]
    productos_df = database["productos_df"]
    
    precios_optimos = {}
    
    # 1. Para cada producto, encontrar todos sus precios (lista y promo) por supermercado
    for item in request.items:
        precios_producto = precios_df[precios_df['ean'] == item.ean].copy()
        if precios_producto.empty: continue

        mejores_precios = precios_producto.groupby('bandera').agg(
            precio_lista=('precio_lista', 'min'),
            precio_promo_a=('precio_promo_a', 'min')
        ).dropna(subset=['precio_lista']).to_dict('index')
        
        if mejores_precios:
            precios_optimos[item.ean] = mejores_precios

    # 2. Lógica de optimización: encontrar el súper más barato para cada producto
    canastas = {}
    for ean, precios_por_super in precios_optimos.items():
        mejor_opcion_para_producto = None
        precio_mas_bajo = float('inf')

        for super, precios in precios_por_super.items():
            precio_a_usar = precios['precio_lista']
            if request.use_promos and pd.notna(precios['precio_promo_a']):
                precio_a_usar = precios['precio_promo_a']
            
            if pd.notna(precio_a_usar) and precio_a_usar < precio_mas_bajo:
                precio_mas_bajo = precio_a_usar
                mejor_opcion_para_producto = super
        
        if mejor_opcion_para_producto:
            if mejor_opcion_para_producto not in canastas:
                canastas[mejor_opcion_para_producto] = []
            canastas[mejor_opcion_para_producto].append(ean)

    # 3. Consolidar si hay más de 2 canastas (lógica simplificada)
    if len(canastas) > 2:
        # Una estrategia simple: mantener las dos canastas con más productos
        canastas_ordenadas = sorted(canastas.items(), key=lambda item: len(item[1]), reverse=True)
        canastas_principales = dict(canastas_ordenadas[:2])
        
        # Reasignar los productos de las canastas restantes
        for super_descartado, eans_descartados in canastas_ordenadas[2:]:
            for ean in eans_descartados:
                # Encontrar el segundo mejor precio entre las canastas principales
                mejor_destino = None
                menor_precio_en_principales = float('inf')
                for super_principal in canastas_principales:
                    if super_principal in precios_optimos[ean]:
                        precio_actual = precios_optimos[ean][super_principal]['precio_lista']
                        if request.use_promos and pd.notna(precios_optimos[ean][super_principal]['precio_promo_a']):
                            precio_actual = precios_optimos[ean][super_principal]['precio_promo_a']
                        
                        if precio_actual < menor_precio_en_principales:
                            menor_precio_en_principales = precio_actual
                            mejor_destino = super_principal
                
                if mejor_destino:
                    canastas_principales[mejor_destino].append(ean)
        
        canastas = canastas_principales

    # 4. Formatear la respuesta final
    resultado_optimizado = []
    total_compra_optimizada = 0
    
    for super, eans in canastas.items():
        detalle_canasta, total_canasta = [], 0
        for ean in eans:
            item_original = next(i for i in request.items if i.ean == ean)
            
            precios_reales = precios_optimos[ean][super]
            precio_lista_final = precios_reales['precio_lista']
            precio_promo_a_final = precios_reales.get('precio_promo_a')
            if not pd.notna(precio_promo_a_final): precio_promo_a_final = None

            precio_a_usar = precio_lista_final
            if request.use_promos and precio_promo_a_final is not None:
                precio_a_usar = precio_promo_a_final
            
            total_canasta += precio_a_usar * item_original.quantity
            producto_info = productos_df.loc[productos_df['ean'] == ean].iloc[0]
            
            detalle_canasta.append({
                'nombre': producto_info['nombre'], 'quantity': item_original.quantity,
                'ean': ean,
                'precio_lista': precio_lista_final,
                'precio_promo_a': precio_promo_a_final
            })
        
        resultado_optimizado.append({'bandera': super, 'total_canasta': round(total_canasta, 2), 'detalle': detalle_canasta})
        total_compra_optimizada += total_canasta

    return {"total_optimizado": round(total_compra_optimizada, 2), "canastas": resultado_optimizado}

# --- Bloque de ejecución directa ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)