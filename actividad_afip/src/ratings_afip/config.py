"""
Configuración centralizada del proyecto ratings-afip.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolver BASE_DIR como la carpeta que contiene a src/
BASE_DIR = Path(__file__).parent.parent.parent.resolve()

# Cargar .env explícitamente desde la raíz del proyecto (sin importar cwd)
load_dotenv(BASE_DIR / ".env")

# Rutas de certificados AFIP
CERT_PATH = BASE_DIR / os.getenv("AFIP_CERT_PATH", "afip_keys/produccion.crt")
KEY_PATH = BASE_DIR / os.getenv("AFIP_KEY_PATH", "afip_keys/scaianosofia.key")

# Credenciales AFIP SDK
AFIP_CUIT = int(os.getenv("AFIP_CUIT", "0"))
AFIP_ACCESS_TOKEN = os.getenv("AFIP_ACCESS_TOKEN", "")

# Rutas de datos
DATA_DIR = BASE_DIR / "data"
RAW_JSON_DIR = DATA_DIR / "output" / "raw"  # Respuestas crudas de AFIP
RESULTS_CSV = DATA_DIR / "output" / "actividades_economicas.csv"
ERRORS_CSV = DATA_DIR / "output" / "errores.csv"
SUMMARY_JSON = DATA_DIR / "output" / "summary.json"
SLEEP_SECONDS = float(os.getenv("AFIP_SLEEP_SECONDS", "2"))
