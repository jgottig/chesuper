"""
Configuration file for the unified product scraper system.
Centralizes all settings for better maintainability and flexibility.
"""

import os
from typing import Dict, List, Any

# === ROSARIO CONFIGURATION ===
ROSARIO_CONFIG = {
    'location': {
        'name': 'Rosario',
        'lat': -32.9478,
        'lng': -60.6305
    },
    'files': {
        'products': 'base_de_productos_rosario.xlsx',
        'prices': 'precios_obtenidos_rosario.xlsx'
    },
    'api': {
        'products_url': 'https://d3e6htiiul5ek9.cloudfront.net/prod/productos',
        'product_detail_url': 'https://d3e6htiiul5ek9.cloudfront.net/prod/producto',
        'image_base_url': 'https://imagenes.preciosclaros.gob.ar/productos',
        'timeout': 15,
        'rate_limit': 1.2,  # seconds between requests
        'max_retries': 3,
        'retry_backoff': 2.0,  # exponential backoff multiplier
        'page_limit': 50
    },
    'search': {
        'use_smart_keywords': True,
        'use_categories': True,
        'use_brands': True,
        'use_fallback_combinations': True,  # Enable for maximum coverage
        'batch_save_size': 50,  # Save more frequently for safety
        'max_concurrent_requests': 3
    }
}

# === SMART SEARCH KEYWORDS ===
# Expanded high-value search terms for maximum product discovery
SMART_KEYWORDS = [
    # Basic food items
    'leche', 'pan', 'aceite', 'azucar', 'arroz', 'harina', 'sal', 'agua',
    'yogur', 'queso', 'manteca', 'huevo', 'pollo', 'carne', 'pescado',
    
    # Dairy specific terms (ADDED TO FIX CREMON ISSUE)
    'cremon', 'untable', 'cremoso', 'casancrem', 'finlandia', 'philadelphia',
    'dulce de leche', 'ricota', 'mascarpone', 'roquefort', 'cheddar',
    
    # Beverages
    'coca', 'pepsi', 'sprite', 'fanta', 'cerveza', 'vino', 'jugo', 'gaseosa',
    'agua', 'soda', 'energizante', 'isotonica', 'te', 'cafe', 'mate',
    
    # Cleaning products
    'detergente', 'lavandina', 'jabon', 'shampoo', 'papel', 'toalla',
    'limpiador', 'desinfectante', 'suavizante', 'esponja',
    
    # Snacks and sweets
    'chocolate', 'galletita', 'alfajor', 'caramelo', 'papas', 'snack',
    'cereales', 'barrita', 'gomita', 'chicle', 'turron',
    
    # Size and package variations
    '1l', '2l', '500ml', '1kg', '500g', '250g', '280g', 'pack', 'x6', 'x12',
    'docena', 'unidad', 'botella', 'lata', 'sachet', 'sobre',
    
    # Product modifiers
    'light', 'diet', 'integral', 'descremada', 'entera', 'sin', 'con',
    'extra', 'premium', 'clasico', 'original', 'natural',
    
    # Common brands (partial names)
    'nestle', 'unilever', 'arcor', 'marolio', 'molinos', 'sancor',
    'serenisima', 'quilmes', 'brahma', 'bimbo', 'bagley', 'terrabusi',
    
    # Generic terms and connectors
    'la', 'el', 'del', 'de', 'con', 'sin', 'para', 'super', 'mega',
    
    # Numbers and quantities
    '1', '2', '3', '4', '5', '6', '12', '24', '500', '1000',
    
    # Common food categories
    'dulce', 'salado', 'fresco', 'congelado', 'enlatado', 'instantaneo'
]

