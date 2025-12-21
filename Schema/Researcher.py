from typing import Optional
from pydantic import BaseModel


class ProductCompanyRequest(BaseModel):
    product_company: str
    is_deepresearch_needed: bool = False
    custom_filter: Optional[str] = None
    sys_promt: Optional[str] = None
    clarification: Optional[str] = None 
    