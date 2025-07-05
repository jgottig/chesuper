"""
Backend de CheSuper usando PostgreSQL (Supabase)
Versión migrada desde Excel a base de datos relacional
"""
import math
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

# Importar modelos y conexión de base de datos
from database.connection import get_db
from database.models import Producto, Supermercado, Precio

# --- INICIALIZACIÓN ---
app = FastAPI(title="API de Che Súper! - PostgreSQL")

# --- MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

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
    return {"mensaje": "API Che Súper funcionando correctamente con PostgreSQL."}

@app.get("/api/categorias", summary="Obtiene la lista de categorías únicas")
def get_categorias(db: Session = Depends(get_db)):
    """
    Obtiene todas las categorías únicas de productos
    """
    try:
        categorias = db.query(Producto.categoria).filter(
            Producto.categoria.isnot(None)
        ).distinct().all()
        
        categorias_list = [cat[0] for cat in categorias if cat[0]]
        
        # Mover 'Otros' al final si existe
        if 'Otros' in categorias_list:
            categorias_list.remove('Otros')
            return sorted(categorias_list) + ['Otros']
        
        return sorted(categorias_list)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo categorías: {str(e)}")

@app.get("/api/productos", summary="Obtiene una lista paginada de productos con sus supermercados")
def get_productos(
    q: Optional[str] = None, 
    categoria: Optional[str] = None, 
    min_supermercados: int = 1, 
    page: int = 1, 
    limit: int = 24,
    db: Session = Depends(get_db)
):
    """
    Obtiene productos con información de en qué supermercados están disponibles
    """
    try:
        # Query base para productos
        query = db.query(Producto)
        
        # Filtro por categoría
        if categoria:
            query = query.filter(func.lower(Producto.categoria) == categoria.lower())
        
        # Filtro por búsqueda de texto
        if q:
            q_lower = q.lower().strip()
            palabras_busqueda = [palabra.strip() for palabra in q_lower.split() if palabra.strip()]
            
            if palabras_busqueda:
                # Crear condiciones de búsqueda para cada palabra
                condiciones = []
                for palabra in palabras_busqueda:
                    condicion = or_(
                        func.lower(Producto.nombre).contains(palabra),
                        func.lower(Producto.marca).contains(palabra)
                    )
                    condiciones.append(condicion)
                
                # Aplicar todas las condiciones (AND)
                query = query.filter(and_(*condiciones))
        
        # Subconsulta para contar supermercados por producto
        if min_supermercados > 1:
            subquery = db.query(
                Precio.producto_id,
                func.count(func.distinct(Precio.supermercado_id)).label('num_supermercados')
            ).group_by(Precio.producto_id).subquery()
            
            query = query.join(subquery, Producto.id == subquery.c.producto_id).filter(
                subquery.c.num_supermercados >= min_supermercados
            )
        
        # Contar total de productos
        total_productos = query.count()
        
        # Paginación
        total_paginas = math.ceil(total_productos / limit)
        start_index = (page - 1) * limit
        
        productos = query.offset(start_index).limit(limit).all()
        
        # Para cada producto, obtener los supermercados donde está disponible
        productos_con_supermercados = []
        for producto in productos:
            supermercados_disponibles = db.query(Supermercado.nombre).join(
                Precio, Supermercado.id == Precio.supermercado_id
            ).filter(Precio.producto_id == producto.id).distinct().all()
            
            banderas_disponibles = [super[0] for super in supermercados_disponibles]
            
            productos_con_supermercados.append({
                "id": producto.id,
                "ean": producto.ean,
                "nombre": producto.nombre,
                "marca": producto.marca,
                "categoria": producto.categoria,
                "peso_volumen": producto.peso_volumen,
                "banderas_disponibles": banderas_disponibles
            })
        
        return {
            "productos": productos_con_supermercados,
            "pagina_actual": page,
            "total_paginas": total_paginas,
            "total_productos_disponibles": total_productos
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo productos: {str(e)}")

@app.post("/api/comparar", summary="Compara un carrito y devuelve los totales y detalles de precios")
def comparar_carrito(request: ComparisonRequest, db: Session = Depends(get_db)):
    """
    Compara precios de un carrito en todos los supermercados
    """
    try:
        # Obtener todos los supermercados activos
        supermercados = db.query(Supermercado).filter(Supermercado.activo == True).all()
        
        resultados_finales = []
        todos_los_eans_del_carrito = {item.ean for item in request.items}
        
        for supermercado in supermercados:
            total_inicial = 0.0
            items_encontrados = 0
            detalle_productos = []
            productos_no_encontrados = []
            eans_encontrados_en_supermercado = set()
            
            for item in request.items:
                # Buscar producto por EAN
                producto = db.query(Producto).filter(Producto.ean == item.ean).first()
                if not producto:
                    continue
                
                # Buscar precios del producto en este supermercado
                precio_query = db.query(Precio).filter(
                    and_(
                        Precio.producto_id == producto.id,
                        Precio.supermercado_id == supermercado.id,
                        Precio.activo == True
                    )
                )
                
                # Obtener el mejor precio (mínimo)
                precio_lista = precio_query.filter(Precio.precio_lista.isnot(None)).order_by(Precio.precio_lista).first()
                precio_promo = precio_query.filter(Precio.precio_promo_a.isnot(None)).order_by(Precio.precio_promo_a).first()
                
                if not precio_lista:
                    continue
                
                eans_encontrados_en_supermercado.add(item.ean)
                
                precio_lista_final = float(precio_lista.precio_lista)
                precio_promo_a_final = float(precio_promo.precio_promo_a) if precio_promo else None
                
                # Decidir qué precio usar
                precio_a_usar = precio_lista_final
                if request.use_promos and precio_promo_a_final is not None:
                    precio_a_usar = precio_promo_a_final
                
                items_encontrados += 1
                total_inicial += precio_a_usar * item.quantity
                
                detalle_productos.append({
                    'nombre': producto.nombre,
                    'ean': item.ean,
                    'quantity': item.quantity,
                    'precio_lista': precio_lista_final,
                    'precio_promo_a': precio_promo_a_final
                })
            
            # Productos no encontrados en este supermercado
            eans_faltantes = todos_los_eans_del_carrito - eans_encontrados_en_supermercado
            for ean_faltante in eans_faltantes:
                producto = db.query(Producto).filter(Producto.ean == ean_faltante).first()
                if producto:
                    productos_no_encontrados.append({'nombre': producto.nombre})
            
            # Solo agregar si encontró al menos un producto
            if items_encontrados > 0:
                resultados_finales.append({
                    'bandera': supermercado.nombre,
                    'total_inicial': round(total_inicial, 2),
                    'items_encontrados': items_encontrados,
                    'items_faltantes': len(eans_faltantes),
                    'detalle': detalle_productos,
                    'no_encontrados': productos_no_encontrados
                })
        
        # Ordenar por total y limitar a 4 resultados
        resultados_finales.sort(key=lambda x: x['total_inicial'])
        resultados_limitados = resultados_finales[:4]
        
        return {
            "comparativa": resultados_limitados,
            "promo_inicial_activada": request.use_promos
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparando carrito: {str(e)}")

@app.post("/api/optimizar", summary="Calcula la mejor combinación de compra en dos supermercados")
def optimizar_carrito(request: ComparisonRequest, db: Session = Depends(get_db)):
    """
    Optimiza la compra distribuyendo productos entre máximo 2 supermercados
    """
    try:
        precios_optimos = {}
        
        # 1. Para cada producto, encontrar el mejor precio en cada supermercado
        for item in request.items:
            producto = db.query(Producto).filter(Producto.ean == item.ean).first()
            if not producto:
                continue
            
            # Obtener precios por supermercado
            precios_por_super = {}
            supermercados = db.query(Supermercado).filter(Supermercado.activo == True).all()
            
            for supermercado in supermercados:
                precio_query = db.query(Precio).filter(
                    and_(
                        Precio.producto_id == producto.id,
                        Precio.supermercado_id == supermercado.id,
                        Precio.activo == True
                    )
                )
                
                precio_lista = precio_query.filter(Precio.precio_lista.isnot(None)).order_by(Precio.precio_lista).first()
                precio_promo = precio_query.filter(Precio.precio_promo_a.isnot(None)).order_by(Precio.precio_promo_a).first()
                
                if precio_lista:
                    precios_por_super[supermercado.nombre] = {
                        'precio_lista': float(precio_lista.precio_lista),
                        'precio_promo_a': float(precio_promo.precio_promo_a) if precio_promo else None
                    }
            
            if precios_por_super:
                precios_optimos[item.ean] = precios_por_super
        
        # 2. Encontrar el supermercado más barato para cada producto
        canastas = {}
        for ean, precios_por_super in precios_optimos.items():
            mejor_supermercado = None
            precio_mas_bajo = float('inf')
            
            for supermercado, precios in precios_por_super.items():
                precio_a_usar = precios['precio_lista']
                if request.use_promos and precios['precio_promo_a'] is not None:
                    precio_a_usar = precios['precio_promo_a']
                
                if precio_a_usar < precio_mas_bajo:
                    precio_mas_bajo = precio_a_usar
                    mejor_supermercado = supermercado
            
            if mejor_supermercado:
                if mejor_supermercado not in canastas:
                    canastas[mejor_supermercado] = []
                canastas[mejor_supermercado].append(ean)
        
        # 3. Consolidar a máximo 2 supermercados
        if len(canastas) > 2:
            canastas_ordenadas = sorted(canastas.items(), key=lambda item: len(item[1]), reverse=True)
            canastas_principales = dict(canastas_ordenadas[:2])
            
            # Reasignar productos de supermercados descartados
            for super_descartado, eans_descartados in canastas_ordenadas[2:]:
                for ean in eans_descartados:
                    mejor_destino = None
                    menor_precio_en_principales = float('inf')
                    
                    for super_principal in canastas_principales:
                        if super_principal in precios_optimos[ean]:
                            precio_actual = precios_optimos[ean][super_principal]['precio_lista']
                            if request.use_promos and precios_optimos[ean][super_principal]['precio_promo_a'] is not None:
                                precio_actual = precios_optimos[ean][super_principal]['precio_promo_a']
                            
                            if precio_actual < menor_precio_en_principales:
                                menor_precio_en_principales = precio_actual
                                mejor_destino = super_principal
                    
                    if mejor_destino:
                        canastas_principales[mejor_destino].append(ean)
            
            canastas = canastas_principales
        
        # 4. Formatear respuesta final
        resultado_optimizado = []
        total_compra_optimizada = 0
        
        for supermercado, eans in canastas.items():
            detalle_canasta = []
            total_canasta = 0
            
            for ean in eans:
                item_original = next(i for i in request.items if i.ean == ean)
                producto = db.query(Producto).filter(Producto.ean == ean).first()
                
                precios_reales = precios_optimos[ean][supermercado]
                precio_lista_final = precios_reales['precio_lista']
                precio_promo_a_final = precios_reales.get('precio_promo_a')
                
                precio_a_usar = precio_lista_final
                if request.use_promos and precio_promo_a_final is not None:
                    precio_a_usar = precio_promo_a_final
                
                total_canasta += precio_a_usar * item_original.quantity
                
                detalle_canasta.append({
                    'nombre': producto.nombre,
                    'quantity': item_original.quantity,
                    'ean': ean,
                    'precio_lista': precio_lista_final,
                    'precio_promo_a': precio_promo_a_final
                })
            
            resultado_optimizado.append({
                'bandera': supermercado,
                'total_canasta': round(total_canasta, 2),
                'detalle': detalle_canasta
            })
            total_compra_optimizada += total_canasta
        
        return {
            "total_optimizado": round(total_compra_optimizada, 2),
            "canastas": resultado_optimizado
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizando carrito: {str(e)}")

# --- ENDPOINTS ADICIONALES PARA ADMINISTRACIÓN ---
@app.get("/api/stats", summary="Estadísticas de la base de datos")
def get_stats(db: Session = Depends(get_db)):
    """
    Obtiene estadísticas básicas de la base de datos
    """
    try:
        total_productos = db.query(Producto).count()
        total_supermercados = db.query(Supermercado).filter(Supermercado.activo == True).count()
        total_precios = db.query(Precio).filter(Precio.activo == True).count()
        
        return {
            "total_productos": total_productos,
            "total_supermercados": total_supermercados,
            "total_precios": total_precios,
            "database_type": "PostgreSQL (Supabase)"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")

# --- Bloque de ejecución directa ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_postgresql:app", host="127.0.0.1", port=8000, reload=True)