# === PRODUCT CATEGORIES WITH NORMALIZED KEYWORDS ===
PRODUCT_CATEGORIES = {
    "Almacén": [
        'aceite', 'vinagre', 'arroz', 'fideo', 'harina', 'azucar', 'sal', 
        'yerba', 'mate', 'te', 'cafe', 'cacao', 'mermelada', 'dulce de leche', 
        'galletita', 'legumbre', 'lenteja', 'garbanzo', 'poroto', 'enlatado', 
        'atun', 'sardina', 'choclo', 'arveja', 'salsa', 'pure de tomate', 
        'mayonesa', 'ketchup', 'mostaza', 'condimento', 'especias'
    ],
    "Lácteos y Frescos": [
        'leche', 'yogur', 'queso', 'crema', 'manteca', 'postre', 'flan', 
        'ricota', 'fiambre', 'jamon', 'salame', 'pascualina', 'tapa empanada',
        'huevo', 'leche en polvo', 'dulce de leche', 'cremon', 'untable',
        'cremoso', 'casancrem', 'finlandia', 'philadelphia', 'mascarpone',
        'roquefort', 'cheddar', 'mozzarella', 'parmesano', 'dambo'
    ],
    "Carnes y Pescados": [
        'carne', 'pollo', 'pescado', 'cerdo', 'cordero', 'milanesa', 
        'hamburguesa', 'salchicha', 'chorizo', 'morcilla'
    ],
    "Panificados": [
        'pan', 'pan lactal', 'budin', 'magdalena', 'factura', 'bizcocho',
        'tostada', 'galleta', 'masa'
    ],
    "Bebidas": [
        'gaseosa', 'agua', 'jugo', 'bebida', 'cerveza', 'vino', 'fernet', 
        'aperitivo', 'isotonica', 'energizante', 'soda', 'coca', 'pepsi',
        'sprite', 'fanta', 'manaos'
    ],
    "Limpieza": [
        'lavandina', 'detergente', 'limpiador', 'desengrasante', 'jabon en polvo', 
        'jabon liquido', 'suavizante', 'lustramuebles', 'insecticida', 
        'papel higienico', 'rollo de cocina', 'servilleta', 'bolsa de residuo',
        'esponja', 'trapo', 'escoba'
    ],
    "Higiene y Cuidado Personal": [
        'jabon de tocador', 'shampoo', 'acondicionador', 'crema de enjuague', 
        'desodorante', 'talco', 'protector solar', 'repelente', 'toalla femenina', 
        'pañal', 'crema dental', 'pasta dental', 'dentifrico', 'cepillo de diente', 
        'enjuague bucal', 'maquina de afeitar', 'espuma de afeitar', 'preservativo',
        'perfume', 'colonia'
    ],
    "Snacks y Golosinas": [
        'papas fritas', 'snack', 'mani', 'palitos salados', 'chupetin', 
        'caramelo', 'chocolate', 'alfajor', 'turron', 'chicle', 'gomita',
        'barrita', 'cereales'
    ],
    "Frutas y Verduras": [
        'banana', 'manzana', 'naranja', 'tomate', 'papa', 'cebolla', 
        'zanahoria', 'lechuga', 'apio', 'brocoli', 'zapallo'
    ],
    "Congelados": [
        'helado', 'hamburguesa congelada', 'papa congelada', 'verdura congelada',
        'pescado congelado', 'pollo congelado'
    ]
}

# === COMMON BRANDS ===
COMMON_BRANDS = [
    # Major beverage brands
    'coca cola', 'pepsi', 'sprite', 'fanta', 'quilmes', 'brahma', 'stella artois',
    'manaos', 'paso de los toros', 'villavicencio', 'ser', 'glaciar',
    
    # Food brands
    'nestle', 'arcor', 'marolio', 'molinos rio', 'bimbo', 'bagley', 'terrabusi',
    'georgalos', 'don satur', 'tita', 'oreo', 'club social', 'criollitas',
    
    # Dairy brands
    'la serenisima', 'sancor', 'milkaut', 'ilolay', 'tregar', 'verónica',
    'gandara', 'manfrey', 'santa rosa',
    
    # Cleaning and personal care
    'unilever', 'skip', 'ala', 'dove', 'head shoulders', 'pantene', 'sedal',
    'rexona', 'axe', 'clear', 'suave', 'johnson', 'colgate', 'oral b',
    
    # Supermarket brands
    'carrefour', 'coto', 'jumbo', 'disco', 'vea', 'dia', 'libertad',
    'la anonima', 'cordiez', 'precio uno',
    
    # Meat and cold cuts
    'swift', 'paladini', 'oscar mayer', 'fargo', 'cattivelli', 'granja tres arroyos',
    
    # Oil and condiments
    'cocinero', 'natura', 'lira', 'cañuelas', 'hellmanns', 'danica',
    
    # Partial brand names for broader matching
    'la', 'el', 'don', 'doña', 'san', 'santa', 'del', 'de la'
]

# === HTTP HEADERS ===
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site'
}

# === LOGGING CONFIGURATION ===
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'scraper.log',
    'max_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

def get_config() -> Dict[str, Any]:
    """Get the complete configuration dictionary."""
    return ROSARIO_CONFIG

def get_search_keywords() -> List[str]:
    """Get all smart search keywords."""
    return SMART_KEYWORDS

def get_category_keywords() -> Dict[str, List[str]]:
    """Get product categories with their keywords."""
    return PRODUCT_CATEGORIES

def get_common_brands() -> List[str]:
    """Get list of common brands to search for."""
    return COMMON_BRANDS
