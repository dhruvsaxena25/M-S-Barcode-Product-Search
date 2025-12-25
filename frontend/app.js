// ============================================
// GLOBAL STATE
// ============================================

let ws = null;
let video = null;
let canvas = null;
let detectionCanvas = null;
let detectionCtx = null;
let frameInterval = null;
let categories = {};
let activeDetections = new Map();
let fpsCounter = 0;
let lastFpsUpdate = Date.now();

// ============================================
// INITIALIZATION
// ============================================

window.addEventListener('DOMContentLoaded', async () => {
    await loadCategories();
    console.log('✅ Scanner initialized');
});

// ============================================
// LOAD CATEGORIES
// ============================================

async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        const data = await response.json();
        categories = data.categories;
        
        const mainCategorySelect = document.getElementById('main-category');
        mainCategorySelect.innerHTML = '<option value="">All Categories</option>';
        
        Object.keys(categories).forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = formatCategoryName(cat);
            mainCategorySelect.appendChild(option);
        });
        
        console.log('✅ Categories loaded:', Object.keys(categories).length);
    } catch (error) {
        console.error('❌ Failed to load categories:', error);
    }
}

function loadSubcategories() {
    const mainCategory = document.getElementById('main-category').value;
    const subcategorySelect = document.getElementById('subcategory');
    
    subcategorySelect.innerHTML = '<option value="">All Subcategories</option>';
    
    if (mainCategory && categories[mainCategory]) {
        categories[mainCategory].forEach(subcat => {
            const option = document.createElement('option');
            option.value = subcat;
            option.textContent = subcat;
            subcategorySelect.appendChild(option);
        });
    }
}

function formatCategoryName(cat) {
    return cat.split('_').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

// ============================================
// MODE TOGGLE
// ============================================

function toggleMode() {
    const mode = document.getElementById('mode').value;
    const categorySection = document.getElementById('category-section');
    const searchLabel = document.getElementById('search-label');
    const searchHint = document.getElementById('search-hint');
    const queriesInput = document.getElementById('queries');
    
    if (mode === 'upc-only') {
        categorySection.classList.add('hidden');
        searchLabel.textContent = 'UPC Codes';
        searchHint.textContent = 'Enter UPC codes separated by commas';
        queriesInput.placeholder = 'e.g., 29456086, 985482, 141130';
    } else {
        categorySection.classList.remove('hidden');
        searchLabel.textContent = 'Search Products';
        searchHint.textContent = 'Separate multiple items with commas';
        queriesInput.placeholder = 'e.g., Chocolate Cookies, Milk';
    }
}

// ============================================
// START SCANNING
// ============================================

async function startScanning() {
    const queries = document.getElementById('queries').value.trim();
    const mode = document.getElementById('mode').value;
    const mainCategory = document.getElementById('main-category').value;
    const subcategory = document.getElementById('subcategory').value;
    
    // Validation
    if (!queries) {
        alert('⚠️ Please enter ' + (mode === 'upc-only' ? 'UPC codes' : 'product names'));
        return;
    }
    
    // Update status
    updateStatus('Initializing camera...');
    
    // Show camera view
    document.getElementById('setup').classList.add('hidden');
    document.getElementById('camera-view').classList.remove('hidden');
    
    // Get elements
    video = document.getElementById('video');
    canvas = document.getElementById('canvas');
    detectionCanvas = document.getElementById('detection-canvas');
    detectionCtx = detectionCanvas.getContext('2d');
    
    try {
        // Request camera
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        });
        
        video.srcObject = stream;
        await video.play();
        
        // Resize canvas
        detectionCanvas.width = video.videoWidth;
        detectionCanvas.height = video.videoHeight;
        
        updateStatus('Connecting to server...');
        
        // Connect WebSocket
        connectWebSocket(queries, mode, mainCategory, subcategory);
        
    } catch (error) {
        console.error('❌ Camera error:', error);
        alert('Failed to access camera: ' + error.message);
        stopScanning();
    }
}

// ============================================
// WEBSOCKET CONNECTION
// ============================================

