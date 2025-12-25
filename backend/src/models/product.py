from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra='allow',  
        arbitrary_types_allowed=True)
    
    # Core product fields
    name: str = Field(..., min_length=1, description="Name of the product")
    upc: str  = Field(..., description="Universal Product Code")

    # Category fields (set during catalog loading)
    main_category: Optional[str] = Field(default=None, description="Main category (e.g., ambient, cold_chain)")
    subcategory: Optional[str] = Field(default=None, description="Subcategory (e.g., Biscuits, Dessert)")
    
