import json
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class LegalClaim(StrictModel):
    statement:str
    basis_ids:list[str]=Field(min_length=1)

class Finding(StrictModel):
    title:str
    level:Literal['high','attention','uncertain']
    quote_id:str=Field(default='',exclude=True,description='从material_quotes选择的原句编号，不得使用知识库依据编号')
    quote:str=''
    material_id:str='user'
    page_number:int=0
    explanation:str
    evidence_ids:list[str]
    suggestions:list[str]
    category:Literal['risk','check','advice']='risk'
    fact_basis:Literal['abnormal_clause','abnormal_behavior','missing_information','normal_fact','user_request'] | None=None
    legal_claims:list[LegalClaim]=Field(default_factory=list)

class PreventionPlan(StrictModel):
    decision:Literal['pause','verify']
    label:str
    steps:list[str]
    note:str

class Report(StrictModel):
    situation_overview:str=Field(default="",max_length=350)
    summary:str
    findings:list[Finding]
    limitations:list[str]
    change_reason:str=''
    prevention:PreventionPlan | None=None
    self_checks:list[str]=Field(default_factory=list)

    @field_validator('situation_overview')
    @classmethod
    def clean_overview(cls,value):
        from .situation import valid_overview
        if value and not valid_overview(value):
            raise ValueError('情况概述不得包含内部备注或超长内容')
        return ' '.join(value.split())

    @field_validator('change_reason',mode='before')
    @classmethod
    def empty_reason(cls,value):
        return '' if value is None else value

class TurnResult(StrictModel):
    action:Literal['ask','answer','report','revise']
    employment_stage:Literal['preemployment','employed','unknown']='unknown'
    stage_reason:str=''
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

def decode_turn(content):
    """Recover only known, lossless field placement mistakes; validate everything else."""
    value=json.loads(content)
    if isinstance(value,dict) and 'change_reason' in value and isinstance(value.get('report'),dict):
        reason=value['change_reason'];nested=value['report'].get('change_reason')
        if isinstance(reason,str) and (nested in (None,'') or nested==reason):
            value['report']['change_reason']=value.pop('change_reason')
    if isinstance(value,dict):
        # Some responses duplicate empty Finding defaults at enclosing levels.
        # Non-empty quotes, other origins, partial triples and other extras stay invalid.
        for container in [value,value.get('report')]:
            if (isinstance(container,dict) and all(k in container for k in ('quote','material_id','page_number'))
                and container['quote']=='' and container['material_id']=='user'
                and type(container['page_number']) is int and container['page_number']==0):
                for name in ('quote','material_id','page_number'):container.pop(name)
    return value

def parse_turn(content):
    return TurnResult.model_validate(decode_turn(content))
