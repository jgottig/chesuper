"""
Search strategy module for the product scraper system.
Implements intelligent search algorithms and optimization.
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
import random
from collections import defaultdict, Counter

from config import get_search_keywords, get_category_keywords, get_common_brands
from utils import normalize_text, format_number

class SearchStrategy:
    """
    Manages intelligent search strategies for product discovery.
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize search strategy with configuration and logger.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        
        # Search terms and strategies
        self.smart_keywords = get_search_keywords()
        self.category_keywords = get_category_keywords()
        self.common_brands = get_common_brands()
        
        # Search effectiveness tracking
        self.search_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'attempts': 0,
            'products_found': 0,
            'pages_searched': 0,
            'effectiveness': 0.0,
            'last_used': None
        })
        
        # Used search terms to avoid repetition
        self.used_search_terms: Set[str] = set()
        
        # Character combinations for fallback
        self.base_chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
        
    def generate_search_terms(self) -> List[str]:
        """
        Generate optimized list of search terms based on strategy configuration.
        
        Returns:
            List of search terms ordered by expected effectiveness
        """
        search_terms = []
        
        # 1. Smart keywords (highest priority)
        if self.config['search']['use_smart_keywords']:
            search_terms.extend(self._get_smart_keyword_terms())
        
        # 2. Category-based searches
        if self.config['search']['use_categories']:
            search_terms.extend(self._get_category_based_terms())
        
        # 3. Brand-based searches
        if self.config['search']['use_brands']:
            search_terms.extend(self._get_brand_based_terms())
        
        # 4. Fallback to character combinations if enabled
        if self.config['search']['use_fallback_combinations']:
            search_terms.extend(self._get_fallback_combinations())
        
        # Remove duplicates while preserving order
        unique_terms = []
        seen = set()
        for term in search_terms:
            normalized_term = normalize_text(term)
            if normalized_term not in seen and normalized_term not in self.used_search_terms:
                unique_terms.append(term)
                seen.add(normalized_term)
        
        # Sort by effectiveness (if we have historical data)
        unique_terms.sort(key=self._get_term_effectiveness, reverse=True)
        
        self.logger.info(f"Generated {len(unique_terms)} unique search terms")
        return unique_terms
    
    def _get_smart_keyword_terms(self) -> List[str]:
        """
        Get smart keyword search terms.
        
        Returns:
            List of smart keyword terms
        """
        terms = self.smart_keywords.copy()
        
        # Add variations and combinations
        variations = []
        
        # Single character additions (common prefixes/suffixes)
        for keyword in self.smart_keywords[:20]:  # Limit to avoid explosion
            if len(keyword) >= 3:
                variations.extend([
                    f"{keyword}a",  # Common suffix
                    f"{keyword}s",  # Plural
                    f"la {keyword}",  # Common prefix
                    f"el {keyword}",  # Common prefix
                ])
        
        terms.extend(variations)
        return terms
    
    def _get_category_based_terms(self) -> List[str]:
        """
        Get category-based search terms.
        
        Returns:
            List of category-based terms
        """
        terms = []
        
        # Use keywords from each category
        for category, keywords in self.category_keywords.items():
            # Take top keywords from each category
            terms.extend(keywords[:5])  # Limit per category
        
        return terms
    
    def _get_brand_based_terms(self) -> List[str]:
        """
        Get brand-based search terms.
        
        Returns:
            List of brand-based terms
        """
        terms = []
        
        # Full brand names
        terms.extend(self.common_brands)
        
        # Brand name parts (for partial matching)
        brand_parts = []
        for brand in self.common_brands:
            parts = brand.split()
            for part in parts:
                if len(part) >= 3:  # Avoid very short parts
                    brand_parts.append(part)
        
        # Remove duplicates and add
        terms.extend(list(set(brand_parts)))
        
        return terms
    
    def _get_fallback_combinations(self) -> List[str]:
        """
        Get fallback character combinations (last resort).
        
        Returns:
            List of character combinations
        """
        combinations = []
        
        # Generate strategic 2-character combinations
        # Prioritize common letter combinations in Spanish
        common_pairs = [
            'ar', 'er', 'ir', 'or', 'ur',  # Common endings
            'la', 'el', 'de', 'en', 'es',  # Common words
            'an', 'in', 'on', 'un',        # Common patterns
            'al', 'il', 'ol', 'ul',        # More patterns
        ]
        
        combinations.extend(common_pairs)
        
        # Add some random combinations if needed
        if len(combinations) < 50:
            for _ in range(50 - len(combinations)):
                combo = ''.join(random.choices(self.base_chars, k=2))
                if combo not in combinations:
                    combinations.append(combo)
        
        return combinations
    
    def _get_term_effectiveness(self, term: str) -> float:
        """
        Get effectiveness score for a search term.
        
        Args:
            term: Search term to evaluate
            
        Returns:
            Effectiveness score (higher is better)
        """
        normalized_term = normalize_text(term)
        stats = self.search_stats.get(normalized_term)
        
        if not stats or stats['attempts'] == 0:
            # No historical data, use heuristics
            return self._estimate_term_effectiveness(term)
        
        return stats['effectiveness']
    
    def _estimate_term_effectiveness(self, term: str) -> float:
        """
        Estimate effectiveness of a term based on heuristics.
        
        Args:
            term: Search term to estimate
            
        Returns:
            Estimated effectiveness score
        """
        score = 0.5  # Base score
        
        # Longer terms are often more specific and effective
        if len(term) >= 4:
            score += 0.2
        elif len(term) <= 2:
            score -= 0.2
        
        # Common food/product terms are usually effective
        food_terms = ['leche', 'pan', 'aceite', 'agua', 'yogur', 'queso']
        if any(food_term in normalize_text(term) for food_term in food_terms):
            score += 0.3
        
        # Brand terms are often effective
        if any(brand.lower() in normalize_text(term) for brand in self.common_brands):
            score += 0.2
        
        # Very generic terms might be less effective
        generic_terms = ['a', 'e', 'i', 'o', 'u', 'x', 'y', 'z']
        if term.lower() in generic_terms:
            score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def record_search_result(self, search_term: str, products_found: int, pages_searched: int):
        """
        Record the results of a search for effectiveness tracking.
        
        Args:
            search_term: The search term used
            products_found: Number of products found
            pages_searched: Number of pages searched
        """
        normalized_term = normalize_text(search_term)
        stats = self.search_stats[normalized_term]
        
        stats['attempts'] += 1
        stats['products_found'] += products_found
        stats['pages_searched'] += pages_searched
        
        # Calculate effectiveness (products per page)
        if stats['pages_searched'] > 0:
            stats['effectiveness'] = stats['products_found'] / stats['pages_searched']
        
        # Mark as used
        self.used_search_terms.add(normalized_term)
        
        self.logger.debug(f"Search '{search_term}': {products_found} products, {pages_searched} pages, effectiveness: {stats['effectiveness']:.2f}")
    
    def get_next_search_term(self, available_terms: List[str]) -> Optional[str]:
        """
        Get the next most promising search term.
        
        Args:
            available_terms: List of available search terms
            
        Returns:
            Next search term or None if exhausted
        """
        if not available_terms:
            return None
        
        # Filter out already used terms
        unused_terms = [
            term for term in available_terms 
            if normalize_text(term) not in self.used_search_terms
        ]
        
        if not unused_terms:
            self.logger.info("All search terms have been used")
            return None
        
        # Return the most promising term
        best_term = max(unused_terms, key=self._get_term_effectiveness)
        return best_term
    
    def should_continue_search(self, current_term: str, pages_searched: int, products_found: int) -> bool:
        """
        Determine if we should continue searching with the current term.
        
        Args:
            current_term: Current search term
            pages_searched: Pages searched so far for this term
            products_found: Products found so far for this term
            
        Returns:
            True if should continue searching
        """
        # Always search at least one page
        if pages_searched == 0:
            return True
        
        # Stop if we've searched too many pages without results
        if pages_searched >= 10 and products_found == 0:
            return False
        
        # Stop if effectiveness is very low
        if pages_searched >= 5:
            effectiveness = products_found / pages_searched
            if effectiveness < 0.1:  # Less than 0.1 products per page
                return False
        
        # Continue if we're still finding products
        return True
    
    def optimize_search_order(self, terms: List[str]) -> List[str]:
        """
        Optimize the order of search terms based on historical performance.
        
        Args:
            terms: List of search terms to optimize
            
        Returns:
            Optimized list of search terms
        """
        # Separate terms into categories
        high_performers = []
        medium_performers = []
        untested = []
        
        for term in terms:
            normalized_term = normalize_text(term)
            if normalized_term in self.search_stats:
                effectiveness = self.search_stats[normalized_term]['effectiveness']
                if effectiveness >= 0.5:
                    high_performers.append(term)
                else:
                    medium_performers.append(term)
            else:
                untested.append(term)
        
        # Sort each category
        high_performers.sort(key=self._get_term_effectiveness, reverse=True)
        medium_performers.sort(key=self._get_term_effectiveness, reverse=True)
        untested.sort(key=self._estimate_term_effectiveness, reverse=True)
        
        # Combine: high performers first, then untested, then medium performers
        optimized = high_performers + untested + medium_performers
        
        self.logger.info(f"Optimized search order: {len(high_performers)} high performers, "
                        f"{len(untested)} untested, {len(medium_performers)} medium performers")
        
        return optimized
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive search statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self.search_stats:
            return {'total_terms_tried': 0}
        
        total_attempts = sum(stats['attempts'] for stats in self.search_stats.values())
        total_products = sum(stats['products_found'] for stats in self.search_stats.values())
        total_pages = sum(stats['pages_searched'] for stats in self.search_stats.values())
        
        # Calculate effectiveness distribution
        effectiveness_scores = [stats['effectiveness'] for stats in self.search_stats.values() if stats['attempts'] > 0]
        
        if effectiveness_scores:
            avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores)
            max_effectiveness = max(effectiveness_scores)
            min_effectiveness = min(effectiveness_scores)
        else:
            avg_effectiveness = max_effectiveness = min_effectiveness = 0.0
        
        # Top performing terms
        top_terms = sorted(
            [(term, stats) for term, stats in self.search_stats.items() if stats['attempts'] > 0],
            key=lambda x: x[1]['effectiveness'],
            reverse=True
        )[:10]
        
        return {
            'total_terms_tried': len(self.search_stats),
            'total_attempts': total_attempts,
            'total_products_found': total_products,
            'total_pages_searched': total_pages,
            'avg_effectiveness': round(avg_effectiveness, 3),
            'max_effectiveness': round(max_effectiveness, 3),
            'min_effectiveness': round(min_effectiveness, 3),
            'top_performing_terms': [(term, round(stats['effectiveness'], 3)) for term, stats in top_terms],
            'terms_used': len(self.used_search_terms)
        }
    
    def reset_used_terms(self):
        """
        Reset the set of used search terms (for restarting searches).
        """
        old_count = len(self.used_search_terms)
        self.used_search_terms.clear()
        self.logger.info(f"Reset {old_count} used search terms")
    
    def export_search_report(self, filename: str = "search_effectiveness_report.txt") -> str:
        """
        Export a detailed search effectiveness report.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to exported report
        """
        stats = self.get_search_statistics()
        
        report_content = f"""
SEARCH EFFECTIVENESS REPORT
Generated: {format_number(stats.get('total_attempts', 0))} total searches
{'=' * 50}

OVERVIEW:
- Terms Tried: {stats.get('total_terms_tried', 0)}
- Total Searches: {format_number(stats.get('total_attempts', 0))}
- Products Found: {format_number(stats.get('total_products_found', 0))}
- Pages Searched: {format_number(stats.get('total_pages_searched', 0))}
- Average Effectiveness: {stats.get('avg_effectiveness', 0):.3f} products/page

EFFECTIVENESS RANGE:
- Maximum: {stats.get('max_effectiveness', 0):.3f} products/page
- Minimum: {stats.get('min_effectiveness', 0):.3f} products/page

TOP PERFORMING SEARCH TERMS:
"""
        
        for i, (term, effectiveness) in enumerate(stats.get('top_performing_terms', []), 1):
            report_content += f"{i:2d}. '{term}': {effectiveness:.3f} products/page\n"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            self.logger.info(f"Search effectiveness report exported to: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Error exporting search report: {e}")
            return ""
