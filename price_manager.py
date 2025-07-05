"""
Price manager module for Supabase operations.
Handles all price-related database interactions for the scraper system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import func, and_

from backend.database.connection import SessionLocal, engine, test_connection
from backend.database.models import Producto, Supermercado, Precio
from utils import format_number, get_timestamp

class PriceManager:
    """
    Manages all price-related database operations for Supabase.
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize PriceManager with configuration and logger.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.connection_tested = False
        
        # Cache for performance optimization
        self.ean_to_producto_id = {}  # Cache EAN -> producto_id mappings
        self.bandera_to_supermercado_id = {}  # Cache bandera -> supermercado_id mappings
        
        # Statistics tracking
        self.stats = {
            'precios_insertados': 0,
            'precios_actualizados': 0,
            'precios_omitidos': 0,
            'errores_base_datos': 0,
            'productos_no_encontrados': 0,
            'supermercados_no_encontrados': 0,
            'ultima_operacion': None
        }
    
    def test_database_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            True if connection is successful
        """
        if self.connection_tested:
            return True
            
        try:
            self.logger.info("Testing database connection...")
            if test_connection():
                self.connection_tested = True
                self.logger.info("✅ Database connection successful")
                return True
            else:
                self.logger.error("❌ Database connection failed")
                return False
        except Exception as e:
            self.logger.error(f"Database connection test error: {e}")
            return False
    
    def get_session(self) -> Session:
        """
        Get a database session.
        
        Returns:
            SQLAlchemy session
        """
        try:
            session = SessionLocal()
            return session
        except Exception as e:
            self.logger.error(f"Error creating database session: {e}")
            raise
    
    def load_producto_cache(self):
        """
        Load all products into cache for faster EAN lookups.
        """
        try:
            with self.get_session() as session:
                productos = session.query(Producto.ean, Producto.id).all()
                self.ean_to_producto_id = {str(ean): producto_id for ean, producto_id in productos}
                self.logger.info(f"Loaded {len(self.ean_to_producto_id)} products into cache")
        except Exception as e:
            self.logger.error(f"Error loading product cache: {e}")
    
    def load_supermercado_cache(self):
        """
        Load all supermercados into cache for faster bandera lookups.
        """
        try:
            with self.get_session() as session:
                supermercados = session.query(Supermercado.codigo, Supermercado.id).all()
                self.bandera_to_supermercado_id = {codigo: supermercado_id for codigo, supermercado_id in supermercados}
                self.logger.info(f"Loaded {len(self.bandera_to_supermercado_id)} supermercados into cache")
        except Exception as e:
            self.logger.error(f"Error loading supermercado cache: {e}")
    
    def get_producto_id_by_ean(self, ean: str) -> Optional[int]:
        """
        Get producto_id by EAN, using cache for performance.
        
        Args:
            ean: Product EAN code
            
        Returns:
            producto_id or None if not found
        """
        # Check cache first
        if ean in self.ean_to_producto_id:
            return self.ean_to_producto_id[ean]
        
        # If not in cache, query database
        try:
            with self.get_session() as session:
                producto = session.query(Producto).filter(Producto.ean == ean).first()
                if producto:
                    # Add to cache
                    self.ean_to_producto_id[ean] = producto.id
                    return producto.id
                else:
                    self.stats['productos_no_encontrados'] += 1
                    return None
        except Exception as e:
            self.logger.error(f"Error getting producto_id for EAN {ean}: {e}")
            return None
    
    def get_supermercado_id_by_bandera(self, bandera: str) -> Optional[int]:
        """
        Get supermercado_id by bandera, using cache for performance.
        
        Args:
            bandera: Supermercado bandera/codigo
            
        Returns:
            supermercado_id or None if not found
        """
        # Check cache first
        if bandera in self.bandera_to_supermercado_id:
            return self.bandera_to_supermercado_id[bandera]
        
        # If not in cache, query database
        try:
            with self.get_session() as session:
                supermercado = session.query(Supermercado).filter(Supermercado.codigo == bandera).first()
                if supermercado:
                    # Add to cache
                    self.bandera_to_supermercado_id[bandera] = supermercado.id
                    return supermercado.id
                else:
                    self.stats['supermercados_no_encontrados'] += 1
                    return None
        except Exception as e:
            self.logger.error(f"Error getting supermercado_id for bandera {bandera}: {e}")
            return None
    
    def add_or_update_price(self, price_data: Dict[str, Any]) -> bool:
        """
        Add a price in the database using EAN directly as producto_id.
        
        Args:
            price_data: Price information dictionary from scraper
            
        Returns:
            True if price was added successfully
        """
        try:
            # Extract data from price_data
            ean = str(price_data.get('ean', ''))
            bandera = price_data.get('bandera', '').strip()
            
            self.logger.debug(f"Processing price data: EAN={ean}, bandera={bandera}")
            
            if not ean or not bandera:
                self.logger.warning(f"Missing EAN or bandera in price data: {price_data}")
                self.stats['precios_omitidos'] += 1
                return False
            
            # Use EAN directly as producto_id (no lookup needed)
            try:
                producto_id = int(ean)  # Convert EAN string to integer
                self.logger.debug(f"Converted EAN {ean} to producto_id {producto_id}")
            except ValueError as e:
                self.logger.error(f"Invalid EAN format {ean}: {e}")
                self.stats['precios_omitidos'] += 1
                return False
            
            # Set supermercado_id to NULL as requested
            supermercado_id = None
            
            # Prepare price data
            precio_data = {
                'producto_id': producto_id,
                'supermercado_id': supermercado_id,
                'sucursal': price_data.get('sucursal', ''),
                'precio_lista': float(price_data.get('precio_lista', 0)),
                'precio_promo_a': float(price_data.get('precio_promo_a')) if price_data.get('precio_promo_a') else None,
                'precio_promo_b': None,  # Always NULL as requested
                'bandera': bandera,
                'super_razon_social': price_data.get('supermercado', ''),
                'activo': True
            }
            
            self.logger.debug(f"Prepared price data: {precio_data}")
            
            # Add price
            result = self._add_or_update_price_record(precio_data)
            self.logger.debug(f"Price insertion result: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing price data: {e}")
            import traceback
            traceback.print_exc()
            self.stats['errores_base_datos'] += 1
            return False
    
    def _add_or_update_price_record(self, precio_data: Dict[str, Any]) -> bool:
        """
        Always insert a new price record in the database (no updates).
        
        Args:
            precio_data: Processed price data
            
        Returns:
            True if successful
        """
        session = None
        try:
            session = self.get_session()
            
            # Always insert new price (no updates, always create new records)
            new_price = Precio(
                producto_id=precio_data['producto_id'],
                supermercado_id=precio_data['supermercado_id'],
                sucursal=precio_data['sucursal'],
                precio_lista=precio_data['precio_lista'],
                precio_promo_a=precio_data['precio_promo_a'],
                precio_promo_b=precio_data['precio_promo_b'],
                bandera=precio_data['bandera'],
                super_razon_social=precio_data['super_razon_social'],
                activo=precio_data['activo']
            )
            
            session.add(new_price)
            session.commit()
            self.stats['precios_insertados'] += 1
            self.logger.debug(f"Inserted new price for product_id {precio_data['producto_id']}, supermercado_id {precio_data['supermercado_id']}")
            return True
                
        except Exception as e:
            if session:
                session.rollback()
            self.logger.error(f"Error inserting price: {e}")
            self.stats['errores_base_datos'] += 1
            return False
        finally:
            if session:
                session.close()
    
    def batch_save_prices(self, prices_list: List[Dict[str, Any]]) -> Tuple[int, int, int]:
        """
        Save multiple prices in a single transaction for better performance.
        
        Args:
            prices_list: List of price dictionaries
            
        Returns:
            Tuple of (inserted, updated, skipped) counts
        """
        if not prices_list:
            return 0, 0, 0
        
        inserted = 0
        updated = 0
        skipped = 0
        
        for price_data in prices_list:
            result = self.add_or_update_price(price_data)
            if result:
                # Check if it was insert or update based on stats change
                if self.stats['precios_insertados'] > inserted:
                    inserted += 1
                elif self.stats['precios_actualizados'] > updated:
                    updated += 1
            else:
                skipped += 1
        
        self.logger.info(f"Batch save completed: {inserted} inserted, {updated} updated, {skipped} skipped")
        return inserted, updated, skipped
    
    def get_price_count(self) -> int:
        """
        Get total number of prices in database.
        
        Returns:
            Number of prices
        """
        try:
            with self.get_session() as session:
                count = session.query(func.count(Precio.id)).scalar()
                return count or 0
        except Exception as e:
            self.logger.error(f"Error getting price count: {e}")
            return 0
    
    def get_prices_by_supermercado(self) -> Dict[str, int]:
        """
        Get price count by supermercado bandera.
        
        Returns:
            Dictionary with supermercado counts
        """
        try:
            with self.get_session() as session:
                results = session.query(
                    Precio.bandera, 
                    func.count(Precio.id)
                ).group_by(Precio.bandera).all()
                
                supermercado_counts = {}
                for bandera, count in results:
                    supermercado_counts[bandera or 'Sin bandera'] = count
                
                return supermercado_counts
        except Exception as e:
            self.logger.error(f"Error getting prices by supermercado: {e}")
            return {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the price database.
        
        Returns:
            Statistics dictionary
        """
        try:
            with self.get_session() as session:
                # Basic counts
                total_prices = session.query(func.count(Precio.id)).scalar() or 0
                
                if total_prices == 0:
                    return {'total_prices': 0}
                
                # Active prices
                active_prices = session.query(func.count(Precio.id)).filter(Precio.activo == True).scalar() or 0
                
                # Supermercado counts
                supermercado_counts = self.get_prices_by_supermercado()
                
                # Price range statistics
                price_stats = session.query(
                    func.min(Precio.precio_lista),
                    func.max(Precio.precio_lista),
                    func.avg(Precio.precio_lista)
                ).first()
                
                min_price, max_price, avg_price = price_stats if price_stats else (0, 0, 0)
                
                # Products with prices
                products_with_prices = session.query(func.count(func.distinct(Precio.producto_id))).scalar() or 0
                
                return {
                    'total_prices': total_prices,
                    'active_prices': active_prices,
                    'inactive_prices': total_prices - active_prices,
                    'supermercados': supermercado_counts,
                    'products_with_prices': products_with_prices,
                    'min_price': float(min_price) if min_price else 0.0,
                    'max_price': float(max_price) if max_price else 0.0,
                    'avg_price': float(avg_price) if avg_price else 0.0,
                    'last_updated': get_timestamp(),
                    'operation_stats': self.stats.copy()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting price statistics: {e}")
            return {'total_prices': 0, 'operation_stats': self.stats.copy()}
    
    def cleanup_old_prices(self, days_old: int = 30) -> int:
        """
        Mark old prices as inactive.
        
        Args:
            days_old: Number of days to consider prices as old
            
        Returns:
            Number of prices marked as inactive
        """
        try:
            with self.get_session() as session:
                cutoff_date = datetime.now() - timedelta(days=days_old)
                
                updated_count = session.query(Precio).filter(
                    and_(
                        Precio.fecha_actualizacion < cutoff_date,
                        Precio.activo == True
                    )
                ).update({'activo': False})
                
                session.commit()
                
                if updated_count > 0:
                    self.logger.info(f"Marked {updated_count} old prices as inactive")
                
                return updated_count
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old prices: {e}")
            return 0
    
    def get_operation_stats(self) -> Dict[str, Any]:
        """
        Get current operation statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """
        Reset operation statistics.
        """
        self.stats = {
            'precios_insertados': 0,
            'precios_actualizados': 0,
            'precios_omitidos': 0,
            'errores_base_datos': 0,
            'productos_no_encontrados': 0,
            'supermercados_no_encontrados': 0,
            'ultima_operacion': None
        }
