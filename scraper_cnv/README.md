# CNV Scraper - Calificaciones de Riesgo

Scraper para extraer calificaciones de riesgo de sociedades de la Comisión Nacional de Valores (CNV) de Argentina, filtrando por la categoría **Empresas**.

## 📋 Características

- ✅ Extrae calificaciones de la categoría **Empresas** (tipoId=2)
- ✅ Obtiene datos de la tabla: fecha, tipo de título, instrumento, calificadora, calificación
- ✅ Extrae el resumen detallado del XML (moneda, monto, perspectiva, rating watch, etc.)
- ✅ **Descarga PDFs con Playwright**: Usa navegador headless para descargar informes automáticamente
- ✅ **Optimizado**: Descarga 1 PDF por fecha única (evita duplicados)
- ✅ **Preview antes de ejecutar**: Muestra estimaciones de tiempo y recursos
- ✅ Guarda datos en CSV y JSON (backup)
- ✅ **Reanudable**: puede interrumpirse y continuar desde donde quedó
- ✅ Modo prueba para validaciones
- ✅ Registra errores de descarga en el CSV
- ✅ CLI moderna con **Typer** y **Rich**
- ✅ Logging estructurado con **Structlog**
- ✅ Gestión de dependencias con **uv**

## 📁 Estructura del Proyecto

```
scraper_cnv/
├── src/
│   └── scraper_cnv/         # Paquete principal
│       ├── __init__.py
│       ├── __main__.py      # Entry point
│       ├── cli.py           # CLI con Typer + Rich
│       ├── scraper.py       # Lógica de scraping
│       ├── pdf_downloader.py # Descarga PDFs con Playwright
│       ├── config.py        # Configuraciones
│       └── logging_config.py # Configuración de structlog
├── tests/                   # Tests
├── downloads/
│   ├── informes/            # PDFs descargados
│   └── resumen_json/        # JSON por CUIT (backup)
├── data/
│   ├── estado_scraper.json  # Estado para reanudar
│   ├── sociedades_cache.json # Cache de sociedades
│   └── logs/                # Logs de ejecución
├── calificaciones.csv       # Output principal
├── pyproject.toml           # Configuración uv
└── README.md
```

## 🚀 Instalación

### Requisitos

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes)

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd scraper_cnv
```

### 2. Instalar dependencias con uv

```bash
uv sync
```

### 3. Instalar navegador Chromium para Playwright

```bash
uv run playwright install chromium
```

## 🎯 Uso

### Comandos disponibles

```bash
# Ver ayuda
uv run scraper-cnv --help

# Ejecutar scraper en modo prueba (interactivo)
uv run scraper-cnv scrape prueba

# Ejecutar scraper con límite específico
uv run scraper-cnv scrape prueba --limite 5

# Ejecutar scraper en modo completo
uv run scraper-cnv scrape completo

# Reanudar ejecución interrumpida
uv run scraper-cnv scrape reanudar

# Ver estadísticas
uv run scraper-cnv stats

