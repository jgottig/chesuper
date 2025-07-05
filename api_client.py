"""
API client module for the product scraper system.
Handles HTTP requests, rate limiting, retries, and error handling.
"""

import requests
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import random

from config import DEFAULT_HEADERS

class APIClient:
    """
    Robust API client with rate limiting, retries, and error handling.
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize API client with configuration and logger.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        
        # Rate limiting
        self.last_request_time = 0
        self.rate_limit = config['api']['rate_limit']
        
        # Retry configuration
        self.max_retries = config['api']['max_retries']
        self.retry_backoff = config['api']['retry_backoff']
        self.timeout = config['api']['timeout']
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limited_requests = 0
        
        # Circuit breaker
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10
        self.circuit_breaker_timeout = 300  # 5 minutes
        self.circuit_breaker_reset_time = None
        
    def _wait_for_rate_limit(self):
        """
        Implement rate limiting by waiting between requests.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit:
            wait_time = self.rate_limit - time_since_last_request
            # Add small random jitter to avoid thundering herd
            wait_time += random.uniform(0, 0.2)
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _is_circuit_breaker_open(self) -> bool:
        """
        Check if circuit breaker is open (blocking requests).
        
        Returns:
            True if circuit breaker is open
        """
        if self.consecutive_failures < self.max_consecutive_failures:
            return False
        
        if self.circuit_breaker_reset_time is None:
            self.circuit_breaker_reset_time = datetime.now() + timedelta(seconds=self.circuit_breaker_timeout)
            self.logger.warning(f"Circuit breaker opened due to {self.consecutive_failures} consecutive failures")
            return True
        
        if datetime.now() >= self.circuit_breaker_reset_time:
            self.logger.info("Circuit breaker reset time reached, attempting to close")
            self.consecutive_failures = 0
            self.circuit_breaker_reset_time = None
            return False
        
        return True
    
    def _handle_request_success(self):
        """
        Handle successful request for circuit breaker and statistics.
        """
        self.consecutive_failures = 0
        self.circuit_breaker_reset_time = None
        self.successful_requests += 1
    
    def _handle_request_failure(self, error: Exception):
        """
        Handle failed request for circuit breaker and statistics.
        
        Args:
            error: Exception that occurred
        """
        self.consecutive_failures += 1
        self.failed_requests += 1
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.logger.error(f"Circuit breaker triggered after {self.consecutive_failures} failures")
    
    def search_products(self, search_term: str, offset: int = 0, limit: int = 50) -> Optional[Dict[str, Any]]:
        """
        Search for products using the API.
        
        Args:
            search_term: Term to search for
            offset: Pagination offset
            limit: Number of results per page
            
        Returns:
            API response data or None if failed
        """
        if self._is_circuit_breaker_open():
            self.logger.warning("Circuit breaker is open, skipping request")
            return None
        
        params = {
            'string': search_term,
            'lat': self.config['location']['lat'],
            'lng': self.config['location']['lng'],
            'limit': limit,
            'offset': offset
        }
        
        return self._make_request(self.config['api']['products_url'], params)
    
    def get_product_details(self, product_id: str, sucursales: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed product information including prices.
        
        Args:
            product_id: Product EAN/ID
            sucursales: Comma-separated list of store IDs
            
        Returns:
            API response data or None if failed
        """
        if self._is_circuit_breaker_open():
            self.logger.warning("Circuit breaker is open, skipping request")
            return None
        
        params = {
            'id_producto': product_id,
            'array_sucursales': sucursales
        }
        
        return self._make_request(self.config['api']['product_detail_url'], params)
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request with retries and error handling.
        
        Args:
            url: Request URL
            params: Request parameters
            
        Returns:
            Response data or None if failed
        """
        self.total_requests += 1
        
        for attempt in range(self.max_retries + 1):
            try:
                # Rate limiting
                self._wait_for_rate_limit()
                
                # Make request
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                
                # Handle different HTTP status codes
                if response.status_code == 200:
                    data = response.json()
                    self._handle_request_success()
                    return data
                
                elif response.status_code == 429:  # Rate limited
                    self.rate_limited_requests += 1
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    time.sleep(retry_after)
                    continue
                
                elif response.status_code in [500, 502, 503, 504]:  # Server errors
                    if attempt < self.max_retries:
                        wait_time = (self.retry_backoff ** attempt) + random.uniform(0, 1)
                        self.logger.warning(f"Server error {response.status_code}, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{self.max_retries + 1})")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Server error {response.status_code} after {self.max_retries} retries")
                        self._handle_request_failure(Exception(f"HTTP {response.status_code}"))
                        return None
                
                elif response.status_code == 404:  # Not found
                    self.logger.debug(f"Resource not found (404) for params: {params}")
                    return None
                
                else:  # Other client errors
                    self.logger.error(f"HTTP error {response.status_code}: {response.text}")
                    self._handle_request_failure(Exception(f"HTTP {response.status_code}"))
                    return None
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    wait_time = (self.retry_backoff ** attempt) + random.uniform(0, 1)
                    self.logger.warning(f"Request timeout, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{self.max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"Request timeout after {self.max_retries} retries")
                    self._handle_request_failure(Exception("Timeout"))
                    return None
            
            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries:
                    wait_time = (self.retry_backoff ** attempt) + random.uniform(0, 1)
                    self.logger.warning(f"Connection error, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{self.max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"Connection error after {self.max_retries} retries: {e}")
                    self._handle_request_failure(e)
                    return None
            
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error: {e}")
                self._handle_request_failure(e)
                return None
            
            except ValueError as e:  # JSON decode error
                self.logger.error(f"Invalid JSON response: {e}")
                self._handle_request_failure(e)
                return None
            
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                self._handle_request_failure(e)
                return None
        
        return None
    
    def test_connection(self) -> bool:
        """
        Test API connection with a simple request.
        
        Returns:
            True if connection is working
        """
        self.logger.info("Testing API connection...")
        
        try:
            # Simple test search
            result = self.search_products("test", limit=1)
            
            if result is not None:
                self.logger.info("API connection test successful")
                return True
            else:
                self.logger.warning("API connection test failed")
                return False
                
        except Exception as e:
            self.logger.error(f"API connection test error: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get API client statistics.
        
        Returns:
            Statistics dictionary
        """
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'rate_limited_requests': self.rate_limited_requests,
            'success_rate': round(success_rate, 2),
            'consecutive_failures': self.consecutive_failures,
            'circuit_breaker_open': self._is_circuit_breaker_open(),
            'rate_limit': self.rate_limit
        }
    
    def reset_statistics(self):
        """
        Reset API client statistics.
        """
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limited_requests = 0
        self.consecutive_failures = 0
        self.circuit_breaker_reset_time = None
        
        self.logger.info("API client statistics reset")
    
    def adjust_rate_limit(self, new_rate_limit: float):
        """
        Dynamically adjust rate limit based on API performance.
        
        Args:
            new_rate_limit: New rate limit in seconds
        """
        old_rate_limit = self.rate_limit
        self.rate_limit = max(0.1, min(10.0, new_rate_limit))  # Clamp between 0.1 and 10 seconds
        
        self.logger.info(f"Rate limit adjusted from {old_rate_limit}s to {self.rate_limit}s")
    
    def close(self):
        """
        Close the HTTP session and cleanup resources.
        """
        if self.session:
            self.session.close()
            self.logger.info("API client session closed")
    
    def __enter__(self):
        """
        Context manager entry.
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit.
        """
        self.close()
