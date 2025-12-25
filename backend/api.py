from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import cv2
import numpy as np
import base64
import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from src.models.api_models import ScanRequest, FrameRequest
from src.scanner.core import BarcodeScanner
from src.models.catalog import ProductCatalog

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize FastAPI
app = FastAPI(
    title="Mobile Barcode Scanner API",
    version="1.0.0",
    description="Real-time barcode detection from mobile camera"
)


# CORS - Allow mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load product catalog
try:
    catalog = ProductCatalog(Path("products.json"))
    logger.info(f"✅ Loaded {len(catalog.products)} products")
except Exception as e:
    logger.error(f"❌ Failed to load catalog: {e}")
    catalog = None
    
# ============================================
frontend_path = Path("../frontend")  ## ../ remove for docker
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory="../frontend"), name="frontend") ## ../ remove for docker
    logger.info(f"✅ Mounted frontend: {frontend_path.absolute()}")
else:
    logger.warning(f"⚠️ Frontend not found: {frontend_path.absolute()}")

# ============================================
# ROOT - SERVE LANDING PAGE
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve API landing page from frontend folder"""
    landing_page = Path("../frontend/api-home.html") ## ../ remove for docker
    
    if landing_page.exists():
        return landing_page.read_text(encoding='utf-8')
    
    # Fallback
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Barcode Scanner API</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: system-ui;
                background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                text-align: center;
                padding: 20px;
            }
            .container {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                padding: 60px 40px;
                border-radius: 24px;
                max-width: 600px;
            }
            h1 { font-size: 48px; margin-bottom: 16px; }
            .status {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                background: rgba(16, 185, 129, 0.3);
                padding: 12px 24px;
                border-radius: 20px;
                margin: 20px 0;
            }
            .dot {
                width: 10px;
                height: 10px;
                background: #10b981;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            a {
                color: white;
                background: rgba(255,255,255,0.2);
                padding: 14px 28px;
                border-radius: 12px;
                text-decoration: none;
                display: inline-block;
                margin: 8px;
                font-weight: 600;
                border: 2px solid rgba(255,255,255,0.3);
            }
            a:hover { background: rgba(255,255,255,0.3); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Barcode Scanner API</h1>
            <div class="status">
                <div class="dot"></div>
                <strong>Status: Running</strong>
            </div>
            <div>
                <a href="/docs">📖 API Docs</a>
                <a href="/static/index.html">📱 Scanner</a>
            </div>
        </div>
    </body>
    </html>
    """)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "products": len(catalog.products) if catalog else 0
    }

# ============================================
# WebSocket Real-Time Scanning (RECOMMENDED)
# ============================================