function connectWebSocket(queries, mode, mainCategory, subcategory) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/scan`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('✅ WebSocket connected');
        updateStatus('Scanning...');
        
        const queryList = queries.split(',').map(q => q.trim()).filter(q => q);
        
        ws.send(JSON.stringify({
            queries: queryList,
            mode: mode,
            main_category: mainCategory || null,
            subcategory: subcategory || null
        }));
        
        startFrameCapture();
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'init') {
            console.log('✅ Initialized:', data.matched_products.length, 'products');
        } 
        else if (data.type === 'detection') {
            handleDetection(data);
        } 
        else if (data.type === 'error') {
            console.error('❌ Server error:', data.message);
            alert('Error: ' + data.message);
            stopScanning();
        }
    };
    
    ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        alert('Connection error. Please try again.');
        stopScanning();
    };
    
    ws.onclose = () => {
        console.log('WebSocket closed');
        stopFrameCapture();
    };
}

// ============================================
// FRAME CAPTURE
// ============================================

function startFrameCapture() {
    let lastCapture = 0;
    const captureInterval = 100; // 10 FPS
    
    frameInterval = setInterval(() => {
        const now = Date.now();
        if (now - lastCapture < captureInterval) return;
        lastCapture = now;
        
        if (ws && ws.readyState === WebSocket.OPEN) {
            captureFrame();
            updateFPS();
        }
    }, 30);
}

function captureFrame() {
    if (!video || !canvas) return;
    
    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob((blob) => {
        if (!blob) return;
        
        const reader = new FileReader();
        reader.onloadend = () => {
            const base64 = reader.result.split(',')[1];
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'frame',
                    frame: base64
                }));
            }
        };
        reader.readAsDataURL(blob);
    }, 'image/jpeg', 0.7);
}

function stopFrameCapture() {
    if (frameInterval) {
        clearInterval(frameInterval);
        frameInterval = null;
    }
}

function updateFPS() {
    fpsCounter++;
    const now = Date.now();
    
    if (now - lastFpsUpdate >= 1000) {
        document.getElementById('fps').textContent = fpsCounter + ' FPS';
        fpsCounter = 0;
        lastFpsUpdate = now;
    }
}

// ============================================
// DETECTION HANDLING
// ============================================

function handleDetection(data) {
    const now = Date.now();
    
    // Clear canvas
    detectionCtx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
    
    // Update active detections
    if (data.detections && data.detections.length > 0) {
        data.detections.forEach(det => {
            activeDetections.set(det.upc, {
                ...det,
                timestamp: now
            });
        });
    }
    
    // Remove stale detections (2 seconds)
    activeDetections.forEach((det, upc) => {
        if (now - det.timestamp > 2000) {
            activeDetections.delete(upc);
        }
    });
    
    // Render
    renderDetections();
}

function renderDetections() {
    const detectionsDiv = document.getElementById('detections');
    
    // Clear
    detectionsDiv.innerHTML = '';
    detectionCtx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
    
    // Render each detection
    activeDetections.forEach(det => {
        // Create overlay card
        const detDiv = document.createElement('div');
        detDiv.className = 'detection-item';
        
        const matchClass = det.match_type === 'full' ? 'full' : 
                          det.match_type === 'partial' ? 'partial' : 'upc';
        
        const matchLabel = det.match_type === 'full' ? 'EXACT MATCH' :
                          det.match_type === 'partial' ? 'PARTIAL' : 'DETECTED';
        
        detDiv.innerHTML = `
            <div class="detection-name">${det.product_name}</div>
            <div class="detection-upc">UPC: ${det.upc}</div>
            <span class="detection-badge ${matchClass}">${matchLabel}</span>
        `;
        
        detectionsDiv.appendChild(detDiv);
        
        // Draw bounding box
        if (det.rect) {
            drawBoundingBox(det.rect, det.product_name);
        }
    });
}

function drawBoundingBox(rect, label) {
    const scaleX = detectionCanvas.width / video.videoWidth;
    const scaleY = detectionCanvas.height / video.videoHeight;
    
    const x = rect.x * scaleX;
    const y = rect.y * scaleY;
    const width = rect.width * scaleX;
    const height = rect.height * scaleY;
    
    // Draw rectangle
    detectionCtx.strokeStyle = '#f97316';
    detectionCtx.lineWidth = 3;
    detectionCtx.strokeRect(x, y, width, height);
    
    // Draw label background
    detectionCtx.font = 'bold 16px Inter';
    const textWidth = detectionCtx.measureText(label).width;
    
    detectionCtx.fillStyle = '#f97316';
    detectionCtx.fillRect(x, y - 30, textWidth + 20, 26);
    
    // Draw label text
    detectionCtx.fillStyle = '#ffffff';
    detectionCtx.fillText(label, x + 10, y - 10);
}

// Auto-clear old detections
setInterval(() => {
    const now = Date.now();
    let hasChanges = false;
    
    activeDetections.forEach((det, upc) => {
        if (now - det.timestamp > 2000) {
            activeDetections.delete(upc);
            hasChanges = true;
        }
    });
    
    if (hasChanges) {
        renderDetections();
    }
}, 500);

// ============================================
// STOP SCANNING
// ============================================

function stopScanning() {
    // Stop frame capture
    stopFrameCapture();
    
    // Close WebSocket
    if (ws) {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'stop' }));
        }
        ws.close();
        ws = null;
    }
    
    // Stop camera
    if (video && video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }
    
    // Reset UI
    document.getElementById('camera-view').classList.add('hidden');
    document.getElementById('setup').classList.remove('hidden');
    
    activeDetections.clear();
    
    updateStatus('Ready to scan');
    console.log('✅ Scanning stopped');
}

// ============================================
// UTILITY
// ============================================

function updateStatus(text) {
    const statusText = document.getElementById('status-text');
    const cameraStatus = document.getElementById('camera-status-text');
    
    if (statusText) statusText.textContent = text;
    if (cameraStatus) cameraStatus.textContent = text;
}
