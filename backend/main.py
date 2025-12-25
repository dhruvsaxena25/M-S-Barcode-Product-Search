#!/usr/bin/env python3
"""
Complete Professional Barcode Scanner with Rich UI + Color Coding
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

def show_matched_products(products):
    """Rich table with match type colors."""
    table = Table(title="✅ Matched Products", show_header=True, header_style="bold green")
    table.add_column("🍪 Product", style="cyan")
    table.add_column("UPC", style="yellow")
    table.add_column("Match", style="magenta", justify="center")
    
    for product in products:
        match_type = getattr(product, '_match_type', 'full').upper()
        match_style = "bold green" if match_type == "FULL" else "bold orange"
        table.add_row(product.name, product.upc, f"[{match_style}]{match_type}[/]")
    
    console.print(table)

def show_results_catalog(matches, catalog):
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
    
    for name, count in counter.items():
        product = catalog.find_by_name(name)
        match_type = getattr(product, '_match_type', 'full').upper()
        match_style = "bold green" if match_type == "FULL" else "bold orange"
        table.add_row(f"{name} [{match_style}]{match_type}[/]", str(count), product.upc)
    
    console.print(table)
    console.print(f"[bold green]✅ Total detections: {len(matches)}[/bold green]")

def show_results_upc(matches):
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

def main():
    console.clear()

    
    mode = console.input("\n[bold]Mode[/bold] [1=Catalog/2=UPC-only] [1]: ").strip() or "1"
    use_catalog = mode == "1"
    
    console.print("\n[bold cyan]Enter products/UPCs (comma separated)[/bold cyan]")
    query_input = console.input("→ ").strip()
    if not query_input:
        console.print("[red]❌ No queries![/red]")
        return
    
    queries = parse_queries(query_input)
    show_queries_separate(queries)
    
    duration_input = console.input("\n[bold]Duration[/bold] (seconds) [30]: ").strip()
    duration = int(duration_input) if duration_input.isdigit() else 30
    
    console.print("\n" + "="*80)
    
    if use_catalog:
        console.print(Panel("[bold green]📦 CATALOG MODE[/bold green]", 
                          title="Mode", border_style="green"))
        
        try:
            catalog = ProductCatalog(Path("products.json"))
            scanner = BarcodeScanner()
            scanner.initialize(catalog)
            
            success, matched = scanner.set_filter(queries)
            if not success:
                console.print("[bold red]❌ No products found![/bold red]")
                return
            
            console.print(f"[green]✅ Found {len(matched)} product(s):[/green]")
            show_matched_products(matched)
            
            console.print("\n[yellow]📹 Camera scanning... Press 'q' to quit early[/yellow]")
            matches = scanner.scan_camera(duration)
            show_results_catalog(matches, catalog)
            scanner.close()
        
        except FileNotFoundError:
            console.print("[bold red]❌ products.json not found in project root![/bold red]")
    
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
        sys.exit(1)