@app.websocket("/ws/scan")
async def websocket_scan(websocket: WebSocket):
    """
    Real-time mobile camera scanning via WebSocket.
    
    Flow:
    1. Mobile connects
    2. Sends init: {"queries": ["Product1", "Product2"], "mode": "catalog"}
    3. Sends frames: {"type": "frame", "frame": "base64..."}
    4. API returns: {"type": "detection", "detections": [...]}
    """
    await websocket.accept()
    logger.info("📱 Client connected")
    
    scanner = BarcodeScanner()
    scanner.initialize(catalog)
    
    try:
        # Step 1: Init with category support
        init_data = await websocket.receive_json()
        queries = init_data.get("queries", [])
        mode = init_data.get("mode", "catalog")
        main_category = init_data.get("main_category")  
        subcategory = init_data.get("subcategory")     
        
        logger.info(f"🔍 Queries: {queries}, Mode: {mode}, Category: {main_category}/{subcategory}")
        
        # Step 2: Set filter with category
        success, matched = scanner.set_filter(
            queries, 
            upc_only=(mode == "upc-only"),
            main_category=main_category,
            subcategory=subcategory
        )
        
        if not success:
            await websocket.send_json({
                "type": "error",
                "message": "No products found"
            })
            await websocket.close()
            return
        
        # Step 3: Send matched products
        await websocket.send_json({
            "type": "init",
            "matched_products": matched
        })
        
        logger.info(f"✅ Allowed UPCs: {scanner._allowed_upcs}")
        
        # Step 4: Process frames
        frame_count = 0
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "frame":
                frame_count += 1
                
                try:
                    # Decode base64 frame
                    img_data = base64.b64decode(data["frame"])
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        logger.warning(f"Frame {frame_count}: Failed to decode")
                        continue
                    
                    # Process frame
                    matches = scanner._process_frame(frame, display=False)
                    
                    if frame_count % 10 == 0:
                        logger.info(f"Frame {frame_count}: {len(matches)} detections")
                    
                    # Send detections
                    if matches:
                        from pyzbar.pyzbar import decode
                        barcodes = decode(frame)
                        
                        detection_data = {
                            "type": "detection",
                            "frame_id": frame_count,
                            "detections": []
                        }
                        
                        for m in matches:
                            # Find matching barcode for coordinates
                            barcode_rect = None
                            for barcode in barcodes:
                                if barcode.data.decode('utf-8') == m.get("upc"):
                                    barcode_rect = {
                                        "x": barcode.rect.left,
                                        "y": barcode.rect.top,
                                        "width": barcode.rect.width,
                                        "height": barcode.rect.height
                                    }
                                    break
                            
                            det = {
                                "upc": m.get("upc"),
                                "product_name": m.get("product", {}).get("name", f"UPC: {m.get('upc')}"),
                                "match_type": m.get("match_type", "full"),
                                "rect": barcode_rect
                            }
                            detection_data["detections"].append(det)
                        
                        await websocket.send_json(detection_data)
                        logger.info(f"📤 Sent {len(matches)} detections")
                
                except Exception as e:
                    logger.error(f"Frame {frame_count} error: {e}", exc_info=True)
            
            elif data.get("type") == "stop":
                logger.info("🛑 Client requested stop")
                break
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    
    finally:
        scanner.close()
        await websocket.close()
        logger.info("✅ Scanner closed")
        
# ============================================
# HTTP Endpoints (Alternative)
# ============================================


@app.post("/api/scan-frame")
async def scan_frame(request: FrameRequest):
    """
    Single frame scan (HTTP).
    Lower FPS than WebSocket but simpler.
    """
    try:
        # Decode frame
        img_data = base64.b64decode(request.frame)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(400, "Invalid image")
        
        # Create scanner
        scanner = BarcodeScanner()
        scanner.initialize(catalog)
        success, matched = scanner.set_filter(request.queries, request.mode == "upc-only")
        
        if not success:
            return {"success": False, "error": "No products found"}
        
        # Process
        matches = scanner._process_frame(frame)
        scanner.close()
        
        return {
            "success": True,
            "detections": [
                {
                    "upc": m.get("upc"),
                    "product_name": m.get("product", {}).get("name"),
                    "match_type": m.get("match_type", "full")
                } for m in matches
            ]
        }
    
    except Exception as e:
        logger.error(f"Scan error: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/categories")
async def get_categories():
    """Get all available categories and subcategories"""
    if not catalog:
        raise HTTPException(500, "Catalog not loaded")
    
    return {
        "categories": catalog.get_categories()
    }
    
    
@app.get("/api/products/category")
async def get_products_by_category(
    main_category: Optional[str] = None,
    subcategory: Optional[str] = None,
    limit: int = 100
):
    """Get products by category"""
    if not catalog:
        raise HTTPException(500, "Catalog not loaded")
    
    products = catalog.find_by_category(main_category, subcategory)
    
    return {
        "main_category": main_category,
        "subcategory": subcategory,
        "total": len(products),
        "products": [
            {
                "name": p.name,
                "upc": p.upc,
                "category": p.category,
                "subcategory": p.subcategory
            }
            for p in products[:limit]
        ]
    }

@app.get("/api/search")
async def search_products(q: str, limit: int = 10):
    """Search products by query."""
    if not catalog:
        raise HTTPException(500, "Catalog not loaded")
    
    matched = catalog.find_multiple([q])
    return [
        {
            "name": p.name,
            "upc": p.upc,
            "match_type": getattr(p, '_match_type', 'full')
        }
        for p in matched[:limit]
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)