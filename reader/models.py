from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field


class InputError(ValueError):
    pass


class PageResult(BaseModel):
    page_number: int
    text: str = ''
    method: Literal['text', 'pdf_text', 'vision', 'blank']
    status: Literal['read', 'partial', 'failed', 'blank']
    issues: list[str] = Field(default_factory=list)


class MaterialResult(BaseModel):
    material_id: str = Field(default_factory=lambda: 'M' + uuid4().hex)
    filename: str
    kind: Literal['text', 'pdf', 'image']
    status: Literal['read', 'partial', 'failed'] = 'read'
    pages: list[PageResult]
    extraction_verified: bool = False
