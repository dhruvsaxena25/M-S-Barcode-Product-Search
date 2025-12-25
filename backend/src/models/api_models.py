from typing import List
from pydantic import BaseModel

# Models
class ScanRequest(BaseModel):
    queries: List[str]
    mode: str = "catalog"

class FrameRequest(BaseModel):
    frame: str  # base64 encoded
    queries: List[str]
    mode: str = "catalog"
    
    