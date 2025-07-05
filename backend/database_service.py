"""
Database service for backend API.
Handles all database queries replacing Excel file operations.
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, String
from sqlalchemy.exc import SQLAlchemyError
from .database.connection import SessionLocal
from .database.models import Producto, Precio

class DatabaseService:
    """
    Service class to handle all database operations for the API.
    Replaces Excel file operations with direct database queries.
    """
    
    def __init__(self):
        """Initialize the database service."""
        pass
    
    @contextmanager
    def get_session(self):
        """
        Context manager for database sessions.
        Ensures proper session handling with automatic rollback on errors.
        """
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error occurred: {e}")
            raise
        except Exception as e:
            session.rollback()
            print(f"Unexpected error occurred: {e}")
            raise
        finally:
            session.close()
    
    def close_session(self):
        """Deprecated method - sessions are now handled by context manager."""
        pass
    
    def get_productos_df(self) -> pd.DataFrame:
        """
        Get productos as DataFrame (mimicking Excel load).
        
        Returns:
            DataFrame with productos data
        """
        try:
            with self.get_session() as session:
                # Query all productos
                productos = session.query(Producto).all()
                
                # Convert to DataFrame to maintain compatibility
                productos_data = []
                for producto in productos:
                    productos_data.append({
                        'ean': str(producto.ean),
                        'nombre': producto.nombre or 'Sin Nombre',
                        'marca': producto.marca or 'Sin Marca',
                        'Categoria': producto.categoria or 'Otros'  # Note: capital C to match Excel
                    })
                
                df = pd.DataFrame(productos_data)
                df['ean'] = df['ean'].astype(str)
                
                return df
                
        except Exception as e:
            print(f"Error loading productos from database: {e}")
            return pd.DataFrame()
    
    def get_precios_df(self) -> pd.DataFrame:
        """
        Get precios as DataFrame (mimicking Excel load).
        
        Returns:
            DataFrame with precios data
        """
        try:
            with self.get_session() as session:
                # Query all precios
                precios = session.query(Precio).filter(Precio.activo == True).all()
                
                # Convert to DataFrame to maintain compatibility
                precios_data = []
                for precio in precios:
                    # Create sucursal field to match Excel format
                    sucursal = f"{precio.bandera} - {precio.sucursal}" if precio.sucursal else precio.bandera
                    
                    precios_data.append({
                        'ean': str(precio.producto_id),  # producto_id is the EAN
                        'sucursal': sucursal,
                        'bandera': precio.bandera,
                        'precio_lista': float(precio.precio_lista) if precio.precio_lista else None,
                        'precio_promo_a': float(precio.precio_promo_a) if precio.precio_promo_a else None
                    })
                
                df = pd.DataFrame(precios_data)
                df['ean'] = df['ean'].astype(str)
                
                # Extract bandera from sucursal (to match original logic)
                df['bandera'] = df['sucursal'].apply(
                    lambda x: x.split(' - ')[0] if isinstance(x, str) and ' - ' in x else x
                )
                
                return df
                
        except Exception as e:
            print(f"Error loading precios from database: {e}")
            return pd.DataFrame()
    
    def get_categorias(self) -> List[str]:
        """
        Get unique categories from database.
        
        Returns:
            List of unique categories
        """
        try:
            with self.get_session() as session:
                # Query distinct categories
                categorias = session.query(Producto.categoria).distinct().all()
                categorias_raw = [cat[0] for cat in categorias if cat[0]]
                
                # Clean and normalize categories
                categorias_clean = []
                for cat in categorias_raw:
                    # Fix encoding issues and normalize
                    cat_clean = self._clean_category_name(cat)
                    if cat_clean and cat_clean not in categorias_clean:
                        categorias_clean.append(cat_clean)
                
                # Sort and put 'Otros' at the end (matching original logic)
                if 'Otros' in categorias_clean:
                    categorias_clean.remove('Otros')
                    return sorted(categorias_clean) + ['Otros']
                
                return sorted(categorias_clean)
                
        except Exception as e:
            print(f"Error getting categorias from database: {e}")
            return []
    
    def _clean_category_name(self, category: str) -> str:
        """
        Clean and normalize category names.
        
        Args:
            category: Raw category name
            
        Returns:
            Cleaned category name
        """
        if not category:
            return 'Otros'
        
        try:
            # Clean the category string
            category = str(category).strip()
            
            # Normalize common variations to standard names
            category_lower = category.lower()
            
            # Direct mapping of known categories (including corrupted ones)
            category_mapping = {
                'almacen': 'Almacén',
                'almacén': 'Almacén',
                'almacn': 'Almacén',  # Handle corrupted encoding
                'bebidas': 'Bebidas',
                'carnes y pescados': 'Carnes y Pescados',
                'congelados': 'Congelados',
                'lacteos': 'Lácteos',
                'lácteos': 'Lácteos',
                'panaderia': 'Panadería',
                'panadería': 'Panadería',
                'limpieza': 'Limpieza',
                'perfumeria': 'Perfumería',
                'perfumería': 'Perfumería',
                'higiene personal': 'Higiene Personal',
                'otros': 'Otros'
            }
            
            # Check direct mapping first
            if category_lower in category_mapping:
                return category_mapping[category_lower]
            
            # Handle special cases for corrupted text
            if '' in category_lower or len(category) != len(category.encode('utf-8').decode('utf-8', errors='ignore')):
                # This looks like corrupted encoding, try to map to known categories
                if 'almac' in category_lower:
                    return 'Almacén'
                elif 'bebida' in category_lower:
                    return 'Bebidas'
                elif 'carne' in category_lower:
                    return 'Carnes y Pescados'
                elif 'congel' in category_lower:
                    return 'Congelados'
                elif 'lacteo' in category_lower:
                    return 'Lácteos'
                elif 'panade' in category_lower:
                    return 'Panadería'
                elif 'limpie' in category_lower:
                    return 'Limpieza'
                elif 'perfume' in category_lower:
                    return 'Perfumería'
                else:
                    return 'Otros'
            
            # If no direct mapping, capitalize properly
            return ' '.join(word.capitalize() for word in category.split())
                
        except Exception as e:
            print(f"Error cleaning category '{category}': {e}")
            return 'Otros'
    
    def _normalize_category_for_filter(self, category: str) -> str:
        """
        Normalize category for filtering to match database variations.
        
        Args:
            category: Category name from frontend
            
        Returns:
            Normalized category name for database query
        """
        if not category:
            return ''
        
        # Map frontend categories to possible database variations
        category_lower = category.lower().strip()
        
        # Return variations that might exist in database
        variations_map = {
            'almacén': 'almacen',  # Frontend sends "Almacén", DB might have "almacen"
            'lácteos': 'lacteos',
            'panadería': 'panaderia',
            'perfumería': 'perfumeria'
        }
        
        return variations_map.get(category_lower, '')
    
    def get_productos_with_banderas(self, q: str = None, categoria: str = None,
                                   min_supermercados: int = 1, page: int = 1, 
                                   limit: int = 24) -> Dict[str, Any]:
        """
        Get productos with their available banderas (paginated and filtered).
        
        Args:
            q: Search query
            categoria: Category filter
            min_supermercados: Minimum number of supermercados
            page: Page number
            limit: Items per page
            
        Returns:
            Dictionary with productos, pagination info
        """
        try:
            with self.get_session() as session:
                # Base query for productos with precios
                # Cast producto_id to string to match ean type
                base_query = session.query(
                    Producto.ean,
                    Producto.nombre,
                    Producto.marca,
                    Producto.categoria.label('Categoria'),
                    func.string_agg(Precio.bandera, ',').label('banderas_disponibles')
                ).join(
                    Precio, Producto.ean == Precio.producto_id.cast(String)
                ).filter(
                    Precio.activo == True
                ).group_by(
                    Producto.ean, Producto.nombre, Producto.marca, Producto.categoria
                )
                
                # Apply min_supermercados filter
                if min_supermercados > 1:
                    base_query = base_query.having(
                        func.count(func.distinct(Precio.bandera)) >= min_supermercados
                    )
                
                # Apply category filter
                if categoria:
                    # Normalize the filter category to match database variations
                    categoria_normalized = self._normalize_category_for_filter(categoria)
                    if categoria_normalized:
                        base_query = base_query.filter(
                            or_(
                                func.lower(Producto.categoria) == categoria.lower(),
                                func.lower(Producto.categoria) == categoria_normalized.lower()
                            )
                        )
                
                # Apply search filter
                if q:
                    q_lower = q.lower().strip()
                    palabras_busqueda = [palabra.strip() for palabra in q_lower.split() if palabra.strip()]
                    
                    if palabras_busqueda:
                        search_conditions = []
                        for palabra in palabras_busqueda:
                            search_conditions.append(
                                or_(
                                    func.lower(Producto.nombre).contains(palabra),
                                    func.lower(Producto.marca).contains(palabra)
                                )
                            )
                        base_query = base_query.filter(and_(*search_conditions))
                
                # Get total count
                total_productos_disponibles = base_query.count()
                
                # Apply pagination
                start_index = (page - 1) * limit
                paginated_results = base_query.offset(start_index).limit(limit).all()
                
                # Convert to format expected by frontend
                productos_list = []
                for result in paginated_results:
                    # Handle banderas_disponibles string (comma-separated)
                    if result.banderas_disponibles:
                        banderas = list(set([b.strip() for b in result.banderas_disponibles.split(',') if b.strip()]))
                    else:
                        banderas = []
                    
                    productos_list.append({
                        'ean': str(result.ean),
                        'nombre': result.nombre or 'Sin Nombre',
                        'marca': result.marca or 'Sin Marca',
                        'Categoria': result.Categoria or 'Otros',
                        'banderas_disponibles': banderas
                    })
                
                import math
                total_paginas = math.ceil(total_productos_disponibles / limit)
                
                return {
                    "productos": productos_list,
                    "pagina_actual": page,
                    "total_paginas": total_paginas,
                    "total_productos_disponibles": total_productos_disponibles
                }
                
        except Exception as e:
            print(f"Error getting productos with banderas: {e}")
            return {
                "productos": [],
                "pagina_actual": page,
                "total_paginas": 0,
                "total_productos_disponibles": 0
            }
    
    def get_precios_for_comparison(self, eans: List[str]) -> pd.DataFrame:
        """
        Get precios for specific EANs for comparison.
        
        Args:
            eans: List of EAN codes
            
        Returns:
            DataFrame with precios data
        """
        try:
            with self.get_session() as session:
                # Convert EANs to integers for database query
                ean_integers = []
                for ean in eans:
                    try:
                        ean_integers.append(int(ean))
                    except ValueError:
                        continue
                
                if not ean_integers:
                    return pd.DataFrame()
                
                # Query precios for specific EANs
                precios = session.query(Precio).filter(
                    and_(
                        Precio.producto_id.in_(ean_integers),
                        Precio.activo == True
                    )
                ).all()
                
                # Convert to DataFrame
                precios_data = []
                for precio in precios:
                    precios_data.append({
                        'ean': str(precio.producto_id),
                        'bandera': precio.bandera,
                        'precio_lista': float(precio.precio_lista) if precio.precio_lista else None,
                        'precio_promo_a': float(precio.precio_promo_a) if precio.precio_promo_a else None
                    })
                
                return pd.DataFrame(precios_data)
                
        except Exception as e:
            print(f"Error getting precios for comparison: {e}")
            return pd.DataFrame()
    
    def get_producto_info(self, ean: str) -> Dict[str, Any]:
        """
        Get producto information by EAN.
        
        Args:
            ean: EAN code
            
        Returns:
            Dictionary with producto info
        """
        try:
            with self.get_session() as session:
                producto = session.query(Producto).filter(Producto.ean == ean).first()
                
                if producto:
                    return {
                        'ean': str(producto.ean),
                        'nombre': producto.nombre or 'Sin Nombre',
                        'marca': producto.marca or 'Sin Marca',
                        'Categoria': producto.categoria or 'Otros'
                    }
                else:
                    return {
                        'ean': ean,
                        'nombre': 'Producto no encontrado',
                        'marca': 'Sin Marca',
                        'Categoria': 'Otros'
                    }
                    
        except Exception as e:
            print(f"Error getting producto info for EAN {ean}: {e}")
            return {
                'ean': ean,
                'nombre': 'Error al cargar producto',
                'marca': 'Sin Marca',
                'Categoria': 'Otros'
            }

# Global instance
db_service = DatabaseService()
