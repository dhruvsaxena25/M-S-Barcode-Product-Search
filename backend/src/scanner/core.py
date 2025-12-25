# import cv2
# import logging
# from pathlib import Path
# from typing import List, Optional, Set, Dict
# from pyzbar.pyzbar import decode

# from src.models.catalog import ProductCatalog
# from src.models.product import Product

# logger = logging.getLogger(__name__)


# class BarcodeScanner:
#     """Barcode scanner with API and local mode support."""
    
#     def __init__(self, camera_index: int = 0):
#         self.camera_index = camera_index
#         self.cap = None  # Don't open camera in __init__ for API mode
#         self.catalog: Optional[ProductCatalog] = None
#         self._allowed_upcs: Set[str] = set()
#         self._match_types: Dict[str, str] = {}
#         self._is_initialized = False
#         self._upc_only_mode = False
#         logger.info(f"Scanner instance created (camera {camera_index})")
    
#     def initialize(self, catalog: Optional[ProductCatalog] = None, upc_only: bool = False):
#         """Initialize scanner with catalog or UPC-only mode."""
#         self._upc_only_mode = upc_only
        
#         if upc_only:
#             logger.info("🚀 UPC-ONLY mode initialized")
#             self._is_initialized = True
#             return
        
#         if catalog:
#             self.catalog = catalog
#             self._allowed_upcs = self.catalog.all_upcs()
#             logger.info(f"📦 Catalog initialized: {len(catalog.products)} products")
        
#         self._is_initialized = True
    
#     def set_filter(self, queries: List[str], upc_only: bool = False,
#                main_category: Optional[str] = None,
#                subcategory: Optional[str] = None) -> tuple[bool, List]:
#         """
#         Set UPC filter with optional category filtering
        
#         Args:
#             queries: List of product names or UPC codes
#             upc_only: If True, treat queries as UPC codes directly
#             main_category: Filter by main category (e.g., "ambient", "cold_chain")
#             subcategory: Filter by subcategory (e.g., "Biscuits", "Dessert")
#         """
#         if not self._is_initialized:
#             logger.error("Scanner not initialized!")
#             return False, []
        
#         self._upc_only_mode = upc_only
#         self._allowed_upcs.clear()
#         self._match_types.clear()
        
#         if upc_only:
#             # UPC-only mode: skip catalog, use queries directly
#             self._allowed_upcs = {q.strip() for q in queries if q.strip()}
#             logger.info(f"UPC-only filter: {len(self._allowed_upcs)} UPCs")
            
#             return True, [
#                 {"name": f"UPC: {upc}", "upc": upc, "match_type": "upc"}
#                 for upc in self._allowed_upcs
#             ]
        
#         if not self.catalog:
#             logger.error("No catalog available for filtering")
#             return False, []
        
#         # Catalog mode: find products with category filter
#         matched_products = self.catalog.find_multiple(
#             queries, 
#             main_category=main_category,
#             subcategory=subcategory
#         )
        
#         if not matched_products:
#             logger.warning(f"No products found for queries: {queries}")
#             return False, []
        
#         # Build allowed UPCs
#         for product in matched_products:
#             upc = str(product.upc)
#             self._allowed_upcs.add(upc)
#             self._match_types[upc] = getattr(product, '_match_type', 'full')
        
#         logger.info(f"Filter set: {len(matched_products)} products from category={main_category}/{subcategory}")
        
#         return True, [
#             {
#                 "name": p.name,
#                 "upc": str(p.upc),
#                 "main_category": p.main_category,
#                 "subcategory": p.subcategory,
#                 "match_type": getattr(p, '_match_type', 'full')
#             }
#             for p in matched_products
#         ]

    
#     # ============================================
#     # LOCAL CAMERA MODE (for main.py testing)
#     # ============================================
    
#     def scan_camera(self, duration_seconds: int = 30) -> List[dict]:
#         """Scan from local camera with OpenCV window (for testing)."""
#         # Open camera only when needed
#         if not self.cap:
#             self.cap = cv2.VideoCapture(self.camera_index)
        
#         if not self.cap.isOpened():
#             logger.error("❌ Camera not available")
#             return []
        
#         logger.info(f"📹 Camera scanning for {duration_seconds}s... Press 'q' to quit")
#         all_matches = []
        
#         start_time = cv2.getTickCount()
        
#         while True:
#             ret, frame = self.cap.read()
#             if not ret:
#                 logger.warning("Failed to read frame")
#                 break
            
#             # Process frame WITH display
#             matches = self._process_frame(frame, display=True)
#             all_matches.extend(matches)
            
