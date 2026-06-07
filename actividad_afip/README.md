# Ratings AFIP

Consulta de actividades económicas de CUITs argentinas vía **AFIP SDK** (Padrón A5 – `ws_sr_constancia_inscripcion`).

## Propósito

Dada una lista de CUITs (por ejemplo, empresas calificadas por la CNV), extrae:
- **ID de actividad económica** (CLAE)
- **Descripción** de cada actividad
- **Flag de actividad principal** (`es_actividad_principal = 1`)
- Todas las actividades adicionales del contribuyente
- **Datos crudos completos** guardados por CUIT en JSON para análisis posteriores

## Instalación

Requiere **Python ≥3.10** y `uv` como gestor de paquetes:

```bash
# Instalar uv (si no lo tenés)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clonar y entrar al repo
git clone ...
cd ratings-afip

# Crear entorno e instalar dependencias
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Configuración

Copiar el archivo de ejemplo y completar tus credenciales:

```bash
cp .env.example .env
```

Editar `.env` con:
- `AFIP_ACCESS_TOKEN` → tu token de [app.afipsdk.com](https://app.afipsdk.com)
- `AFIP_CUIT` → tu CUIT (certificado de producción)
- `AFIP_CERT_PATH` / `AFIP_KEY_PATH` → rutas al certificado y clave generados en AFIP

> **Seguridad:** `.env` y la carpeta `afip_keys/` están protegidas por `.gitignore`. Nunca commitear credenciales.

## Uso

### 1. Ver resumen (sin consumir requests)

```bash
uv run ratings-afip resumen ~/Documents/maestria/TT1/scraper_cnv/backup/calificaciones.csv
```

Muestra:
- Total de CUITs en el CSV
- CUITs ya consultados (archivos JSON en cache)
- CUITs faltantes por consultar

### 2. Consultar CUITs faltantes

```bash
uv run ratings-afip consultar ~/Documents/maestria/TT1/scraper_cnv/backup/calificaciones.csv
```

Por defecto **solo consulta los que faltan**, usando cache de archivos JSON para evitar requests repetidas.

Si querés forzar **re-consulta de todos** (consume requests):

```bash
uv run ratings-afip consultar ~/Documents/maestria/TT1/scraper_cnv/backup/calificaciones.csv --todos
```

### 3. Exportar desde cache a CSV

Si solo querés regenerar el CSV a partir de los JSON guardados:

```bash
uv run ratings-afip exportar -o data/output/actividades_economicas.csv
```

## Output

Se generan en `data/output/`:

| Archivo | Descripción |
|---------|-------------|
| `actividades_economicas.csv` | CUIT + actividad + flag principal |
| `raw/{cuit}.json` | Respuesta cruda completa de AFIP por CUIT |
| `errores.csv` | CUITs que fallaron o no existieron en el padrón |
| `summary.json` | Resumen final del lote |

### Formato CSV `actividades_economicas.csv`

```
cuit_consultado,id_actividad,descripcion,nomenclador,orden,periodo,regimen,es_actividad_principal
30711204055,351190,GENERACIÓN DE ENERGÍA N.C.P.,883,1,201602,Régimen General,1
30711204055,429090,CONSTRUCCIÓN DE OBRAS DE INGENIERÍA CIVIL N.C.P.,883,2,202303,Régimen General,0
```

## Arquitectura

```
ratings-afip/
├── src/ratings_afip/
│   ├── __init__.py
│   ├── cli.py         # Typer CLI
│   ├── config.py      # Config centralizada (leída de .env)
│   ├── models.py      # Pydantic models
│   ├── parser.py      # Parseo de respuesta AFIP A5 → lista de actividades
│   └── services.py    # Conexión AFIP SDK + lógica de resumen
├── data/output/raw/   # Cache JSON (no commitear)
├── afip_keys/         # Certificados AFIP (no commitear)
├── pyproject.toml
├── .env.example
└── README.md
```

## Costo / Requests

Plan Free de AFIP SDK: **1 CUIT + 1.000 requests/mes**.  
Con cache de archivos JSON, solo se consume requests para CUITs nuevos. No se vuelve a consultar lo que ya está guardado.

## Licencia

MIT

## Contacto / Soporte

- AFIP SDK oficial: [afipsdk.com](https://afipsdk.com)
- Documentación: [docs.afipsdk.com](https://docs.afipsdk.com)
- Soporte AFIP: sri@arca.gob.ar
