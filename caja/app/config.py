import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar el archivo .env ubicado en la raíz de caja/
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000")

def _get_required_int_env(var_name: str) -> int:
    raw_value = os.getenv(var_name)
    if not raw_value:
        raise RuntimeError(f"Falta configurar {var_name} en el archivo .env")
    try:
        return int(raw_value)
    except ValueError:
        raise ValueError(f"{var_name} debe ser un entero válido, recibido: {raw_value}")


CASH_REGISTER_ID = _get_required_int_env("CASH_REGISTER_ID")
USER_ID = _get_required_int_env("USER_ID")
