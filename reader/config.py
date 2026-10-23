from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import dotenv_values
from .api_key_settings import stored_api_key
from desktop_runtime import state_root

ROOT = Path(__file__).resolve().parent.parent


def configuration_values():
    # Installed configuration lives beside JobMirror.exe, outside _internal.
    return {**dotenv_values(state_root() / '.env'), **os.environ}


@dataclass
class Settings:
    api_key: str = ''
    base_url: str = 'https://api.deepseek.com'
    model: str = 'deepseek-flash'
    timeout: float = 120
    data_dir: Path = state_root() / 'data'

    @classmethod
    def load(cls):
        values = configuration_values()
        directory = Path(values.get('DATA_DIR') or state_root() / 'data')
        if not directory.is_absolute(): directory = state_root() / directory
        return cls(api_key=stored_api_key(directory.resolve()) or values.get('DEEPSEEK_API_KEY') or '',
                   base_url=values.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com',
                   model=values.get('DEEPSEEK_MODEL') or 'deepseek-flash',
                   timeout=float(values.get('API_TIMEOUT_SECONDS') or 120),
                   data_dir=directory.resolve())