#             # Show window
#             cv2.imshow("Barcode Scanner", frame)
            
#             # Check for quit
#             if cv2.waitKey(1) & 0xFF == ord('q'):
#                 logger.info("User quit scanning")
#                 break
            
#             # Check duration
#             if duration_seconds:
#                 elapsed = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
#                 if elapsed > duration_seconds:
#                     logger.info(f"Duration {duration_seconds}s reached")
#                     break
        
#         self.cap.release()
#         cv2.destroyAllWindows()
#         logger.info(f"✅ Scan complete: {len(all_matches)} detections")
#         return all_matches
    
#     def scan_image(self, image_path: Path) -> List[dict]:
#         """Scan single image file."""
#         if not image_path.exists():
#             logger.error(f"Image not found: {image_path}")
#             return []
        
#         frame = cv2.imread(str(image_path))
#         if frame is None:
#             logger.error(f"Could not read image: {image_path}")
#             return []
        
#         # Process WITHOUT display
#         matches = self._process_frame(frame, display=False)
#         logger.info(f"Image scan: {len(matches)} detections")
#         return matches
    
#     # ============================================
#     # CORE FRAME PROCESSING (API MODE)
#     # ============================================
    
#     def _process_frame(self, frame, display: bool = False) -> List[dict]:
#         """
#         Process single frame and return detections.
        
#         Args:
#             frame: OpenCV image (numpy array)
#             display: If True, draw rectangles/labels on frame
        
#         Returns:
#             List of detection dicts
#         """
#         if frame is None or frame.size == 0:
#             return []
        
#         # Decode barcodes
#         try:
#             barcodes = decode(frame)
#         except Exception as e:
#             logger.error(f"Barcode decode error: {e}")
#             return []
        
#         matches = []
        
#         for barcode in barcodes:
#             try:
#                 # Decode barcode data
#                 data = barcode.data.decode("utf-8")
                
#                 # Filter by allowed UPCs
#                 if data not in self._allowed_upcs:
#                     continue
                
#                 # Get match info for color coding
#                 match_info = self._get_match_info(data)
                
#                 if self._upc_only_mode:
#                     # UPC-only mode detection
#                     detection = {
#                         "upc": data,
#                         "type": barcode.type,
#                         "match_type": "upc"
#                     }
#                     matches.append(detection)
                    
#                     if display:
#                         self._draw_detection(frame, barcode, f"UPC: {data}", 
#                                            (0, 255, 255), "UPC")
                
#                 else:
#                     # Catalog mode detection
#                     product = self.catalog.find_by_upc(data)
#                     if product:
#                         detection = {
#                             "product": product.model_dump(),
#                             "upc": data,
#                             "match_type": match_info['type'].lower()
#                         }
#                         matches.append(detection)
                        
#                         if display:
#                             label = f"{product.name} [{match_info['type']}]"
#                             self._draw_detection(frame, barcode, label, 
#                                                match_info['color'], match_info['type'])
                
#                 logger.debug(f"Detected: {data}")
                
#             except Exception as e:
#                 logger.error(f"Error processing barcode: {e}")
#                 continue
        
#         return matches
    
#     def _get_match_info(self, upc: str) -> dict:
#         """Get color and type info for match quality."""
#         if self._upc_only_mode:
#             return {
#                 "type": "UPC",
#                 "color": (0, 255, 255)  # Yellow (BGR)
#             }
        
#         match_type = self._match_types.get(upc, 'full')
        
#         if match_type == "full":
#             return {
#                 "type": "FULL",
#                 "color": (0, 255, 0)  # Green (BGR)
#             }
#         elif match_type == "partial":
#             return {
#                 "type": "PARTIAL",
#                 "color": (0, 165, 255)  # Orange (BGR)
#             }
        
#         # Default to full match
#         return {
#             "type": "FULL",
#             "color": (0, 255, 0)
#         }
    
#     def _draw_detection(self, frame, barcode, label: str, color: tuple, match_type: str):
#         """Draw rectangle and label on frame."""
#         try:
#             x, y, w, h = barcode.rect
            
#             # Draw rectangle
#             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
#             # Draw label background
#             label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
#             cv2.rectangle(frame, (x, y - label_size[1] - 10), 
#                          (x + label_size[0], y), color, -1)
            
#             # Draw label text
#             cv2.putText(frame, label, (x, y - 5), 
#                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
            
#         except Exception as e:
#             logger.error(f"Draw error: {e}")
    
