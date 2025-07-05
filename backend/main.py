# backend/main.py (Migrado a Supabase)

import pandas as pd
import math
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from .database_service import db_service

# --- INICIALIZACIÓN ---
app = FastAPI(title="API de Che Súper!")

@app.on_event("startup")
def load_data():
    try:
        print("🔗 Conectando a base de datos Supabase...")
        # Test database connection
        categorias = db_service.get_categorias()
        if categorias:
            print(f"✅ Conexión exitosa! Encontradas {len(categorias)} categorías")
        else:
            print("⚠️ Conexión establecida pero sin datos de categorías")
        print("¡Base de datos lista para usar!")
    except Exception as e:
        print(f"❌ ERROR CRÍTICO! No se pudo conectar a la base de datos: {e}")

@app.on_event("shutdown")
def shutdown_event():
    """Close database connections on shutdown."""
    db_service.close_session()

# --- MIDDLEWARE ---
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- MODELOS DE DATOS ---
class CartItem(BaseModel):
    ean: str
    quantity: int

class ComparisonRequest(BaseModel):
    items: List[CartItem]
    use_promos: bool

# --- ENDPOINTS ---
@app.get("/", summary="Ruta raíz para chequear API")
def root():
    return {"mensaje": "API Che Súper funcionando correctamente."}

@app.get("/api/categorias", summary="Obtiene la lista de categorías únicas")
def get_categorias():
    try:
        categorias = db_service.get_categorias()
        return categorias
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo categorías: {str(e)}")

@app.get("/api/productos", summary="Obtiene una lista paginada de productos con sus banderas")
def get_productos(q: str = None, categoria: str = None, min_supermercados: int = 1, page: int = 1, limit: int = 24):
    try:
        # Use database service instead of in-memory DataFrames
        result = db_service.get_productos_with_banderas(
            q=q, 
            categoria=categoria, 
            min_supermercados=min_supermercados, 
            page=page, 
            limit=limit
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo productos: {str(e)}")

@app.post("/api/comparar", summary="Compara un carrito y devuelve los totales y detalles de precios")
def comparar_carrito(request: ComparisonRequest):
    try:
        # Get precios for the requested EANs
        eans_list = [item.ean for item in request.items]
        precios_df = db_service.get_precios_for_comparison(eans_list)
        
        if precios_df.empty:
            return {"comparativa": [], "promo_inicial_activada": request.use_promos}
        
        banderas_unicas = precios_df['bandera'].dropna().unique()
        resultados_finales = []
        todos_los_eans_del_carrito = {item.ean for item in request.items}
        
        for bandera in banderas_unicas:
            total_inicial, items_encontrados, detalle_productos, productos_no_encontrados = 0.0, 0, [], []
            eans_encontrados_en_bandera = set()
            
            for item in request.items:
                precios_producto = precios_df[(precios_df['ean'] == item.ean) & (precios_df['bandera'] == bandera)]
                if precios_producto.empty: 
                    continue
                
                eans_encontrados_en_bandera.add(item.ean)
                precio_lista_final = precios_producto['precio_lista'].min()
                precio_promo_a_final = precios_producto['precio_promo_a'].min()
                
                if not pd.notna(precio_lista_final): 
                    continue
                if not pd.notna(precio_promo_a_final): 
                    precio_promo_a_final = None
                
                precio_a_usar = precio_lista_final
                if request.use_promos and precio_promo_a_final is not None:
                    precio_a_usar = precio_promo_a_final
                
                items_encontrados += 1
                total_inicial += precio_a_usar * item.quantity
                
                # Get product info
                producto_info = db_service.get_producto_info(item.ean)
                detalle_productos.append({
                    'nombre': producto_info['nombre'], 
                    'ean': item.ean, 
                    'quantity': item.quantity,
                    'precio_lista': precio_lista_final, 
                    'precio_promo_a': precio_promo_a_final
                })
            
            eans_faltantes = todos_los_eans_del_carrito - eans_encontrados_en_bandera
            for ean_faltante in eans_faltantes:
                producto_info = db_service.get_producto_info(ean_faltante)
                productos_no_encontrados.append({'nombre': producto_info['nombre']})
            
            if items_encontrados > 0:
                resultados_finales.append({
                    'bandera': bandera, 
                    'total_inicial': round(total_inicial, 2),
                    'items_encontrados': items_encontrados, 
                    'items_faltantes': len(eans_faltantes),
                    'detalle': detalle_productos, 
                    'no_encontrados': productos_no_encontrados
                })
                
        resultados_finales.sort(key=lambda x: x['total_inicial'])
        resultados_limitados = resultados_finales[:4]
        
        return {"comparativa": resultados_limitados, "promo_inicial_activada": request.use_promos}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparando carrito: {str(e)}")

@app.post("/api/optimizar", summary="Calcula la mejor combinación de compra en dos supermercados")
def optimizar_carrito(request: ComparisonRequest):
    try:
        # Get precios for the requested EANs
        eans_list = [item.ean for item in request.items]
        precios_df = db_service.get_precios_for_comparison(eans_list)
        
        if precios_df.empty:
            return {"total_optimizado": 0.0, "canastas": []}
        
        precios_optimos = {}
        
        # 1. Para cada producto, encontrar todos sus precios (lista y promo) por supermercado
        for item in request.items:
            precios_producto = precios_df[precios_df['ean'] == item.ean].copy()
            if precios_producto.empty: 
                continue

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
                if not pd.notna(precio_promo_a_final): 
                    precio_promo_a_final = None

                precio_a_usar = precio_lista_final
                if request.use_promos and precio_promo_a_final is not None:
                    precio_a_usar = precio_promo_a_final
                
                total_canasta += precio_a_usar * item_original.quantity
                
                # Get product info
                producto_info = db_service.get_producto_info(ean)
                
                detalle_canasta.append({
                    'nombre': producto_info['nombre'], 
                    'quantity': item_original.quantity,
                    'ean': ean,
                    'precio_lista': precio_lista_final,
                    'precio_promo_a': precio_promo_a_final
                })
            
            resultado_optimizado.append({
                'bandera': super, 
                'total_canasta': round(total_canasta, 2), 
                'detalle': detalle_canasta
            })
            total_compra_optimizada += total_canasta

        return {"total_optimizado": round(total_compra_optimizada, 2), "canastas": resultado_optimizado}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizando carrito: {str(e)}")

# --- Bloque de ejecución directa ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
