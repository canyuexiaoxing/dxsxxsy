from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class Finding(StrictModel):
    title:str
    level:Literal['high','attention','uncertain']
    quote:str
    material_id:str
    page_number:int
    explanation:str
    evidence_ids:list[str]
    suggestions:list[str]

class Report(StrictModel):
    summary:str
    findings:list[Finding]
    limitations:list[str]
    change_reason:str

    @field_validator('change_reason',mode='before')
    @classmethod
    def empty_reason(cls,value):
        return '' if value is None else value

class TurnResult(StrictModel):
    action:Literal['ask','answer','report','revise']
    message:str
    questions:list[str]=Field(max_length=3)
    evidence_ids:list[str]
    report:Report | None

    @field_validator('message',mode='before')
    @classmethod
    def empty_message(cls,value):
        return '' if value is None else value

    @field_validator('questions',mode='before')
    @classmethod
    def empty_questions(cls,value):
        return [] if value is None else value
