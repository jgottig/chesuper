"""
Utility functions for the product scraper system.
Includes text normalization, data validation, and helper functions.
"""

import unicodedata
import re
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

def normalize_text(text: str) -> str:
    """
    Normalize text by removing accents, converting to lowercase, and cleaning.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text string
    """
    if not isinstance(text, str) or not text:
        return ""
    
    # Remove accents and diacritics
    nfkd_form = unicodedata.normalize('NFKD', text)
    text_without_accents = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
    
    # Convert to lowercase and clean
    normalized = text_without_accents.lower().strip()
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized

def clean_product_name(name: str) -> str:
    """
    Clean and standardize product names.
    
    Args:
        name: Raw product name
        
    Returns:
        Cleaned product name
    """
    if not name:
        return ""
    
    # Basic cleaning
    cleaned = name.strip()
    
    # Remove excessive punctuation
    cleaned = re.sub(r'[^\w\s\-\.\,\(\)\%]', ' ', cleaned)
    
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Capitalize first letter of each word
    cleaned = ' '.join(word.capitalize() for word in cleaned.split())
    
    return cleaned

def validate_ean(ean: str) -> bool:
    """
    Validate EAN (product ID) format.
    Enhanced to accept more formats including store codes and promotional IDs.
    
    Args:
        ean: EAN string to validate
        
    Returns:
        True if valid EAN format
    """
    if not ean or not isinstance(ean, str):
        return False
    
    # Remove hyphens and other separators that might be in web data
    cleaned_ean = ean.replace('-', '').replace('_', '').replace(' ', '')
    
    # Remove any non-digit characters for validation
    digits_only = re.sub(r'\D', '', cleaned_ean)
    
    # Accept EAN codes with 8+ digits (no upper limit for store codes)
    # This handles standard EANs, internal store codes, and promotional codes
    return len(digits_only) >= 8

def construct_image_url(ean: str, base_url: str = "https://imagenes.preciosclaros.gob.ar/productos") -> str:
    """
    Construct proper image URL for a product.
    
    Args:
        ean: Product EAN/ID
        base_url: Base URL for images
        
    Returns:
        Complete image URL
    """
    if not ean:
        return ""
    
    return f"{base_url}/{ean}.jpg"

def calculate_data_completeness(product: Dict[str, Any]) -> float:
    """
    Calculate completeness score for a product record.
    
    Args:
        product: Product dictionary
        
    Returns:
        Completeness score between 0.0 and 1.0
    """
    required_fields = ['ean', 'nombre', 'marca']
    optional_fields = ['imagen_url', 'categoria']
    
    score = 0.0
    total_weight = 0.0
    
    # Required fields (weight: 0.6)
    required_weight = 0.6 / len(required_fields)
    for field in required_fields:
        total_weight += required_weight
        if field in product and product[field] and str(product[field]).strip():
            score += required_weight
    
    # Optional fields (weight: 0.4)
    optional_weight = 0.4 / len(optional_fields)
    for field in optional_fields:
        total_weight += optional_weight
        if field in product and product[field] and str(product[field]).strip():
            score += optional_weight
    
    return min(score / total_weight if total_weight > 0 else 0.0, 1.0)

def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """
    Setup logging configuration.
    
    Args:
        config: Logging configuration dictionary
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('product_scraper')
    logger.setLevel(getattr(logging, config.get('level', 'INFO')))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler
    if config.get('file'):
        file_handler = logging.FileHandler(config['file'], encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Add file handler
        formatter = logging.Formatter(config.get('format', '%(asctime)s - %(levelname)s - %(message)s'))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Add console handler
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

def format_number(num: int) -> str:
    """
    Format number with thousands separator.
    
    Args:
        num: Number to format
        
    Returns:
        Formatted number string
    """
    return f"{num:,}"

def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        Current timestamp string
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters for Windows/Linux filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove excessive dots and spaces
    sanitized = re.sub(r'\.+', '.', sanitized)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return sanitized

def merge_product_data(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two product records, preferring non-empty values.
    
    Args:
        existing: Existing product data
        new: New product data
        
    Returns:
        Merged product data
    """
    merged = existing.copy()
    
    for key, value in new.items():
        if value and str(value).strip():
            # If existing value is empty or new value is more complete
            if not merged.get(key) or str(merged.get(key, '')).strip() == '':
                merged[key] = value
            elif key == 'nombre' and len(str(value)) > len(str(merged.get(key, ''))):
                # Prefer longer product names (usually more descriptive)
                merged[key] = value
    
    return merged

def extract_numeric_value(text: str) -> Optional[float]:
    """
    Extract numeric value from text (useful for prices, weights, etc.).
    
    Args:
        text: Text containing numeric value
        
    Returns:
        Extracted numeric value or None
    """
    if not text:
        return None
    
    # Find numeric patterns
    pattern = r'[\d,]+\.?\d*'
    matches = re.findall(pattern, str(text))
    
    if matches:
        try:
            # Take the first match and clean it
            value_str = matches[0].replace(',', '')
            return float(value_str)
        except ValueError:
            pass
    
    return None

def is_valid_url(url: str) -> bool:
    """
    Check if URL is valid.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL appears valid
    """
    if not url or not isinstance(url, str):
        return False
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks of specified size.
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get value from dictionary with nested key support.
    
    Args:
        dictionary: Dictionary to search
        key: Key to find (supports dot notation for nested keys)
        default: Default value if key not found
        
    Returns:
        Value or default
    """
    try:
        if '.' in key:
            keys = key.split('.')
            value = dictionary
            for k in keys:
                value = value[k]
            return value
        else:
            return dictionary.get(key, default)
    except (KeyError, TypeError):
        return default
