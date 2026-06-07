"""Configuración del Scraper CNV Calificaciones."""

from pathlib import Path
from typing import Final

# URLs base
BASE_URL: Final[str] = "https://www.cnv.gov.ar/SitioWeb"
AIF2_URL: Final[str] = "https://aif2.cnv.gov.ar"
BLOB_URL: Final[str] = "https://blob.cnv.gov.ar/BlobWebService.svc"

# Endpoints
ENDPOINTS: Final[dict[str, str]] = {
    "sociedades": f"{BASE_URL}/Calificaciones/SociedadesCalificadas",
    "titulos": f"{BASE_URL}/Calificaciones/TitulosCalificadoras",
    "calificaciones": f"{BASE_URL}/Calificaciones/UltimasCalificaciones",
    "presentacion": f"{AIF2_URL}/Presentations/publicview",
}

# Configuración de categorías
CATEGORIA_EMPRESAS_ID: Final[int] = 2
CATEGORIA_EMPRESAS_NOMBRE: Final[str] = "Empresas"

# Paginación
TOTAL_PAGINAS: Final[int] = 32
SOCIEDADES_POR_PAGINA: Final[int] = 20

# Rutas del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
INFORMES_DIR = DOWNLOADS_DIR / "informes"
RESUMEN_JSON_DIR = DOWNLOADS_DIR / "resumen_json"
XML_RAW_DIR = DOWNLOADS_DIR / "xml_raw"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
CACHE_FILE = DATA_DIR / "sociedades_cache.json"
ESTADO_FILE = DATA_DIR / "estado_scraper.json"
CSV_OUTPUT = PROJECT_ROOT / "calificaciones.csv"

# Crear directorios si no existen
for dir_path in [INFORMES_DIR, RESUMEN_JSON_DIR, XML_RAW_DIR, DATA_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Configuración de requests
REQUEST_TIMEOUT: Final[int] = 30
RETRY_ATTEMPTS: Final[int] = 3
RETRY_DELAY: Final[int] = 2  # segundos
DELAY_ENTRE_REQUESTS: Final[int] = 1  # segundos

# User-Agent para requests
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Headers por defecto
DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Columnas del CSV
CSV_COLUMNS: Final[list[str]] = [
    "cuit",
    "razon_social",
    "calificadora",
    "cuit_calificadora",
    "fecha_consejo",
    "tipo_emision",
    "moneda_a_calificar",
    "monto_emision",
    "calificacion_categoria",
    "calificacion_prefijos",
    "calificacion_sufijos",
    "calificacion_signo",
    "perspectiva",
    "rating_watch",
    "resultado_calificacion",
    "instrumento",
    "url_resumen",
    "presentacion_id",
    "nombre_archivo_informe",
    "ruta_pdf_descargado",
    "estado_descarga",
    "error_detalle",
    "fecha_extraccion",
]

# Estados de descarga
ESTADOS_DESCARGA: Final[dict[str, str]] = {
    "EXITOSO": "EXITOSO",
    "ERROR_404": "ERROR_404",
    "ERROR_TIMEOUT": "ERROR_TIMEOUT",
    "ERROR_OTRO": "ERROR_OTRO",
    "NO_HAY_INFORME": "NO_HAY_INFORME",
    "PENDIENTE": "PENDIENTE",
    "ERROR_ARCHIVO_CORRUPTO": "ERROR_ARCHIVO_CORRUPTO",
    "ERROR_XML_INVALIDO": "ERROR_XML_INVALIDO",
}

# Modos de ejecución
MODOS: Final[dict[str, str]] = {
    "PRUEBA": "PRUEBA",
    "COMPLETO": "COMPLETO",
    "REANUDAR": "REANUDAR",
    "ESTADISTICAS": "ESTADISTICAS",
}

# Guardar estado cada N sociedades
GUARDAR_ESTADO_CADA: Final[int] = 10

# Configuración de Playwright
PLAYWRIGHT_TIMEOUT: Final[int] = 30000  # 30 segundos
PLAYWRIGHT_TIMEOUT_BOTON: Final[int] = 10000  # 10 segundos para esperar botón
PLAYWRIGHT_HEADLESS: Final[bool] = True  # Modo headless (sin ventana)
PLAYWRIGHT_MAX_INTENTOS: Final[int] = 3  # Intentos de descarga
PLAYWRIGHT_RETRASO_ENTRE_INTENTOS: Final[int] = 2  # Segundos entre intentos
