import re
from pathlib import Path
from .models import InputError, MaterialResult


class MaterialStore:
    def __init__(self,root: Path):
        self.root = root / 'materials'

    def _directory(self,material_id):
        if not re.fullmatch(r'M[0-9a-f]{32}',material_id): raise InputError('材料编号无效')
        return self.root / material_id

    def save(self,result: MaterialResult,original: bytes):
        directory = self._directory(result.material_id)
        directory.mkdir(parents=True,exist_ok=False)
        (directory/'original').write_bytes(original)
        (directory/'result.json').write_text(result.model_dump_json(indent=2),encoding='utf-8')

    def load(self,material_id):
        path = self._directory(material_id)/'result.json'
        if not path.is_file(): raise InputError('未找到材料')
        return MaterialResult.model_validate_json(path.read_text(encoding='utf-8'))

    def original_path(self,material_id):
        self.load(material_id)
        return self._directory(material_id)/'original'