#     def close(self):
#         """Clean up resources."""
#         if self.cap:
#             self.cap.release()
#             self.cap = None
#         cv2.destroyAllWindows()
#         logger.info("Scanner closed")

#!/usr/bin/env python3
"""
Complete Professional Barcode Scanner with Rich UI + Nested Categories
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from src.config import ConfigManager
from src.scanner.core import BarcodeScanner
from src.models.catalog import ProductCatalog

console = Console()
ConfigManager.setup_logging()


def parse_queries(raw_input: str) -> list[str]:
    """Split by comma, keep full product names."""
    return [part.strip() for part in raw_input.split(",") if part.strip()]


def show_queries_separate(queries: list[str]):
    """Display queries as separate lines."""
    table = Table(title="🎯 Search Queries", show_header=True, header_style="bold cyan")
    table.add_column("Query", style="magenta")
    
    for query in queries:
        table.add_row(f"[bold cyan]'{query}'[/bold cyan]")
    
    console.print(table)


def show_category_tree(catalog: ProductCatalog):
    """Display available categories in a tree structure."""
    categories = catalog.get_categories()
    
    table = Table(title="📁 Available Categories", show_header=True, header_style="bold cyan")
    table.add_column("Main Category", style="cyan", no_wrap=True)
    table.add_column("Subcategories", style="yellow")
    
    for main_cat, subcats in categories.items():
        subcat_list = ", ".join(subcats) if subcats else "[dim]None[/dim]"
        table.add_row(
            f"[bold]{main_cat.upper()}[/bold]",
            subcat_list
        )
    
    console.print(table)


def show_matched_products(products):
    """Rich table with match type colors and categories."""
    table = Table(title="✅ Matched Products", show_header=True, header_style="bold green")
    table.add_column("🍪 Product", style="cyan")
    table.add_column("UPC", style="yellow")
    table.add_column("Category", style="blue")
    table.add_column("Match", style="magenta", justify="center")
    
    for product in products:
        match_type = getattr(product, '_match_type', 'full').upper()
        match_style = "bold green" if match_type == "FULL" else "bold orange"
        
        # Category display
        category_display = product.category or "[dim]N/A[/dim]"
        if product.subcategory:
            category_display += f" > {product.subcategory}"
        
        table.add_row(
            product.name,
            product.upc,
            category_display,
            f"[{match_style}]{match_type}[/]"
        )
    
    console.print(table)


def show_results_catalog(matches, catalog):
    """Display catalog scan results with categories."""
    if not matches:
        console.print(Panel("❌ [bold red]No matching products detected[/bold red]", 
                          title="Scan Results"))
        return
    
    counter = {}
    for match in matches:
        name = match["product"]["name"]
        counter[name] = counter.get(name, 0) + 1
    
    table = Table(title="📊 Scan Results", show_header=True, header_style="bold magenta")
    table.add_column("🍪 Product", style="cyan")
    table.add_column("Detections", style="green", justify="right")
    table.add_column("UPC", style="yellow")
    table.add_column("Category", style="blue")
    
    for name, count in counter.items():
        product = catalog.find_by_name(name)
        match_type = getattr(product, '_match_type', 'full').upper()
        match_style = "bold green" if match_type == "FULL" else "bold orange"
        
        # Category display
        category_display = product.category or "[dim]N/A[/dim]"
        if product.subcategory:
            category_display += f" > {product.subcategory}"
        
        table.add_row(
            f"{name} [{match_style}]{match_type}[/]",
            str(count),
            product.upc,
            category_display
        )
    
    console.print(table)
    console.print(f"[bold green]✅ Total detections: {len(matches)}[/bold green]")


def show_results_upc(matches):
    """Display UPC-only scan results."""
    if not matches:
        console.print(Panel("❌ [bold red]No matching UPCs detected[/bold red]", 
                          title="Scan Results"))
        return
    
    counter = {}
    for match in matches:
        upc = match["upc"]
        counter[upc] = counter.get(upc, 0) + 1
    
    table = Table(title="📊 Scan Results", show_header=True, header_style="bold magenta")
    table.add_column("🔢 UPC", style="cyan")
    table.add_column("Detections", style="green", justify="right")
    
    for upc, count in counter.items():
        table.add_row(upc, str(count))
    
    console.print(table)
    console.print(f"[bold green]✅ Total detections: {len(matches)}[/bold green]")


def get_category_filter(catalog: ProductCatalog):
    """Interactive category selection with nested support."""
    console.print("\n[bold cyan]═══ Category Filter (Optional) ═══[/bold cyan]")
    
    # Show available categories
    show_category_tree(catalog)
    
    # Get main category
    console.print("\n[bold]Filter by Main Category?[/bold] (Enter to skip)")
    console.print("[dim]Examples: ambient, chilled, frozen[/dim]")
    main_category = console.input("→ Main Category: ").strip().lower()
    
    if not main_category:
        return None, None
    
    # Validate main category
    categories = catalog.get_categories()
    if main_category not in categories:
        console.print(f"[yellow]⚠️  Unknown category '{main_category}', proceeding without filter[/yellow]")
        return None, None
    
    # Get subcategory
    available_subcats = categories[main_category]
    if available_subcats:
        console.print(f"\n[bold]Filter by Subcategory?[/bold] (Enter to skip)")
        console.print(f"[dim]Available: {', '.join(available_subcats)}[/dim]")
        subcategory = console.input("→ Subcategory: ").strip()
        
        if subcategory and subcategory not in available_subcats:
            console.print(f"[yellow]⚠️  Unknown subcategory '{subcategory}', using main category only[/yellow]")
            subcategory = None
    else:
        subcategory = None
    
    # Show selected filter
    filter_text = f"[bold green]✓ Filter:[/bold green] {main_category.upper()}"
    if subcategory:
        filter_text += f" > {subcategory}"
    console.print(f"\n{filter_text}\n")
    
    return main_category, subcategory


def main():
    console.clear()
    
    # ASCII Banner
    console.print(Panel.fit(
        "[bold cyan]🔍 BARCODE SCANNER PRO[/bold cyan]\n"
        "[dim]Nested Category Support[/dim]",
        border_style="cyan"
    ))
    
    # Mode selection
    mode = console.input("\n[bold]Mode[/bold] [1=Catalog/2=UPC-only] [1]: ").strip() or "1"
    use_catalog = mode == "1"
    
    # Query input
    console.print("\n[bold cyan]Enter products/UPCs (comma separated)[/bold cyan]")
    query_input = console.input("→ ").strip()
    if not query_input:
        console.print("[red]❌ No queries![/red]")
        return
    
    queries = parse_queries(query_input)
    show_queries_separate(queries)
    
    # Duration
    duration_input = console.input("\n[bold]Duration[/bold] (seconds) [30]: ").strip()
    duration = int(duration_input) if duration_input.isdigit() else 30
    
    console.print("\n" + "="*80)
    
    # ============================================
    # CATALOG MODE (with category filtering)
    # ============================================
    if use_catalog:
        console.print(Panel("[bold green]📦 CATALOG MODE[/bold green]", 
                          title="Mode", border_style="green"))
        
        try:
            catalog = ProductCatalog(Path("products.json"))
            scanner = BarcodeScanner()
            scanner.initialize(catalog)
            
            # Get category filter
            main_category, subcategory = get_category_filter(catalog)
            
            # Set filter with categories
            success, matched = scanner.set_filter(
                queries,
                upc_only=False,
                main_category=main_category,
                subcategory=subcategory
            )
            
            if not success:
                console.print("[bold red]❌ No products found matching criteria![/bold red]")
                if main_category:
                    console.print(f"[yellow]💡 Try removing category filter or broadening search[/yellow]")
                return
            
            console.print(f"[green]✅ Found {len(matched)} product(s):[/green]")
            show_matched_products(matched)
            
            console.print("\n[yellow]📹 Camera scanning... Press 'q' to quit early[/yellow]")
            matches = scanner.scan_camera(duration)
            show_results_catalog(matches, catalog)
            scanner.close()
        
        except FileNotFoundError:
            console.print("[bold red]❌ products.json not found in project root![/bold red]")
    
    # ============================================
    # UPC-ONLY MODE
    # ============================================
    else:
        console.print(Panel("[bold yellow]🚀 UPC-ONLY MODE[/bold yellow]", 
                          title="Mode", border_style="yellow"))
        
        scanner = BarcodeScanner()
        scanner.initialize(upc_only=True)
        success, upcs = scanner.set_filter(queries, upc_only=True)
        if not success:
            console.print("[bold red]❌ No UPCs provided![/bold red]")
            return
        
        console.print(f"[yellow]✅ UPCs to detect: {upcs}[/yellow]")
        console.print("\n[yellow]📹 Camera scanning... Press 'q' to quit early[/yellow]")
        matches = scanner.scan_camera(duration)
        show_results_upc(matches)
        scanner.close()
    
    console.print("\n" + Panel("🎉 [bold green]Scan complete![/bold green]", 
                              title="Done", border_style="green"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)
