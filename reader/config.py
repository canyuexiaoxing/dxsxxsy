from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import dotenv_values
from .api_key_settings import stored_api_key

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    api_key: str = ''
    base_url: str = 'https://api.deepseek.com'
    model: str = 'deepseek-flash'
    timeout: float = 120
    data_dir: Path = ROOT / 'data'

    @classmethod
    def load(cls):
        values = {**dotenv_values(ROOT / '.env'), **os.environ}
        directory = Path(values.get('DATA_DIR') or './data')
        if not directory.is_absolute(): directory = ROOT / directory
        return cls(api_key=stored_api_key(directory.resolve()) or values.get('DEEPSEEK_API_KEY') or '',
                   base_url=values.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com',
                   model=values.get('DEEPSEEK_MODEL') or 'deepseek-flash',
                   timeout=float(values.get('API_TIMEOUT_SECONDS') or 120),
                   data_dir=directory.resolve())
