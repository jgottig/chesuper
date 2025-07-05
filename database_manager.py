"""
Database manager module for Supabase operations.
Handles all database interactions for the product scraper system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import func, and_

from backend.database.connection import SessionLocal, engine, test_connection
from backend.database.models import Producto
from utils import (
    normalize_text, clean_product_name, validate_ean, 
    calculate_data_completeness, merge_product_data, 
    format_number, get_timestamp
)

class DatabaseManager:
    """
    Manages all database operations for products in Supabase.
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize DatabaseManager with configuration and logger.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.connection_tested = False
        
        # Statistics tracking
        self.stats = {
            'products_inserted': 0,
            'products_updated': 0,
            'products_skipped': 0,
            'database_errors': 0,
            'last_operation_time': None
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
    
    def load_existing_products_count(self) -> int:
        """
        Get count of existing products in database.
        
        Returns:
            Number of existing products
        """
        session = None
        try:
            session = self.get_session()
            # Use a simpler query with timeout
            count = session.execute("SELECT COUNT(*) FROM productos").scalar()
            self.logger.info(f"Found {format_number(count)} existing products in database")
            return count or 0
        except Exception as e:
            self.logger.error(f"Error counting existing products: {e}")
            return 0
        finally:
            if session:
                session.close()
    
    def product_exists(self, ean: str) -> bool:
        """
        Check if a product exists in the database by EAN.
        
        Args:
            ean: Product EAN code
            
        Returns:
            True if product exists
        """
        try:
            with self.get_session() as session:
                exists = session.query(Producto).filter(Producto.ean == ean).first() is not None
                return exists
        except Exception as e:
            self.logger.error(f"Error checking if product exists (EAN: {ean}): {e}")
            return False
    
    def get_product_by_ean(self, ean: str) -> Optional[Dict[str, Any]]:
        """
        Get a product by EAN from database.
        
        Args:
            ean: Product EAN code
            
        Returns:
            Product dictionary or None
        """
        try:
            with self.get_session() as session:
                product = session.query(Producto).filter(Producto.ean == ean).first()
                if product:
                    return {
                        'id': product.id,
                        'ean': product.ean,
                        'nombre': product.nombre,
                        'marca': product.marca,
                        'categoria': product.categoria,
                        'completeness_score': float(product.completeness_score) if product.completeness_score else 0.0,
                        'created_at': product.created_at,
                        'updated_at': product.updated_at,
                        'image_url': product.image_url
                    }
                return None
        except Exception as e:
            self.logger.error(f"Error getting product by EAN ({ean}): {e}")
            return None
    
    def add_or_update_product(self, product_data: Dict[str, Any]) -> bool:
        """
        Add or update a product in the database.
        
        Args:
            product_data: Product information dictionary
            
        Returns:
            True if product was added/updated successfully
        """
        raw_ean = str(product_data.get('id', product_data.get('ean', '')))
        
        # Clean EAN by removing hyphens and other separators
        cleaned_ean = raw_ean.replace('-', '').replace('_', '').replace(' ', '')
        
        if not validate_ean(cleaned_ean):
            self.stats['products_skipped'] += 1
            return False
        
        # Clean and prepare product data
        cleaned_product = {
            'ean': cleaned_ean,
            'nombre': clean_product_name(str(product_data.get('nombre', ''))),
            'marca': str(product_data.get('marca', '')),
            'categoria': self._categorize_product(str(product_data.get('nombre', ''))),
            'completeness_score': 0.0  # Will be calculated below
        }
        
        # Calculate completeness score
        cleaned_product['completeness_score'] = calculate_data_completeness(cleaned_product)
        
        session = None
        try:
            session = self.get_session()
            
            # Try to insert first (most common case for new products)
            try:
                new_product = Producto(
                    ean=cleaned_product['ean'],
                    nombre=cleaned_product['nombre'],
                    marca=cleaned_product['marca'],
                    categoria=cleaned_product['categoria'],
                    completeness_score=str(round(cleaned_product['completeness_score'], 3)),
                    image_url=None
                )
                
                session.add(new_product)
                session.commit()
                
                self.stats['products_inserted'] += 1
                return True
                
            except IntegrityError:
                # Product already exists, try to update
                session.rollback()
                
                existing_product = session.query(Producto).filter(Producto.ean == cleaned_ean).first()
                if existing_product:
                    return self._update_existing_product(session, existing_product, cleaned_product)
                else:
                    self.stats['products_skipped'] += 1
                    return False
                    
        except Exception as e:
            if session:
                session.rollback()
            self.logger.error(f"Error adding/updating product (EAN: {cleaned_ean}): {e}")
            self.stats['database_errors'] += 1
            return False
        finally:
            if session:
                session.close()
    
    def _update_existing_product(self, session: Session, existing_product: Producto, new_data: Dict[str, Any]) -> bool:
        """
        Update an existing product with new data.
        
        Args:
            session: Database session
            existing_product: Existing product model
            new_data: New product data
            
        Returns:
            True if updated successfully
        """
        try:
            # Convert existing product to dict for comparison
            existing_data = {
                'ean': existing_product.ean,
                'nombre': existing_product.nombre,
                'marca': existing_product.marca,
                'categoria': existing_product.categoria,
                'completeness_score': float(existing_product.completeness_score) if existing_product.completeness_score else 0.0
            }
            
            # Merge data (prioritize more complete data)
            merged_data = merge_product_data(existing_data, new_data)
            
            # Check if update is needed
            if (merged_data['completeness_score'] > existing_data['completeness_score'] or
                merged_data != existing_data):
                
                # Update fields
                existing_product.nombre = merged_data['nombre']
                existing_product.marca = merged_data['marca']
                existing_product.categoria = merged_data['categoria']
                existing_product.completeness_score = str(round(merged_data['completeness_score'], 3))
                existing_product.updated_at = func.now()
                
                session.commit()
                self.stats['products_updated'] += 1
                self.logger.debug(f"Updated product: {existing_product.ean}")
                return True
            else:
                self.stats['products_skipped'] += 1
                return False
                
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating product: {e}")
            self.stats['database_errors'] += 1
            return False
    
    def _insert_new_product(self, session: Session, product_data: Dict[str, Any]) -> bool:
        """
        Insert a new product into the database.
        
        Args:
            session: Database session
            product_data: Product data dictionary
            
        Returns:
            True if inserted successfully
        """
        try:
            new_product = Producto(
                ean=product_data['ean'],
                nombre=product_data['nombre'],
                marca=product_data['marca'],
                categoria=product_data['categoria'],
                completeness_score=str(round(product_data['completeness_score'], 3)),
                image_url=None  # Will be handled later if needed
            )
            
            session.add(new_product)
            session.commit()
            
            self.stats['products_inserted'] += 1
            self.logger.debug(f"Inserted new product: {product_data['ean']}")
            return True
            
        except IntegrityError as e:
            session.rollback()
            # This might happen if another process inserted the same EAN
            self.logger.warning(f"Integrity error inserting product (EAN: {product_data['ean']}): {e}")
            self.stats['products_skipped'] += 1
            return False
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error inserting product: {e}")
            self.stats['database_errors'] += 1
            return False
    
    def _categorize_product(self, product_name: str) -> str:
        """
        Categorize product based on its name.
        
        Args:
            product_name: Product name to categorize
            
        Returns:
            Category name
        """
        if not product_name:
            return "Otros"
        
        # Import here to avoid circular imports
        from config import get_category_keywords
        category_keywords = get_category_keywords()
        
        normalized_name = normalize_text(product_name)
        
        for category, keywords in category_keywords.items():
            if any(keyword in normalized_name for keyword in keywords):
                return category
        
        return "Otros"
    
    def get_product_count(self) -> int:
        """
        Get total number of products in database.
        
        Returns:
            Number of products
        """
        try:
            with self.get_session() as session:
                count = session.query(func.count(Producto.id)).scalar()
                return count
        except Exception as e:
            self.logger.error(f"Error getting product count: {e}")
            return 0
    
    def get_products_by_category(self) -> Dict[str, int]:
        """
        Get product count by category.
        
        Returns:
            Dictionary with category counts
        """
        try:
            with self.get_session() as session:
                results = session.query(
                    Producto.categoria, 
                    func.count(Producto.id)
                ).group_by(Producto.categoria).all()
                
                category_counts = {}
                for categoria, count in results:
                    category_counts[categoria or 'Otros'] = count
                
                return category_counts
        except Exception as e:
            self.logger.error(f"Error getting products by category: {e}")
            return {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the product database.
        
        Returns:
            Statistics dictionary
        """
        try:
            with self.get_session() as session:
                # Basic counts
                total_products = session.query(func.count(Producto.id)).scalar()
                
                if total_products == 0:
                    return {'total_products': 0}
                
                # Category counts
                category_counts = self.get_products_by_category()
                
                # Completeness statistics
                completeness_results = session.query(Producto.completeness_score).all()
                completeness_scores = []
                for result in completeness_results:
                    try:
                        score = float(result[0]) if result[0] else 0.0
                        completeness_scores.append(score)
                    except (ValueError, TypeError):
                        completeness_scores.append(0.0)
                
                avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0.0
                
                # Brand statistics
                brand_results = session.query(
                    Producto.marca, 
                    func.count(Producto.id)
                ).group_by(Producto.marca).all()
                
                brands = {}
                for marca, count in brand_results:
                    brand_key = marca if marca else 'Sin marca'
                    brands[brand_key] = count
                
                top_brands = sorted(brands.items(), key=lambda x: x[1], reverse=True)[:10]
                
                # Data quality metrics
                complete_products = sum(1 for score in completeness_scores if score >= 0.8)
                incomplete_products = sum(1 for score in completeness_scores if score < 0.5)
                
                return {
                    'total_products': total_products,
                    'categories': category_counts,
                    'avg_completeness': round(avg_completeness, 3),
                    'complete_products': complete_products,
                    'incomplete_products': incomplete_products,
                    'top_brands': top_brands,
                    'unique_brands': len(brands),
                    'last_updated': get_timestamp(),
                    'database_stats': self.stats.copy()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting database statistics: {e}")
            return {'total_products': 0, 'database_stats': self.stats.copy()}
    
    def cleanup_duplicates(self) -> int:
        """
        Remove duplicate products based on name similarity.
        
        Returns:
            Number of duplicates removed
        """
        self.logger.info("Starting database duplicate cleanup...")
        
        try:
            with self.get_session() as session:
                # Get all products grouped by normalized name
                products = session.query(Producto).all()
                
                if not products:
                    return 0
                
                # Group products by normalized name
                name_groups = {}
                for product in products:
                    normalized_name = normalize_text(product.nombre)
                    if normalized_name not in name_groups:
                        name_groups[normalized_name] = []
                    name_groups[normalized_name].append(product)
                
                duplicates_removed = 0
                
                # Process groups with multiple products
                for normalized_name, product_group in name_groups.items():
                    if len(product_group) > 1:
                        # Sort by completeness score (descending) and keep the best one
                        product_group.sort(
                            key=lambda x: float(x.completeness_score) if x.completeness_score else 0.0, 
                            reverse=True
                        )
                        best_product = product_group[0]
                        
                        # Remove duplicates
                        for product in product_group[1:]:
                            session.delete(product)
                            duplicates_removed += 1
                            self.logger.debug(f"Removed duplicate: {product.ean} - {product.nombre}")
                
                if duplicates_removed > 0:
                    session.commit()
                    self.logger.info(f"Removed {duplicates_removed} duplicate products from database")
                
                return duplicates_removed
                
        except Exception as e:
            self.logger.error(f"Error during duplicate cleanup: {e}")
            return 0
    
    def batch_save_products(self, products: List[Dict[str, Any]]) -> Tuple[int, int, int]:
        """
        Save multiple products in a single transaction.
        
        Args:
            products: List of product dictionaries
            
        Returns:
            Tuple of (inserted, updated, skipped) counts
        """
        if not products:
            return 0, 0, 0
        
        inserted = 0
        updated = 0
        skipped = 0
        
        try:
            with self.get_session() as session:
                for product_data in products:
                    result = self._process_single_product_in_session(session, product_data)
                    if result == 'inserted':
                        inserted += 1
                    elif result == 'updated':
                        updated += 1
                    else:
                        skipped += 1
                
                session.commit()
                self.logger.info(f"Batch save completed: {inserted} inserted, {updated} updated, {skipped} skipped")
                
        except Exception as e:
            self.logger.error(f"Error in batch save: {e}")
            
        return inserted, updated, skipped
    
    def _process_single_product_in_session(self, session: Session, product_data: Dict[str, Any]) -> str:
        """
        Process a single product within an existing session.
        
        Args:
            session: Database session
            product_data: Product data dictionary
            
        Returns:
            'inserted', 'updated', or 'skipped'
        """
        raw_ean = str(product_data.get('id', product_data.get('ean', '')))
        cleaned_ean = raw_ean.replace('-', '').replace('_', '').replace(' ', '')
        
        if not validate_ean(cleaned_ean):
            return 'skipped'
        
        # Clean and prepare product data
        cleaned_product = {
            'ean': cleaned_ean,
            'nombre': clean_product_name(str(product_data.get('nombre', ''))),
            'marca': str(product_data.get('marca', '')),
            'categoria': self._categorize_product(str(product_data.get('nombre', ''))),
            'completeness_score': 0.0
        }
        
        cleaned_product['completeness_score'] = calculate_data_completeness(cleaned_product)
        
        # Check if product exists
        existing_product = session.query(Producto).filter(Producto.ean == cleaned_ean).first()
        
        if existing_product:
            # Update logic
            existing_data = {
                'ean': existing_product.ean,
                'nombre': existing_product.nombre,
                'marca': existing_product.marca,
                'categoria': existing_product.categoria,
                'completeness_score': float(existing_product.completeness_score) if existing_product.completeness_score else 0.0
            }
            
            merged_data = merge_product_data(existing_data, cleaned_product)
            
            if (merged_data['completeness_score'] > existing_data['completeness_score'] or
                merged_data != existing_data):
                
                existing_product.nombre = merged_data['nombre']
                existing_product.marca = merged_data['marca']
                existing_product.categoria = merged_data['categoria']
                existing_product.completeness_score = str(round(merged_data['completeness_score'], 3))
                existing_product.updated_at = func.now()
                
                return 'updated'
            else:
                return 'skipped'
        else:
            # Insert new product
            new_product = Producto(
                ean=cleaned_product['ean'],
                nombre=cleaned_product['nombre'],
                marca=cleaned_product['marca'],
                categoria=cleaned_product['categoria'],
                completeness_score=str(round(cleaned_product['completeness_score'], 3)),
                image_url=None
            )
            
            session.add(new_product)
            return 'inserted'
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get current database operation statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """
        Reset operation statistics.
        """
        self.stats = {
            'products_inserted': 0,
            'products_updated': 0,
            'products_skipped': 0,
            'database_errors': 0,
            'last_operation_time': None
        }
