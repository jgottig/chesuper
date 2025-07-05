"""
Data management module for the product scraper system.
Handles database operations, data validation, and persistence.
"""

import pandas as pd
import os
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime

from utils import (
    normalize_text, clean_product_name, validate_ean, 
    construct_image_url, calculate_data_completeness,
    merge_product_data, format_number, get_timestamp
)
from config import get_category_keywords
from database_manager import DatabaseManager

class DataManager:
    """
    Manages product data storage, retrieval, and database operations.
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize DataManager with configuration and logger.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.products_file = config['files']['products']
        self.category_keywords = get_category_keywords()
        
        # Initialize database manager
        self.db_manager = DatabaseManager(config, logger)
        
        # In-memory product storage (for compatibility)
        self.products: Dict[str, Dict[str, Any]] = {}
        self.products_loaded = False
        self.last_save_count = 0
        
    def load_existing_products(self) -> int:
        """
        Load existing products count from database.
        
        Returns:
            Number of existing products in database
        """
        try:
            # Test database connection first
            if not self.db_manager.test_database_connection():
                self.logger.error("Cannot connect to database")
                return 0
            
            # Skip counting for now to avoid blocking - just mark as loaded
            self.products_loaded = True
            self.last_save_count = 0
            
            self.logger.info("Database connection established - ready to process products")
            return 0  # Return 0 to avoid the slow count query
            
        except Exception as e:
            self.logger.error(f"Error connecting to database: {e}")
            return 0
    
    def add_product(self, product_data: Dict[str, Any]) -> bool:
        """
        Add or update a product in the database.
        
        Args:
            product_data: Product information dictionary
            
        Returns:
            True if product was added/updated, False otherwise
        """
        try:
            # Use database manager to add/update product
            result = self.db_manager.add_or_update_product(product_data)
            return result
        except Exception as e:
            self.logger.error(f"Error adding product to database: {e}")
            return False
    
    def _get_image_url(self, product_data: Dict[str, Any], ean: str) -> str:
        """
        Get or construct image URL for product.
        
        Args:
            product_data: Raw product data
            ean: Product EAN
            
        Returns:
            Image URL string
        """
        # Check if image URL is provided in data
        image_url = product_data.get('presentacion', product_data.get('imagen_url', ''))
        
        if image_url and image_url.startswith('http'):
            return image_url
        
        # Construct standard image URL
        return construct_image_url(ean, self.config['api']['image_base_url'])
    
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
        
        normalized_name = normalize_text(product_name)
        
        for category, keywords in self.category_keywords.items():
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
            return self.db_manager.get_product_count()
        except Exception as e:
            self.logger.error(f"Error getting product count from database: {e}")
            return 0
    
    def get_products_by_category(self) -> Dict[str, int]:
        """
        Get product count by category from database.
        
        Returns:
            Dictionary with category counts
        """
        try:
            return self.db_manager.get_products_by_category()
        except Exception as e:
            self.logger.error(f"Error getting products by category from database: {e}")
            return {}
    
    def should_save(self, force: bool = False) -> bool:
        """
        Determine if data should be saved based on batch size.
        For database operations, we save immediately, so this always returns True.
        
        Args:
            force: Force save regardless of batch size
            
        Returns:
            True (database saves are immediate)
        """
        return True  # Database operations are immediate
    
    def save_to_excel(self, force: bool = False) -> bool:
        """
        Database operations are immediate, so this method is kept for compatibility.
        
        Args:
            force: Force save regardless of batch size
            
        Returns:
            True (database operations are immediate)
        """
        # Database operations are immediate, no need to save
        self.logger.debug("Database operations are immediate - no batch saving needed")
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the product database.
        
        Returns:
            Statistics dictionary
        """
        try:
            return self.db_manager.get_statistics()
        except Exception as e:
            self.logger.error(f"Error getting statistics from database: {e}")
            return {'total_products': 0}
    
    def cleanup_duplicates(self) -> int:
        """
        Remove duplicate products based on name similarity from database.
        
        Returns:
            Number of duplicates removed
        """
        try:
            return self.db_manager.cleanup_duplicates()
        except Exception as e:
            self.logger.error(f"Error cleaning up duplicates in database: {e}")
            return 0
    
    def export_summary_report(self, filename: Optional[str] = None) -> str:
        """
        Export a summary report of the product database.
        
        Args:
            filename: Optional custom filename
            
        Returns:
            Path to the exported report
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"product_summary_report_{timestamp}.txt"
        
        stats = self.get_statistics()
        
        report_content = f"""
PRODUCT DATABASE SUMMARY REPORT
Generated: {stats['last_updated']}
{'=' * 50}

OVERVIEW:
- Total Products: {format_number(stats['total_products'])}
- Unique Brands: {format_number(stats['unique_brands'])}
- Average Completeness: {stats['avg_completeness']:.1%}
- Complete Products (≥80%): {format_number(stats['complete_products'])}
- Incomplete Products (<50%): {format_number(stats['incomplete_products'])}

CATEGORIES:
"""
        
        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / stats['total_products']) * 100
            report_content += f"- {category}: {format_number(count)} ({percentage:.1f}%)\n"
        
        report_content += f"\nTOP BRANDS:\n"
        for brand, count in stats['top_brands']:
            percentage = (count / stats['total_products']) * 100
            report_content += f"- {brand}: {format_number(count)} ({percentage:.1f}%)\n"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            self.logger.info(f"Summary report exported to: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Error exporting summary report: {e}")
            return ""
