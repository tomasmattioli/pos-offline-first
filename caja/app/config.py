import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar el archivo .env ubicado en la raíz de caja/
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000")

cash_register_id_raw = os.getenv("CASH_REGISTER_ID")
if not cash_register_id_raw:
    raise RuntimeError("Falta configurar CASH_REGISTER_ID en el archivo .env")

try:
    CASH_REGISTER_ID = int(cash_register_id_raw)
except ValueError:
    raise ValueError(f"CASH_REGISTER_ID debe ser un entero válido, recibido: {cash_register_id_raw}")