# Descargar PDFs de un CUIT específico
uv run scraper-cnv download 30696170580
```

### Ejemplos de uso

#### Modo Prueba (recomendado para validar)

```bash
uv run scraper-cnv scrape prueba
```

Te pedirá cuántas sociedades procesar, mostrará un preview con estimaciones y luego ejecutará.

#### Modo Completo

```bash
uv run scraper-cnv scrape completo
```

Procesa todas las sociedades con categoría Empresas (~400-500 sociedades).

#### Reanudar

```bash
uv run scraper-cnv scrape reanudar
```

Continúa desde donde quedó si el scraper se interrumpió.

#### Ver Estadísticas

```bash
uv run scraper-cnv stats
```

Muestra información sobre:
- Sociedades procesadas/pendientes
- Calificaciones encontradas
- PDFs descargados
- Errores
- Último CUIT procesado

## 📊 Output

### CSV Principal (`calificaciones.csv`)

Columnas incluidas:
- `cuit` - CUIT de la sociedad
- `razon_social` - Nombre de la empresa
- `calificadora` - Nombre de la agencia calificadora
- `cuit_calificadora` - CUIT de la calificadora
- `fecha_consejo` - Fecha del consejo/directorio
- `tipo_emision` - Tipo de emisión (Emisoras a Largo/Corto Plazo)
- `moneda_a_calificar` - Moneda de la calificación
- `monto_emision` - Monto de la emisión
- `calificacion_categoria` - Rating asignado
- `calificacion_prefijos` - Prefijos del rating
- `calificacion_sufijos` - Sufijos del rating
- `calificacion_signo` - Signo (+/-)
- `perspectiva` - Perspectiva (Estable, Positiva, Negativa)
- `rating_watch` - Rating Watch
- `resultado_calificacion` - Resultado (Confirma, Mejora, etc.)
- `instrumento` - Instrumento calificado
- `url_resumen` - URL al formulario de resumen
- `presentacion_id` - ID de la presentación
- `nombre_archivo_informe` - Nombre original del PDF
- `ruta_pdf_descargado` - Ruta local del PDF descargado
- `estado_descarga` - Estado (EXITOSO, ERROR_404, etc.)
- `error_detalle` - Detalle del error si falló
- `fecha_extraccion` - Fecha de extracción

### PDFs Descargados

Ubicación: `downloads/informes/`

Nomenclatura: `{CUIT}_{YYYY-MM-DD}_{EMPRESA}.pdf`

Ejemplos:
- `30711204055_2025-12-09_360_ENERGY_SOLAR_SA.pdf`
- `30618705672_2025-11-15_ADECO_AGROPECUARIA_SA.pdf`

### JSONs por Sociedad

Ubicación: `downloads/resumen_json/{CUIT}.json`

Contiene todos los datos extraídos de esa sociedad (backup completo).

## 🔧 Configuración

Puedes modificar `src/scraper_cnv/config.py` para ajustar:

- `DELAY_ENTRE_REQUESTS` - Tiempo entre requests (default: 1 segundo)
- `RETRY_ATTEMPTS` - Intentos de reintento (default: 3)
- `REQUEST_TIMEOUT` - Timeout de requests (default: 30 segundos)
- `GUARDAR_ESTADO_CADA` - Guardar estado cada N sociedades (default: 10)

## 🐛 Manejo de Errores

El scraper registra diferentes tipos de errores:

| Estado | Descripción |
|--------|-------------|
| `EXITOSO` | PDF descargado correctamente |
| `NO_HAY_INFORME` | No hay GUID de informe disponible |
| `ERROR_404` | URL del informe no existe |
| `ERROR_TIMEOUT` | Timeout al descargar |
| `ERROR_ARCHIVO_CORRUPTO` | PDF descargado con 0 bytes |
| `ERROR_OTRO` | Otro error (ver `error_detalle`) |

Los errores se registran en:
- Columna `estado_descarga` del CSV
- Columna `error_detalle` para más información
- Archivo de log en `data/logs/`

## 📝 Logs

Los logs se guardan en `data/logs/` usando **structlog**:

- Formato JSON en producción
- Formato legible en modo debug (`--debug`)

Ejemplo de log:
```json
{
  "event": "processing_company",
  "cuit": "30696170580",
  "razon_social": "AEROPUERTOS ARGENTINA 2000 SA",
  "timestamp": "2025-01-15T10:30:00.000000Z"
}
```

## ⚠️ Notas Importantes

1. **Conexión a Internet**: El scraper requiere conexión estable a internet
2. **Tiempo de ejecución**: El modo completo puede tardar 45-90 minutos
3. **Rate limiting**: Hay delays entre requests para no sobrecargar el servidor
4. **Reanudación**: Si se interrumpe, usa `scrape reanudar` para continuar
5. **Cache**: Las sociedades se cachean en `data/sociedades_cache.json` (puedes borrarlo para refrescar)

## 🔍 Ejemplo de Uso Completo

```bash
# 1. Entrar al directorio
cd scraper_cnv

# 2. Ejecutar modo prueba
uv run scraper-cnv scrape prueba --limite 5

# 3. Si todo va bien, ejecutar modo completo
uv run scraper-cnv scrape completo

# 4. Ver resultados
cat calificaciones.csv
ls downloads/informes/

# 5. Ver estadísticas
uv run scraper-cnv stats
```

## 🛠️ Desarrollo

### Linting y Formato

```bash
# Verificar código con ruff
uv run ruff check src/

# Formatear código
uv run ruff format src/

# Type checking con mypy
uv run mypy src/
```

### Tests

```bash
# Ejecutar tests
uv run pytest
```

## 📄 Licencia

Este proyecto es de uso libre. Respeta los términos de uso de la CNV.

## 🆘 Soporte

Si encuentras algún problema:
1. Revisa los logs en `data/logs/`
2. Verifica que tengas conexión a internet
3. Asegúrate de tener instalado Chromium: `uv run playwright install chromium`
4. Intenta ejecutar en modo prueba primero
5. Usa `--debug` para ver logs detallados

## 🔄 Migración desde versión anterior

Si venías usando la versión anterior con scripts sueltos:

1. **Instala uv** siguiendo las instrucciones de https://docs.astral.sh/uv/
2. **Ejecuta `uv sync`** para instalar dependencias
3. **Elimina el viejo `venv/`** si existe
4. Usa `uv run scraper-cnv` en lugar de `python scraper.py`

Los archivos de datos (`data/`, `downloads/`, `calificaciones.csv`) son compatibles.
