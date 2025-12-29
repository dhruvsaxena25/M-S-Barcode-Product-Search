"""
Barcode Scanner Core Module
Handles barcode detection from camera/image with wildcard UPC matching support.
"""

import cv2
import logging
from pathlib import Path
from typing import List, Optional, Set, Dict
from pyzbar.pyzbar import decode

from src.models.catalog import ProductCatalog
from src.models.product import Product

logger = logging.getLogger(__name__)


# ============================================
# BARCODE SCANNER CLASS
# ============================================

class BarcodeScanner:
    """
    Barcode scanner with API and local mode support.
    
    Features:
    - Real-time camera scanning
    - Static image scanning
    - Wildcard UPC matching (substring matching)
    - Catalog mode (product lookup)
    - UPC-only mode (direct UPC detection)
    - Category filtering
    """
    
    def __init__(self, camera_index: int = 0):
        """
        Initialize barcode scanner instance.
        
        Args:
            camera_index: Camera device index (0 = default camera)
        """
        self.camera_index = camera_index
        self.cap = None  # Don't open camera in __init__ for API mode
        self.catalog: Optional[ProductCatalog] = None
        self._allowed_upcs: Set[str] = set()
        self._match_types: Dict[str, str] = {}
        self._is_initialized = False
        self._upc_only_mode = False
        logger.info(f"Scanner instance created (camera {camera_index})")
    
    # ============================================
    # WILDCARD MATCHING UTILITIES
    # ============================================
    
    @staticmethod
    def match_upc_wildcard(scanned_upc: str, stored_upc: str) -> bool:
        """
        Check if scanned UPC contains stored UPC as substring.
        
        This enables matching long barcodes (e.g., "101526293771070000") 
        with shorter product UPCs (e.g., "29377107").
        
        Args:
            scanned_upc: Full barcode scanned from camera/image
            stored_upc: Product UPC stored in catalog/database
            
        Returns:
            True if stored_upc is found anywhere in scanned_upc
            
        Examples:
            >>> BarcodeScanner.match_upc_wildcard("101526293771070000", "29377107")
            True
            >>> BarcodeScanner.match_upc_wildcard("29377107", "29377107")
            True
            >>> BarcodeScanner.match_upc_wildcard("12345678", "29377107")
            False
        """
        return stored_upc in scanned_upc
    
    @staticmethod
    def find_matching_upc(scanned_upc: str, allowed_upcs: Set[str]) -> Optional[str]:
        """
        Find which stored UPC matches the scanned barcode using wildcard matching.
        
        Iterates through all allowed UPCs and returns the first one that
        appears as a substring in the scanned barcode.
        
        Args:
            scanned_upc: Full barcode string from scanner
            allowed_upcs: Set of valid product UPCs to match against
            
        Returns:
            Matched stored UPC or None if no match found
            
        Examples:
            >>> BarcodeScanner.find_matching_upc("101526293771070000", {"29377107", "12345678"})
            "29377107"
            >>> BarcodeScanner.find_matching_upc("99999999", {"29377107", "12345678"})
            None
        """
        for stored_upc in allowed_upcs:
            if BarcodeScanner.match_upc_wildcard(scanned_upc, stored_upc):
                return stored_upc
        return None
    
    # ============================================
    # INITIALIZATION
    # ============================================
    
    def initialize(self, catalog: Optional[ProductCatalog] = None, upc_only: bool = False):
        """
        Initialize scanner with catalog or UPC-only mode.
        
        Must be called before scanning operations.
        
        Args:
            catalog: ProductCatalog instance for product lookup (None for UPC-only)
            upc_only: If True, only detect UPCs without product lookup
        """
        self._upc_only_mode = upc_only
        
        if upc_only:
            logger.info("🚀 UPC-ONLY mode initialized")
            self._is_initialized = True
            return
        
        if catalog:
            self.catalog = catalog
            self._allowed_upcs = self.catalog.all_upcs()
            logger.info(f"📦 Catalog initialized: {len(catalog.products)} products")
        
        self._is_initialized = True
    
    def set_filter(self, queries: List[str], upc_only: bool = False,
                   main_category: Optional[str] = None,
                   subcategory: Optional[str] = None) -> tuple[bool, List]:
        """
        Set UPC filter with optional category filtering.
        
        Defines which products/UPCs the scanner should detect.
        In catalog mode, searches products by name and filters by category.
        In UPC-only mode, treats queries as direct UPC codes.
        
        Args:
            queries: List of product names (catalog mode) or UPC codes (UPC mode)
            upc_only: If True, treat queries as UPC codes directly
            main_category: Filter by main category (e.g., "ambient", "cold_chain")
            subcategory: Filter by subcategory (e.g., "Biscuits", "Dessert")
            
        Returns:
            Tuple of (success: bool, matched_products: List[dict])
            
        Examples:
            # Catalog mode with category filter
            >>> scanner.set_filter(["Cookie", "Biscuit"], main_category="ambient")
            (True, [{"name": "Chocolate Cookie", "upc": "12345", ...}, ...])
            
            # UPC-only mode
            >>> scanner.set_filter(["29377107", "12345678"], upc_only=True)
            (True, [{"name": "UPC: 29377107", "upc": "29377107", ...}, ...])
        """
        if not self._is_initialized:
            logger.error("Scanner not initialized!")
            return False, []
        
        self._upc_only_mode = upc_only
        self._allowed_upcs.clear()
        self._match_types.clear()
        
        if upc_only:
            # UPC-only mode: skip catalog, use queries directly
            self._allowed_upcs = {q.strip() for q in queries if q.strip()}
            logger.info(f"🔍 UPC-only filter: {len(self._allowed_upcs)} UPCs")
            logger.info(f"   Allowed UPCs: {self._allowed_upcs}")
            
            return True, [
                {"name": f"UPC: {upc}", "upc": upc, "match_type": "upc"}
                for upc in self._allowed_upcs
            ]
        
        if not self.catalog:
            logger.error("No catalog available for filtering")
            return False, []
        
        # Catalog mode: find products with category filter
        matched_products = self.catalog.find_multiple(
            queries, 
            main_category=main_category,
            subcategory=subcategory
        )
        
        if not matched_products:
            logger.warning(f"No products found for queries: {queries}")
            return False, []
        
        # Build allowed UPCs
        for product in matched_products:
            upc = str(product.upc)
            self._allowed_upcs.add(upc)
            self._match_types[upc] = getattr(product, '_match_type', 'full')
        
        logger.info(f"✅ Filter set: {len(matched_products)} products")
        logger.info(f"   Category: {main_category}/{subcategory}")
        logger.info(f"   Allowed UPCs: {self._allowed_upcs}")
        
        return True, [
            {
                "name": p.name,
                "upc": str(p.upc),
                "main_category": p.main_category,
                "subcategory": p.subcategory,
                "match_type": getattr(p, '_match_type', 'full')
            }
            for p in matched_products
        ]
    
    # ============================================
    # LOCAL CAMERA MODE (for main.py testing)
    # ============================================
    
    def scan_camera(self, duration_seconds: int = 30) -> List[dict]:
        """
        Scan from local camera with OpenCV window display.
        
        Opens camera, displays live video with detection overlays,
        and collects all detected barcodes for the specified duration.
        Press 'q' to quit early.
        
        Args:
            duration_seconds: How long to scan (0 = infinite, press 'q' to stop)
            
        Returns:
            List of all detected matches with product details
            
        Note:
            This is for local testing with main.py. 
            API mode uses _process_frame() directly without opening camera.
        """
        # Open camera only when needed
        if not self.cap:
            self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            logger.error("❌ Camera not available")
            return []
        
        logger.info(f"📹 Camera scanning for {duration_seconds}s... Press 'q' to quit")
        all_matches = []
        
        start_time = cv2.getTickCount()
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Failed to read frame")
                break
            
            # Process frame WITH display
            matches = self._process_frame(frame, display=True)
            all_matches.extend(matches)
            
            # Show window
            cv2.imshow("Barcode Scanner", frame)
            
            # Check for quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.info("User quit scanning")
                break
            
            # Check duration
            if duration_seconds:
                elapsed = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
                if elapsed > duration_seconds:
                    logger.info(f"Duration {duration_seconds}s reached")
                    break
        
        self.cap.release()
        cv2.destroyAllWindows()
        logger.info(f"✅ Scan complete: {len(all_matches)} detections")
        return all_matches
    
    def scan_image(self, image_path: Path) -> List[dict]:
        """
        Scan barcodes from a static image file.
        
        Loads image from disk and processes it for barcode detection.
        Useful for testing or batch processing.
        
        Args:
            image_path: Path to image file (JPG, PNG, etc.)
            
        Returns:
            List of detected matches
        """
        if not image_path.exists():
            logger.error(f"Image not found: {image_path}")
            return []
        
        frame = cv2.imread(str(image_path))
        if frame is None:
            logger.error(f"Could not read image: {image_path}")
            return []
        
        # Process WITHOUT display
        matches = self._process_frame(frame, display=False)
        logger.info(f"Image scan: {len(matches)} detections")
        return matches
    
    # ============================================
    # CORE FRAME PROCESSING WITH WILDCARD MATCHING
    # ============================================
    
    def _process_frame(self, frame, display: bool = False) -> List[dict]:
        """
        Process single frame and return detections with wildcard UPC matching.
        
        This is the core detection logic that:
        1. Decodes all barcodes in the frame
        2. Uses wildcard matching to find stored UPCs in scanned codes
        3. Looks up product details (catalog mode) or returns UPC (UPC-only mode)
        4. Optionally draws detection boxes on frame
        
        Args:
            frame: OpenCV image (numpy array) to process
            display: If True, draw rectangles/labels on frame for visualization
        
        Returns:
            List of detection dictionaries containing:
            - Catalog mode: {"product": {...}, "upc": "...", "raw_upc": "...", "match_type": "..."}
            - UPC-only mode: {"upc": "...", "raw_upc": "...", "type": "...", "match_type": "upc"}
            
        Note:
            Uses find_matching_upc() for wildcard substring matching.
            Example: Scanned "101526293771070000" matches stored "29377107"
        """
        if frame is None or frame.size == 0:
            return []
        
        # Decode all barcodes in frame
        try:
            barcodes = decode(frame)
        except Exception as e:
            logger.error(f"Barcode decode error: {e}")
            return []
        
        matches = []
        
        for barcode in barcodes:
            try:
                # Decode barcode data (full scanned code)
                scanned_upc = barcode.data.decode("utf-8")
                
                # ✅ WILDCARD MATCHING: Find which stored UPC matches
                matched_upc = self.find_matching_upc(scanned_upc, self._allowed_upcs)
                
                # Skip if no match found
                if not matched_upc:
                    continue
                
                # Log wildcard match (if different)
                if scanned_upc != matched_upc:
                    logger.info(f"🔍 Wildcard match: {scanned_upc} contains → {matched_upc}")
                else:
                    logger.info(f"✅ Exact match: {scanned_upc}")
                
                # Get match info for color coding
                match_info = self._get_match_info(matched_upc)
                
                if self._upc_only_mode:
                    # UPC-only mode detection
                    detection = {
                        "upc": matched_upc,  # Stored UPC
                        "raw_upc": scanned_upc,  # Full scanned code
                        "type": barcode.type,
                        "match_type": "upc"
                    }
                    matches.append(detection)
                    
                    if display:
                        label = f"UPC: {matched_upc}"
                        if scanned_upc != matched_upc:
                            label += f" (scanned: {scanned_upc[:10]}...)"
                        self._draw_detection(frame, barcode, label, 
                                           (0, 255, 255), "UPC")
                
                else:
                    # Catalog mode detection - lookup product by matched UPC
                    product = self.catalog.find_by_upc(matched_upc)
                    if product:
                        detection = {
                            "product": product.model_dump(),
                            "upc": matched_upc,  # Stored UPC
                            "raw_upc": scanned_upc,  # Full scanned code
                            "match_type": match_info['type'].lower()
                        }
                        matches.append(detection)
                        
                        if display:
                            label = f"{product.name} [{match_info['type']}]"
                            if scanned_upc != matched_upc:
                                label += f" (scanned: {scanned_upc[:10]}...)"
                            self._draw_detection(frame, barcode, label, 
                                               match_info['color'], match_info['type'])
                
            except Exception as e:
                logger.error(f"Error processing barcode: {e}")
                continue
        
        return matches
    
    def _get_match_info(self, upc: str) -> dict:
        """
        Get color and type info for match quality visualization.
        
        Determines the display color and label based on match quality:
        - FULL match (green): Exact product name match
        - PARTIAL match (orange): Substring match in product name
        - UPC match (yellow): UPC-only mode
        
        Args:
            upc: The matched UPC code
            
        Returns:
            Dict with "type" (str) and "color" (BGR tuple) keys
        """
        if self._upc_only_mode:
            return {
                "type": "UPC",
                "color": (0, 255, 255)  # Yellow (BGR)
            }
        
        match_type = self._match_types.get(upc, 'full')
        
        if match_type == "full":
            return {
                "type": "FULL",
                "color": (0, 255, 0)  # Green (BGR)
            }
        elif match_type == "partial":
            return {
                "type": "PARTIAL",
                "color": (0, 165, 255)  # Orange (BGR)
            }
        
        # Default to full match
        return {
            "type": "FULL",
            "color": (0, 255, 0)
        }
    
    def _draw_detection(self, frame, barcode, label: str, color: tuple, match_type: str):
        """
        Draw bounding box and label on frame for detected barcode.
        
        Draws:
        - Colored rectangle around barcode
        - Label background (filled rectangle)
        - Label text with product name and match type
        
        Args:
            frame: OpenCV image to draw on (modified in-place)
            barcode: Pyzbar barcode object with rect attribute
            label: Text to display above barcode
            color: BGR color tuple for rectangle and background
            match_type: Match type string (for logging)
        """
        try:
            x, y, w, h = barcode.rect
            
            # Draw bounding rectangle around barcode
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
            # Calculate label size for background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # Draw label background (filled rectangle)
            cv2.rectangle(frame, (x, y - label_size[1] - 10), 
                         (x + label_size[0], y), color, -1)
            
            # Draw label text (black on colored background)
            cv2.putText(frame, label, (x, y - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
            
        except Exception as e:
            logger.error(f"Draw error: {e}")
    
    def close(self):
        """
        Clean up resources and release camera.
        
        Call this when done scanning to properly release the camera
        and close any OpenCV windows.
        """
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()
        logger.info("Scanner closed")


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    """
    Test wildcard UPC matching functionality.
    """
    print("\n" + "="*60)
    print("🧪 TESTING BARCODE SCANNER - WILDCARD UPC MATCHING")
    print("="*60)
    
    # Test 1: match_upc_wildcard
    print("\n📋 Test 1: match_upc_wildcard()")
    print("-" * 60)
    
    test_cases = [
        ("101526293771070000", "29377107", True, "Long barcode contains product UPC"),
        ("29377107", "29377107", True, "Exact match"),
        ("29377107000", "29377107", True, "Product UPC at start"),
        ("00029377107", "29377107", True, "Product UPC at end"),
        ("12345678", "29377107", False, "No match"),
        ("101526293771070000", "12345678", False, "Different UPC"),
    ]
    
    for scanned, stored, expected, description in test_cases:
        result = BarcodeScanner.match_upc_wildcard(scanned, stored)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"{status} | {description}")
        print(f"       Scanned: {scanned}")
        print(f"       Stored:  {stored}")
        print(f"       Result:  {result} (expected: {expected})")
        print()
    
    # Test 2: find_matching_upc
    print("\n📋 Test 2: find_matching_upc()")
    print("-" * 60)
    
    allowed_upcs = {"29377107", "12345678", "99999999"}
    print(f"Allowed UPCs: {allowed_upcs}\n")
    
    test_scans = [
        ("101526293771070000", "29377107", "Long barcode with embedded UPC"),
        ("29377107", "29377107", "Exact match"),
        ("12345678000", "12345678", "UPC with trailing zeros"),
        ("88888888", None, "No match"),
        ("00099999999", "99999999", "UPC with leading zeros"),
    ]
    
    for scanned, expected, description in test_scans:
        matched = BarcodeScanner.find_matching_upc(scanned, allowed_upcs)
        status = "✅ PASS" if matched == expected else "❌ FAIL"
        print(f"{status} | {description}")
        print(f"       Scanned: {scanned}")
        print(f"       Matched: {matched} (expected: {expected})")
        print()
    
    print("="*60)
    print("✅ Testing complete!")
    print("="*60)
