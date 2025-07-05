"""
Unified Product Scraper for Rosario - Enhanced Version
Combines intelligent search strategies, robust error handling, and efficient data management.
"""

import sys
import signal
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from config import get_config, LOGGING_CONFIG
from utils import setup_logging, format_number, get_timestamp
from data_manager import DataManager
from api_client import APIClient
from search_strategy import SearchStrategy

class UnifiedProductScraper:
    """
    Main scraper class that orchestrates the entire product discovery process.
    """
    
    def __init__(self):
        """
        Initialize the unified scraper with all components.
        """
        # Load configuration
        self.config = get_config()
        
        # Setup logging
        self.logger = setup_logging(LOGGING_CONFIG)
        self.logger.info("=" * 60)
        self.logger.info("UNIFIED PRODUCT SCRAPER - ROSARIO")
        self.logger.info("=" * 60)
        
        # Initialize components
        self.data_manager = DataManager(self.config, self.logger)
        self.api_client = APIClient(self.config, self.logger)
        self.search_strategy = SearchStrategy(self.config, self.logger)
        
        # Scraping state
        self.is_running = False
        self.start_time = None
        self.products_added_this_session = 0
        self.searches_performed = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.is_running = False
    
    def run(self) -> bool:
        """
        Main scraping process.
        
        Returns:
            True if completed successfully
        """
        try:
            self.logger.info(f"Starting scraper for {self.config['location']['name']}")
            self.start_time = datetime.now()
            self.is_running = True
            
            # Test API connection
            if not self.api_client.test_connection():
                self.logger.error("API connection test failed. Aborting.")
                return False
            
            # Load existing products
            existing_count = self.data_manager.load_existing_products()
            self.logger.info(f"Starting with {format_number(existing_count)} existing products")
            
            # Generate search terms
            search_terms = self.search_strategy.generate_search_terms()
            if not search_terms:
                self.logger.error("No search terms generated. Check configuration.")
                return False
            
            self.logger.info(f"Generated {len(search_terms)} search terms")
            
            # Optimize search order
            optimized_terms = self.search_strategy.optimize_search_order(search_terms)
            
            # Main scraping loop
            self._scrape_products(optimized_terms)
            
            # Final save and cleanup
            self._finalize_scraping()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Critical error in main scraping process: {e}")
            return False
        finally:
            self.is_running = False
            self.api_client.close()
    
    def _scrape_products(self, search_terms: List[str]):
        """
        Main product scraping loop.
        
        Args:
            search_terms: List of search terms to process
        """
        total_terms = len(search_terms)
        
        for term_index, search_term in enumerate(search_terms, 1):
            if not self.is_running:
                self.logger.info("Scraping interrupted by user")
                break
            
            self.logger.info(f"[{term_index}/{total_terms}] Searching for: '{search_term}'")
            
            # Search with current term
            products_found = self._search_with_term(search_term)
            
            # Log progress
            if products_found > 0:
                self.logger.info(f"Found {products_found} new products with '{search_term}'")
            else:
                self.logger.debug(f"No new products found with '{search_term}'")
            
            # Show progress update after each search term
            self._log_progress_update()
            
            # Check if we should continue
            if not self._should_continue_scraping():
                self.logger.info("Stopping criteria met")
                break
    
    def _search_with_term(self, search_term: str) -> int:
        """
        Search for products using a specific term.
        
        Args:
            search_term: Search term to use
            
        Returns:
            Number of new products found
        """
        offset = 0
        page_number = 1
        products_found_this_term = 0
        pages_searched = 0
        has_more_pages = True
        
        while has_more_pages and self.is_running:
            # Check if we should continue with this term
            if not self.search_strategy.should_continue_search(
                search_term, pages_searched, products_found_this_term
            ):
                break
            
            # Make API request
            response_data = self.api_client.search_products(
                search_term, 
                offset=offset, 
                limit=self.config['api']['page_limit']
            )
            
            self.searches_performed += 1
            pages_searched += 1
            
            if not response_data:
                self.logger.warning(f"No response for '{search_term}' page {page_number}")
                break
            
            # Process products from response
            products = response_data.get('productos', [])
            if not products:
                has_more_pages = False
                break
            
            # Add products to database
            new_products_this_page = 0
            for i, product in enumerate(products, 1):
                if self.data_manager.add_product(product):
                    new_products_this_page += 1
                    products_found_this_term += 1
                    self.products_added_this_session += 1
                
                # Show progress every 10 products
                if i % 10 == 0:
                    self.logger.info(f"  Processing product {i}/{len(products)} on page {page_number}...")

            self.logger.info(f"'{search_term}' page {page_number}: "
                            f"{new_products_this_page} new products "
                            f"({len(products)} total on page)")
            
            # Prepare for next page
            offset += self.config['api']['page_limit']
            page_number += 1
            
            # Check if we've reached the end
            if len(products) < self.config['api']['page_limit']:
                has_more_pages = False
        
        # Record search results for optimization
        self.search_strategy.record_search_result(
            search_term, products_found_this_term, pages_searched
        )
        
        return products_found_this_term
    
    def _should_continue_scraping(self) -> bool:
        """
        Determine if scraping should continue based on various criteria.
        
        Returns:
            True if should continue scraping
        """
        # Check if user interrupted
        if not self.is_running:
            return False
        
        # Check API client health
        api_stats = self.api_client.get_statistics()
        if api_stats['circuit_breaker_open']:
            self.logger.warning("API circuit breaker is open, stopping")
            return False
        
        # Check if success rate is too low
        if (api_stats['total_requests'] > 50 and 
            api_stats['success_rate'] < 10):  # Less than 10% success rate
            self.logger.warning(f"API success rate too low ({api_stats['success_rate']}%), stopping")
            return False
        
        # Continue scraping
        return True
    
    def _finalize_scraping(self):
        """
        Finalize the scraping process with cleanup and reporting.
        """
        self.logger.info("Finalizing scraping process...")
        
        # Database operations are immediate, no need to force save
        self.logger.debug("Database operations are immediate - finalizing...")
        
        # Clean up duplicates
        duplicates_removed = self.data_manager.cleanup_duplicates()
        if duplicates_removed > 0:
            self.logger.info(f"Cleaned up {duplicates_removed} duplicate products")
        
        # Generate final reports
        self._generate_final_reports()
        
        # Log final statistics
        self._log_final_statistics()
    
    def _generate_final_reports(self):
        """
        Generate comprehensive reports about the scraping session.
        """
        try:
            # Data summary report
            data_report = self.data_manager.export_summary_report()
            if data_report:
                self.logger.info(f"Data summary report: {data_report}")
            
            # Search effectiveness report
            search_report = self.search_strategy.export_search_report()
            if search_report:
                self.logger.info(f"Search effectiveness report: {search_report}")
                
        except Exception as e:
            self.logger.error(f"Error generating reports: {e}")
    
    def _log_progress_update(self):
        """
        Log a progress update with current statistics.
        """
        if not self.start_time:
            return
        
        elapsed = datetime.now() - self.start_time
        total_products = self.data_manager.get_product_count()
        
        # Calculate rates
        products_per_hour = (self.products_added_this_session / 
                           max(elapsed.total_seconds() / 3600, 0.01))
        
        self.logger.info(f"PROGRESS UPDATE:")
        self.logger.info(f"  - Runtime: {str(elapsed).split('.')[0]}")
        self.logger.info(f"  - Total products: {format_number(total_products)}")
        self.logger.info(f"  - New this session: {format_number(self.products_added_this_session)}")
        self.logger.info(f"  - Rate: {products_per_hour:.1f} products/hour")
        self.logger.info(f"  - Searches performed: {format_number(self.searches_performed)}")
    
    def _log_final_statistics(self):
        """
        Log comprehensive final statistics.
        """
        if not self.start_time:
            return
        
        elapsed = datetime.now() - self.start_time
        
        # Get statistics from all components
        data_stats = self.data_manager.get_statistics()
        api_stats = self.api_client.get_statistics()
        search_stats = self.search_strategy.get_search_statistics()
        
        self.logger.info("=" * 60)
        self.logger.info("SCRAPING SESSION COMPLETED")
        self.logger.info("=" * 60)
        
        # Session overview
        self.logger.info(f"Session Duration: {str(elapsed).split('.')[0]}")
        self.logger.info(f"Location: {self.config['location']['name']}")
        self.logger.info(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Product statistics
        self.logger.info(f"\nPRODUCT STATISTICS:")
        self.logger.info(f"  - Total products in database: {format_number(data_stats['total_products'])}")
        self.logger.info(f"  - New products this session: {format_number(self.products_added_this_session)}")
        self.logger.info(f"  - Average data completeness: {data_stats['avg_completeness']:.1%}")
        self.logger.info(f"  - Categories found: {len(data_stats['categories'])}")
        self.logger.info(f"  - Unique brands: {format_number(data_stats['unique_brands'])}")
        
        # API statistics
        self.logger.info(f"\nAPI STATISTICS:")
        self.logger.info(f"  - Total requests: {format_number(api_stats['total_requests'])}")
        self.logger.info(f"  - Success rate: {api_stats['success_rate']:.1f}%")
        self.logger.info(f"  - Rate limited requests: {format_number(api_stats['rate_limited_requests'])}")
        self.logger.info(f"  - Failed requests: {format_number(api_stats['failed_requests'])}")
        
        # Search statistics
        self.logger.info(f"\nSEARCH STATISTICS:")
        self.logger.info(f"  - Search terms tried: {format_number(search_stats['total_terms_tried'])}")
        self.logger.info(f"  - Total searches performed: {format_number(search_stats['total_attempts'])}")
        self.logger.info(f"  - Average effectiveness: {search_stats['avg_effectiveness']:.3f} products/page")
        
        # Performance metrics
        if elapsed.total_seconds() > 0:
            products_per_hour = (self.products_added_this_session / 
                               (elapsed.total_seconds() / 3600))
            requests_per_minute = (api_stats['total_requests'] / 
                                 max(elapsed.total_seconds() / 60, 0.01))
            
            self.logger.info(f"\nPERFORMANCE METRICS:")
            self.logger.info(f"  - Products per hour: {products_per_hour:.1f}")
            self.logger.info(f"  - API requests per minute: {requests_per_minute:.1f}")
        
        # Top categories
        if data_stats['categories']:
            self.logger.info(f"\nTOP CATEGORIES:")
            sorted_categories = sorted(data_stats['categories'].items(), 
                                     key=lambda x: x[1], reverse=True)
            for category, count in sorted_categories[:5]:
                percentage = (count / data_stats['total_products']) * 100
                self.logger.info(f"  - {category}: {format_number(count)} ({percentage:.1f}%)")
        
        self.logger.info("=" * 60)

def main():
    """
    Main entry point for the unified scraper.
    """
    scraper = UnifiedProductScraper()
    
    try:
        success = scraper.run()
        if success:
            scraper.logger.info("Scraping completed successfully!")
            return 0
        else:
            scraper.logger.error("Scraping failed!")
            return 1
            
    except KeyboardInterrupt:
        scraper.logger.info("Scraping interrupted by user")
        return 0
    except Exception as e:
        scraper.logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
