import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from .product import Product

logger = logging.getLogger(__name__)


class ProductCatalog:
    """
    Catalog supporting nested category structure:
    {
      "ambient": {
        "Biscuits": [
          {"name": "...", "upc": "..."},
          ...
        ]
      },
      "cold_chain": {
        "Dessert": [...]
      }
    }
    """
    
    def __init__(self, products_file: Path):
        self.products_file = products_file
        self.products: List[Product] = []
        
        # Indexes
        self._by_upc: Dict[str, Product] = {}
        self._by_name: Dict[str, Product] = {}
        
        # Category structure
        self.categories: Dict[str, Dict[str, List[Product]]] = {}
        
        self._load()
    
    def _load(self):
        """Load products from nested JSON structure"""
        try:
            with self.products_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.products = []
            self.categories = {}
            
            # Parse nested structure
            for main_category, subcategories in data.items():
                if not isinstance(subcategories, dict):
                    logger.warning(f"Skipping invalid category: {main_category}")
                    continue
                
                self.categories[main_category] = {}
                
                for subcategory, products_list in subcategories.items():
                    if not isinstance(products_list, list):
                        logger.warning(f"Skipping invalid subcategory: {main_category}.{subcategory}")
                        continue
                    
                    category_products = []
                    
                    for item in products_list:
                        if "name" not in item or "upc" not in item:
                            logger.warning(f"Skipping invalid product: {item}")
                            continue
                        
                        # Create Product with category metadata
                        product_data = {
                            "name": item["name"],
                            "upc": str(item["upc"])
                        }
                        
                        product = Product.model_validate(product_data)
                        
                        # Add category metadata
                        product.main_category = main_category
                        product.subcategory = subcategory
                        
                        category_products.append(product)
                        self.products.append(product)
                    
                    self.categories[main_category][subcategory] = category_products
            
            self._build_indexes()
            
            logger.info(
                f"✅ Loaded {len(self.products)} products from "
                f"{len(self.categories)} main categories"
            )
            
            # Log category summary
            for main_cat, subcats in self.categories.items():
                total = sum(len(prods) for prods in subcats.values())
                logger.info(f"  📦 {main_cat}: {total} products in {len(subcats)} subcategories")
        
        except Exception as e:
            logger.error(f"Failed to load products: {e}")
            raise
    
    def _build_indexes(self):
        """Build lookup indexes"""
        self._by_upc.clear()
        self._by_name.clear()
        
        for product in self.products:
            self._by_upc[str(product.upc)] = product
            self._by_name[product.name.lower()] = product
    
    def find_by_upc(self, upc: str) -> Optional[Product]:
        """Find product by UPC code"""
        return self._by_upc.get(str(upc))
    
    def find_by_name(self, name: str) -> Optional[Product]:
        """Find product by exact name (case-insensitive)"""
        return self._by_name.get(name.lower())
    
    def find_by_category(
        self, 
        main_category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> List[Product]:
        """
        Get products by category
        
        Args:
            main_category: Main category filter (e.g., "ambient")
            subcategory: Subcategory filter (e.g., "Biscuits")
        
        Returns:
            List of matching products
        """
        if main_category and subcategory:
            # Specific subcategory
            return self.categories.get(main_category, {}).get(subcategory, [])
        
        elif main_category:
            # All products in main category
            results = []
            for subcat_products in self.categories.get(main_category, {}).values():
                results.extend(subcat_products)
            return results
        
        else:
            # All products
            return self.products.copy()
    
    def find_multiple(
        self, 
        queries: List[str],
        main_category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> List[Product]:
        """
        Find products matching queries with optional category filter
        
        Args:
            queries: List of product names or UPC codes
            main_category: Optional main category filter
            subcategory: Optional subcategory filter
        
        Returns:
            List of matched products with _match_type attribute
        """
        # Get candidate products from category
        candidates = self.find_by_category(main_category, subcategory)
        
        if not candidates:
            logger.warning(f"No products in category {main_category}/{subcategory}")
            return []
        
        results = []
        seen_upcs = set()
        
        for raw_query in queries:
            query = raw_query.strip()
            if not query:
                continue
            
            matched = False
            
            # 1. Exact UPC match → FULL (GREEN)
            if product := self.find_by_upc(query):
                # Check if product is in category filter
                if product in candidates:
                    if product.upc not in seen_upcs:
                        product._match_type = "full"
                        results.append(product)
                        seen_upcs.add(product.upc)
                        logger.info(f"✅ UPC match: '{query}' → '{product.name}'")
                        matched = True
            
            # 2. Exact name match → FULL (GREEN)
            elif product := self.find_by_name(query):
                if product in candidates:
                    if product.upc not in seen_upcs:
                        product._match_type = "full"
                        results.append(product)
                        seen_upcs.add(product.upc)
                        logger.info(f"✅ Name match: '{query}' → '{product.name}'")
                        matched = True
            
            # 3. Partial match → PARTIAL (ORANGE)
            if not matched:
                lower_query = query.lower()
                for product in candidates:
                    if product.upc in seen_upcs:
                        continue
                    
                    if (lower_query in product.name.lower() or 
                        product.name.lower() in lower_query):
                        product._match_type = "partial"
                        results.append(product)
                        seen_upcs.add(product.upc)
                        logger.info(f"🟠 Partial match: '{query}' → '{product.name}'")
                        matched = True
                        break
            
            if not matched:
                logger.warning(f"❌ No match for: '{query}'")
        
        return results
    
    def get_categories(self) -> Dict[str, List[str]]:
        """
        Get all categories and subcategories
        
        Returns:
            Dict mapping main categories to list of subcategories
        """
        return {
            main_cat: list(subcats.keys())
            for main_cat, subcats in self.categories.items()
        }
    
    def all_upcs(self) -> Set[str]:
        """Get all UPC codes in catalog"""
        return set(self._by_upc.keys())
    
    def get_stats(self) -> Dict:
        """Get catalog statistics"""
        stats = {
            "total_products": len(self.products),
            "main_categories": len(self.categories),
            "categories": {}
        }
        
        for main_cat, subcats in self.categories.items():
            stats["categories"][main_cat] = {
                "subcategories": len(subcats),
                "products": sum(len(prods) for prods in subcats.values()),
                "breakdown": {
                    subcat: len(prods)
                    for subcat, prods in subcats.items()
                }
            }
        
        return stats
