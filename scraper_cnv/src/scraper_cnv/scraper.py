"""Scraper principal para CNV Calificaciones."""

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from pathlib import Path

from scraper_cnv.config import (
    AIF2_URL,
    BLOB_URL,
    CACHE_FILE,
    CATEGORIA_EMPRESAS_ID,
    CSV_COLUMNS,
    CSV_OUTPUT,
    DEFAULT_HEADERS,
    DELAY_ENTRE_REQUESTS,
    ENDPOINTS,
    ESTADO_FILE,
    ESTADOS_DESCARGA,
    GUARDAR_ESTADO_CADA,
    INFORMES_DIR,
    LOGS_DIR,
    REQUEST_TIMEOUT,
    RESUMEN_JSON_DIR,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    TOTAL_PAGINAS,
    XML_RAW_DIR,
)
from scraper_cnv.logging_config import get_logger
from scraper_cnv.pdf_downloader import PDFDownloader

logger = get_logger("scraper")


class CNVScraper:
    """Scraper principal para CNV Calificaciones."""

    def __init__(self) -> None:
        """Inicializa el scraper."""
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.estado = self._cargar_estado()
        logger.info("scraper_initialized")

    def _cargar_estado(self) -> dict[str, Any]:
        """Carga el estado anterior si existe."""
        if ESTADO_FILE.exists():
            logger.info("loading_state_from_file", file=str(ESTADO_FILE))
            with open(ESTADO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "fecha_inicio": None,
            "modo_ejecucion": None,
            "total_sociedades": 0,
            "sociedades_procesadas": 0,
            "sociedades_pendientes": 0,
            "ultimo_cuit_procesado": None,
            "ultimo_indice": 0,
            "total_calificaciones_encontradas": 0,
            "total_pdfs_descargados": 0,
            "total_errores": 0,
            "csv_ruta": str(CSV_OUTPUT),
            "completado": False,
            "errores_detalle": [],
        }

    def _guardar_estado(self) -> None:
        """Guarda el estado actual del scraper."""
        with open(ESTADO_FILE, "w", encoding="utf-8") as f:
            json.dump(self.estado, f, indent=2, ensure_ascii=False)
        logger.debug("state_saved", file=str(ESTADO_FILE))

    def _make_request(
        self, url: str, params: Optional[dict[str, Any]] = None, intento: int = 1
    ) -> Optional[requests.Response]:
        """Realiza una petición HTTP con reintentos."""
        try:
            time.sleep(DELAY_ENTRE_REQUESTS)
            response = self.session.get(
                url, params=params, timeout=REQUEST_TIMEOUT, allow_redirects=True
            )
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            if intento < RETRY_ATTEMPTS:
                logger.warning(
                    "request_timeout_retrying",
                    url=url,
                    attempt=intento,
                    max_attempts=RETRY_ATTEMPTS,
                )
                time.sleep(RETRY_DELAY * intento)
                return self._make_request(url, params, intento + 1)
            else:
                logger.error("request_timeout_final", url=url)
                return None
        except requests.exceptions.RequestException as e:
            if intento < RETRY_ATTEMPTS:
                logger.warning(
                    "request_error_retrying",
                    url=url,
                    error=str(e),
                    attempt=intento,
                    max_attempts=RETRY_ATTEMPTS,
                )
                time.sleep(RETRY_DELAY * intento)
                return self._make_request(url, params, intento + 1)
            else:
                logger.error("request_error_final", url=url, error=str(e))
                return None

    def obtener_sociedades(self, forzar_refresh: bool = False) -> list[dict[str, Any]]:
        """Obtiene la lista de todas las sociedades calificadas."""
        if not forzar_refresh and CACHE_FILE.exists():
            logger.info("loading_companies_from_cache", file=str(CACHE_FILE))
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)

        logger.info("fetching_companies_from_cnv")
        sociedades: list[dict[str, Any]] = []

        for pagina in tqdm(range(1, TOTAL_PAGINAS + 1), desc="Obteniendo sociedades"):
            response = self._make_request(ENDPOINTS["sociedades"], params={"pagina": pagina})

            if not response:
                logger.error("failed_to_fetch_page", page=pagina)
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            paneles = soup.find_all("div", class_="panel level0")

            for panel in paneles:
                link = panel.find("a", class_="sel-calificacion")
                if link and link.get("data-id"):
                    cuit = link.get("data-id")
                    nombre = link.text.strip()
                    if cuit and nombre:  # Ignorar el primer panel vacío
                        sociedades.append(
                            {
                                "cuit": cuit,
                                "razon_social": nombre,
                                "tiene_empresas": None,  # Se determinará después
                            }
                        )

        logger.info("companies_fetched", total=len(sociedades))

        # Guardar en caché
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(sociedades, f, indent=2, ensure_ascii=False)
        logger.info("companies_cached", file=str(CACHE_FILE))

        return sociedades

    def verificar_categoria_empresas(self, cuit: str) -> bool:
        """Verifica si una sociedad tiene calificaciones en categoría Empresas."""
        response = self._make_request(ENDPOINTS["titulos"], params={"cuit": cuit})

        if not response:
            logger.warning("no_response_for_cuit", cuit=cuit)
            return False

        # Buscar data-tipoTitulo="2" en el HTML
        tiene_empresas = f'data-tipoTitulo="{CATEGORIA_EMPRESAS_ID}"' in response.text

        if tiene_empresas:
            logger.debug("cuit_has_empresas_category", cuit=cuit)
        else:
            logger.debug("cuit_no_empresas_category", cuit=cuit)

        return tiene_empresas

    def filtrar_sociedades_empresas(self, sociedades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filtra solo las sociedades que tienen categoría Empresas."""
        logger.info("filtering_companies_with_empresas_category")

        # Separar sociedades en grupos según estado de verificación
        ya_verificadas_con_empresas: list[dict[str, Any]] = []
        ya_verificadas_sin_empresas: list[dict[str, Any]] = []
        pendientes_verificar: list[dict[str, Any]] = []

        for sociedad in sociedades:
            tiene_emp = sociedad.get("tiene_empresas")
            if tiene_emp is True:
                ya_verificadas_con_empresas.append(sociedad)
            elif tiene_emp is False:
                ya_verificadas_sin_empresas.append(sociedad)
            else:
                pendientes_verificar.append(sociedad)

        logger.info(
            "companies_verification_status",
            with_empresas=len(ya_verificadas_con_empresas),
            without_empresas=len(ya_verificadas_sin_empresas),
            pending=len(pendientes_verificar),
        )

        # Procesar solo las pendientes
        if pendientes_verificar:
            logger.info("verifying_pending_companies", count=len(pendientes_verificar))

            for sociedad in tqdm(pendientes_verificar, desc="Verificando categorías"):
                if self.verificar_categoria_empresas(sociedad["cuit"]):
                    sociedad["tiene_empresas"] = True
                    ya_verificadas_con_empresas.append(sociedad)
                else:
                    sociedad["tiene_empresas"] = False
                    ya_verificadas_sin_empresas.append(sociedad)

            # Actualizar caché con la nueva información
            logger.info("updating_cache_with_verifications")
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(sociedades, f, indent=2, ensure_ascii=False)
        else:
            logger.info("all_companies_already_verified_in_cache")

        total_con_empresas = len(ya_verificadas_con_empresas)
        logger.info("companies_with_empresas_category", total=total_con_empresas)

        return ya_verificadas_con_empresas

    def extraer_calificaciones_tabla(self, cuit: str) -> list[dict[str, Any]]:
        """Extrae las calificaciones desde la tabla HTML."""
        response = self._make_request(
            ENDPOINTS["calificaciones"],
            params={"cuit": cuit, "tipoId": CATEGORIA_EMPRESAS_ID},
        )

        if not response:
            logger.warning("no_response_for_calificaciones", cuit=cuit)
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Buscar tabla por clase (no por ID)
        tabla = soup.find("table", class_="tabla-hechos-relevantes")

        if not tabla:
            logger.warning("calificaciones_table_not_found", cuit=cuit)
            tablas = soup.find_all("table")
            if tablas:
                logger.debug("tables_found_in_page", count=len(tablas), cuit=cuit)
            return []

        logger.debug("calificaciones_table_found", cuit=cuit)

        calificaciones: list[dict[str, Any]] = []
        tbody = tabla.find("tbody")
        if tbody:
            filas = tbody.find_all("tr")
            logger.debug("rows_found_in_table", count=len(filas), cuit=cuit)

            for fila in filas:
                celdas = fila.find_all("td")
                if len(celdas) >= 6:
                    # Extraer enlace al formulario si existe
                    link_elem = celdas[5].find("a")
                    url_formulario: Optional[str] = None
                    if link_elem and link_elem.get("href"):
                        url_formulario = link_elem.get("href")
                        if not url_formulario.startswith("http"):
                            url_formulario = urljoin(AIF2_URL, url_formulario)

                    calificacion = {
                        "fecha": celdas[0].text.strip() if len(celdas) > 0 else "",
                        "tipo_titulo": celdas[1].text.strip() if len(celdas) > 1 else "",
                        "instrumento": celdas[2].text.strip() if len(celdas) > 2 else "",
                        "calificadora": celdas[3].text.strip() if len(celdas) > 3 else "",
                        "calificacion": celdas[4].text.strip() if len(celdas) > 4 else "",
                        "url_formulario": url_formulario,
                    }
                    calificaciones.append(calificacion)
                    logger.debug(
                        "calificacion_extracted",
                        cuit=cuit,
                        fecha=calificacion["fecha"],
                        calificadora=calificacion["calificadora"],
                    )
        else:
            logger.warning("no_tbody_in_table", cuit=cuit)

        return calificaciones

    def extraer_resumen_xml(self, url_resumen: str) -> list[dict[str, Any]]:
        """Extrae los resúmenes detallados de cada fila del XML en la página de presentación."""
        if not url_resumen:
            return []

        response = self._make_request(url_resumen)
        if not response:
            return []

        cuit_calificadora = ""
        presentacion_id = ""
        xml_content = ""

        try:
            html_text = response.text

            # Extraer CUIT de la calificadora del título
            title_match = re.search(r"\| (\d+) - Comisión Nacional de Valores", html_text)
            if title_match:
                cuit_calificadora = title_match.group(1)

            # Extraer presentación ID
            pres_id_match = re.search(r"Presentaci&#xF3;n #(\d+)", html_text)
            presentacion_id = pres_id_match.group(1) if pres_id_match else ""

            # Buscar el XML en la variable presentation
            xml_match = re.search(r"var presentation\s*=\s*'(.*?)';", html_text, re.DOTALL)
            if not xml_match:
                return [
                    {
                        "cuit_calificadora": cuit_calificadora,
                        "presentacion_id": presentacion_id,
                        "error": "No se encontró variable presentation",
                    }
                ]

            xml_content = xml_match.group(1)
            # Decodificar entidades HTML
            xml_content = xml_content.replace("&lt;", "<").replace("&gt;", ">")
            xml_content = xml_content.replace("&quot;", '"').replace("&amp;", "&")

            # Guardar XML raw para debugging
            self._guardar_xml_raw(presentacion_id, xml_content)

            # Parsear el XML
            root = ET.fromstring(xml_content)

            resumenes: list[dict[str, Any]] = []

            # Extraer info del PDF desde la entidad Adjunto (común a todas las filas)
            nombre_archivo_pdf = ""
            guid_pdf = ""
            for entidad in root.iter("entidad"):
                clave = entidad.get("clave", "")
                if clave == "Adjunto" or "adjunto" in clave.lower():
                    for prop in entidad.iter("propiedad"):
                        prop_id = prop.get("id", "")
                        archivo_text = prop.text or ""
                        if ".pdf" in archivo_text.lower():
                            nombre_archivo_pdf = archivo_text
                            guid_match = re.search(r"([a-f0-9-]{36})", archivo_text)
                            if guid_match:
                                guid_pdf = guid_match.group(1)
                    break

            # Fallback GUID en todo el HTML
            if not guid_pdf:
                guid_pattern = r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"
                guids = re.findall(guid_pattern, response.text)
                if guids:
                    guid_pdf = guids[0]

            # Buscar la entidad grid y extraer cada fila
            for entidad in root.iter("entidad"):
                if entidad.get("grid") == "1" or entidad.get("clave") == "Grilla":
                    for fila in entidad.iter("fila"):
                        props: dict[str, str] = {}
                        for prop in fila.iter("propiedad"):
                            prop_id = prop.get("id", "")
                            props[prop_id] = prop.text or ""

                        # Parsear fechaConsejo
                        fecha_consejo_raw = props.get("fechaConsejo", "")
                        fecha_consejo = ""
                        if fecha_consejo_raw:
                            try:
                                dt = datetime.fromisoformat(
                                    fecha_consejo_raw.replace("Z", "+00:00")
                                )
                                fecha_consejo = dt.strftime("%d/%m/%Y")
                            except Exception:
                                fecha_consejo = fecha_consejo_raw

                        # Humanizar tipo_emision (id puede ser "EmisorasaLargoPlazo")
                        tipo_emision_raw = props.get("id", "")
                        tipo_emision = re.sub(r"(?<!^)(?=[A-Z])", " ", tipo_emision_raw)

                        resumen = {
                            "cuit_calificadora": cuit_calificadora,
                            "presentacion_id": presentacion_id,
                            "tipo_emision": tipo_emision,
                            "moneda_a_calificar": props.get("MonedaACalificar", ""),
                            "monto": props.get("montoCalif", ""),
                            "fecha_consejo": fecha_consejo,
                            "categoria": props.get("categoria", ""),
                            "prefijos": props.get("prefijos", ""),
                            "sufijos": props.get("sufijos", ""),
                            "signo": props.get("signo", ""),
                            # El XML usa "persepectiva" (con typo) con valor tipo "3-Estable"
                            "perspectiva": props.get("persepectiva", ""),
                            "rating_watch": props.get("rating", ""),
                            "resultado_calificacion": props.get("resultado", ""),
                            "nombre_archivo_pdf": nombre_archivo_pdf,
                            "guid_pdf": guid_pdf,
                            "texto_calificacion_completo": props.get("CalificacionFinal", ""),
                            "quecalifica": props.get("quecalifica", ""),
                        }
                        resumenes.append(resumen)
                    break

            return resumenes

        except ET.ParseError as e:
            logger.error("xml_parse_error", error=str(e))
            return [
                {
                    "cuit_calificadora": cuit_calificadora,
                    "presentacion_id": presentacion_id,
                    "error": f"XML inválido: {str(e)}",
                }
            ]
        except Exception as e:
            logger.error("resumen_extraction_error", error=str(e))
            return [{"error": str(e)}]

    def _guardar_xml_raw(self, presentacion_id: str, xml_content: str) -> None:
        """Guarda el XML raw para debugging."""
        try:
            nombre = (
                f"{presentacion_id}.xml"
                if presentacion_id
                else f"unknown_{datetime.now().strftime('%Y%m%d%H%M%S')}.xml"
            )
            ruta = XML_RAW_DIR / nombre
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(xml_content)
        except Exception as e:
            logger.warning("xml_raw_save_failed", error=str(e))

    def _parsear_texto_calificacion(self, texto: str) -> dict[str, str]:
        """Parsea el texto de calificación en sus componentes."""
        partes: dict[str, str] = {
            "empresa": "",
            "tipo_emision": "",
            "moneda_a_calificar": "",
            "monto": "",
            "fecha_consejo": "",
            "categoria": "",
            "prefijos": "",
            "sufijos": "",
            "signo": "",
            "perspectiva": "",
            "rating_watch": "",
            "resultado_calificacion": "",
        }

        try:
            # Extraer empresa (todo antes del primer :)
            if ":" in texto:
                partes["empresa"] = texto.split(":")[0]

            # Buscar patrones específicos
            patrones = {
                "tipo_emision": r":(Emisora\w+):",
                "moneda_a_calificar": r"MonedaaCalificar:(.*?)(?=Monto:|$)",
                "monto": r"Monto:([^:]*):",
                "fecha_consejo": r"FechaConsejo:(\d{2}/\d{2}/\d{4})",
                "categoria": r"Categoría:([^:]+?)(?=Prefijos:)",
                "prefijos": r"Prefijos:([^:]*):",
                "sufijos": r"Sufijos:([^:]*):",
                "signo": r"Signo:([^:]*):",
                "perspectiva": r"Perspectiva:([^:]*?)(?=RatingWatch:)",
                "rating_watch": r"RatingWatch:([^:]*):",
                "resultado_calificacion": r"ResultadoCalificación:([^:]+?)(?:$|:)",
            }

            for campo, patron in patrones.items():
                match = re.search(patron, texto)
                if match:
                    partes[campo] = match.group(1).strip()

        except Exception as e:
            logger.error("parse_calificacion_text_error", error=str(e))

        return partes

    def descargar_pdf(
        self, guid: str, nombre_archivo: str, cuit: str, fecha: str
    ) -> tuple[str, str, str]:
        """Descarga el PDF del informe."""
        if not guid:
            return "", ESTADOS_DESCARGA["NO_HAY_INFORME"], "No hay GUID disponible"

        url_descarga = f"{BLOB_URL}/Download/{guid}"

        nombre_limpio = self._limpiar_nombre_archivo(cuit, fecha, nombre_archivo)
        ruta_destino = INFORMES_DIR / nombre_limpio

        # Si ya existe, no descargar de nuevo
        if ruta_destino.exists():
            return (
                str(ruta_destino),
                ESTADOS_DESCARGA["EXITOSO"],
                "Archivo ya existente",
            )

        try:
            response = self._make_request(url_descarga)

            if not response:
                return "", ESTADOS_DESCARGA["ERROR_TIMEOUT"], "Timeout al descargar"

            # Verificar que es un PDF
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and response.content[:4] != b"%PDF":
                return (
                    "",
                    ESTADOS_DESCARGA["ERROR_404"],
                    f"Content-Type: {content_type}",
                )

            # Verificar tamaño
            if len(response.content) == 0:
                return (
                    "",
                    ESTADOS_DESCARGA["ERROR_ARCHIVO_CORRUPTO"],
                    "Archivo vacío",
                )

            # Guardar archivo
            with open(ruta_destino, "wb") as f:
                f.write(response.content)

            return str(ruta_destino), ESTADOS_DESCARGA["EXITOSO"], ""

        except Exception as e:
            return "", ESTADOS_DESCARGA["ERROR_OTRO"], str(e)

    def _limpiar_nombre_archivo(self, cuit: str, fecha: str, nombre_original: str) -> str:
        """Limpia y construye el nombre del archivo."""
        fecha_iso = fecha
        if "/" in fecha:
            try:
                partes = fecha.split("/")
                fecha_iso = f"{partes[2]}-{partes[1]}-{partes[0]}"
            except Exception:
                fecha_iso = datetime.now().strftime("%Y-%m-%d")

        nombre_limpio = nombre_original.replace(".pdf", "")
        nombre_limpio = re.sub(r"[^\w\s-]", "", nombre_limpio)
        nombre_limpio = nombre_limpio.replace(" ", "_").upper()

        if len(nombre_limpio) > 50:
            nombre_limpio = nombre_limpio[:50]

        return f"{cuit}_{fecha_iso}_{nombre_limpio}.pdf"

    def procesar_sociedad_con_playwright(
        self, sociedad: dict[str, Any], pdf_downloader: PDFDownloader
    ) -> list[dict[str, Any]]:
        """Procesa una sociedad usando Playwright para descargar PDFs."""
        cuit = sociedad["cuit"]
        razon_social = sociedad["razon_social"]

        logger.info("processing_company", cuit=cuit, razon_social=razon_social)

        calificaciones_tabla = self.extraer_calificaciones_tabla(cuit)

        if not calificaciones_tabla:
            logger.warning("no_calificaciones_found", cuit=cuit)
            return []

        logger.info("calificaciones_found", cuit=cuit, count=len(calificaciones_tabla))

        # Agrupar calificaciones por (fecha, url_formulario) única
        calificaciones_por_grupo: dict[str, dict[str, Any]] = {}
        for calif in calificaciones_tabla:
            fecha = calif.get("fecha", "")
            url = calif.get("url_formulario", "")
            clave = f"{fecha}|{url}"

            if clave not in calificaciones_por_grupo:
                calificaciones_por_grupo[clave] = {
                    "fecha": fecha,
                    "url": url,
                    "calificaciones": [],
                }
            calificaciones_por_grupo[clave]["calificaciones"].append(calif)

        logger.info("unique_groups_found", cuit=cuit, count=len(calificaciones_por_grupo))

        resultados: list[dict[str, Any]] = []

        for clave, grupo in calificaciones_por_grupo.items():
            fecha = grupo["fecha"]
            url = grupo["url"]
            califs_grupo = grupo["calificaciones"]

            logger.debug("processing_group", cuit=cuit, fecha=fecha, count=len(califs_grupo))

            resumenes: list[dict[str, Any]] = []
            if url:
                resumenes = self.extraer_resumen_xml(url)

            ruta_pdf = ""
            estado_descarga = ESTADOS_DESCARGA["NO_HAY_INFORME"]
            error_detalle = ""
            nombre_archivo_pdf = ""
            guid_pdf = ""

            if url and resumenes:
                # Tomar el GUID/Nombre del primer resumen (PDF es común a la presentación)
                guid_pdf = resumenes[0].get("guid_pdf", "")
                nombre_archivo_pdf_raw = resumenes[0].get("nombre_archivo_pdf", "")

                try:
                    fecha_iso = fecha
                    if "/" in fecha:
                        try:
                            partes = fecha.split("/")
                            fecha_iso = f"{partes[2]}-{partes[1]}-{partes[0]}"
                        except Exception:
                            fecha_iso = datetime.now().strftime("%Y-%m-%d")

                    if guid_pdf:
                        ruta_pdf = pdf_downloader.descargar_pdf(
                            url=url, cuit=cuit, fecha=fecha_iso, empresa=razon_social
                        )
                        estado_descarga = ESTADOS_DESCARGA["EXITOSO"]
                        self.estado["total_pdfs_descargados"] += 1
                        nombre_archivo_pdf = Path(ruta_pdf).name
                    elif nombre_archivo_pdf_raw:
                        # Hay PDF pero no se descargó directamente
                        ruta_pdf = ""
                        estado_descarga = ESTADOS_DESCARGA["NO_HAY_INFORME"]
                        nombre_archivo_pdf = nombre_archivo_pdf_raw
                    else:
                        estado_descarga = ESTADOS_DESCARGA["NO_HAY_INFORME"]

                except Exception as e:
                    estado_descarga = ESTADOS_DESCARGA["ERROR_OTRO"]
                    error_detalle = str(e)
                    self.estado["total_errores"] += 1
                    self.estado["errores_detalle"].append(
                        {
                            "cuit": cuit,
                            "fecha": fecha,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    logger.error("pdf_download_error", cuit=cuit, fecha=fecha, error=str(e))

            nombre_calificadora = ""
            if califs_grupo:
                nombre_calificadora = califs_grupo[0].get("calificadora", "")

            if resumenes and not any("error" in r for r in resumenes):
                # Fuente principal: XML.  Cada fila del XML genera un registro.
                for resumen in resumenes:
                    registro = {
                        "cuit": cuit,
                        "razon_social": razon_social,
                        "calificadora": nombre_calificadora,
                        "cuit_calificadora": resumen.get("cuit_calificadora", ""),
                        "fecha_consejo": resumen.get("fecha_consejo", fecha),
                        "tipo_emision": resumen.get("tipo_emision", ""),
                        "moneda_a_calificar": resumen.get("moneda_a_calificar", ""),
                        "monto_emision": resumen.get("monto", ""),
                        "calificacion_categoria": resumen.get("categoria", ""),
                        "calificacion_prefijos": resumen.get("prefijos", ""),
                        "calificacion_sufijos": resumen.get("sufijos", ""),
                        "calificacion_signo": resumen.get("signo", ""),
                        "perspectiva": resumen.get("perspectiva", ""),
                        "rating_watch": resumen.get("rating_watch", ""),
                        "resultado_calificacion": resumen.get("resultado_calificacion", ""),
                        "instrumento": resumen.get("tipo_emision", ""),
                        "url_resumen": url,
                        "presentacion_id": resumen.get("presentacion_id", ""),
                        "nombre_archivo_informe": nombre_archivo_pdf,
                        "ruta_pdf_descargado": ruta_pdf,
                        "estado_descarga": estado_descarga,
                        "error_detalle": error_detalle,
                        "fecha_extraccion": datetime.now().isoformat(),
                    }
                    resultados.append(registro)
                    self.estado["total_calificaciones_encontradas"] += 1

                if califs_grupo:
                    self._guardar_json_sociedad(
                        cuit, razon_social, url, nombre_calificadora, resumenes, resultados[-1]
                    )
            else:
                # Fallback: no hay XML o viene con error; usar datos del HTML.
                for calif in califs_grupo:
                    registro = {
                        "cuit": cuit,
                        "razon_social": razon_social,
                        "calificadora": calif.get("calificadora", ""),
                        "cuit_calificadora": "",
                        "fecha_consejo": calif.get("fecha", ""),
                        "tipo_emision": "",
                        "moneda_a_calificar": "",
                        "monto_emision": "",
                        "calificacion_categoria": calif.get("calificacion", ""),
                        "calificacion_prefijos": "",
                        "calificacion_sufijos": "",
                        "calificacion_signo": "",
                        "perspectiva": "",
                        "rating_watch": "",
                        "resultado_calificacion": "",
                        "instrumento": calif.get("instrumento", ""),
                        "url_resumen": url,
                        "presentacion_id": "",
                        "nombre_archivo_informe": nombre_archivo_pdf,
                        "ruta_pdf_descargado": ruta_pdf,
                        "estado_descarga": estado_descarga,
                        "error_detalle": error_detalle,
                        "fecha_extraccion": datetime.now().isoformat(),
                    }
                    resultados.append(registro)
                    self.estado["total_calificaciones_encontradas"] += 1

        return resultados

    def _guardar_json_sociedad(
        self,
        cuit: str,
        razon_social: str,
        url_resumen: str,
        nombre_calificadora: str,
        resumenes: list[dict[str, Any]],
        registro: dict[str, Any],
    ) -> None:
        """Guarda los datos de una sociedad en JSON."""
        json_data: dict[str, Any] = {
            "cuit": cuit,
            "razon_social": razon_social,
            "fecha_extraccion": datetime.now().isoformat(),
            "url_resumen": url_resumen,
            "calificaciones": [],
            "informe": {
                "nombre_archivo": registro.get("nombre_archivo_informe", ""),
                "guid": (
                    resumenes[0].get("guid_pdf", "")
                    if resumenes and isinstance(resumenes, list)
                    else ""
                ),
                "descargado": registro.get("estado_descarga") == ESTADOS_DESCARGA["EXITOSO"],
                "ruta_local": registro.get("ruta_pdf_descargado", ""),
                "error": registro.get("error_detalle", ""),
            },
            "metadatos_extraccion": {
                "presentacion_id": (
                    resumenes[0].get("presentacion_id", "")
                    if resumenes and isinstance(resumenes, list)
                    else ""
                ),
                "formulario": "Formulario Único para la Carga de Calificaciones",
                "fecha_extraccion_completa": datetime.now().isoformat(),
                "version_scraper": "1.1",
            },
        }

        # Guardar todas las calificaciones de esta presentación
        for resumen in (resumenes if resumenes and isinstance(resumenes, list) else []):
            json_data["calificaciones"].append(
                {
                    "calificadora": nombre_calificadora,
                    "cuit_calificadora": resumen.get("cuit_calificadora", ""),
                    "fecha_consejo": resumen.get("fecha_consejo", ""),
                    "tipo_emision": resumen.get("tipo_emision", ""),
                    "moneda_a_calificar": resumen.get("moneda_a_calificar", ""),
                    "monto_emision": resumen.get("monto", ""),
                    "calificacion_categoria": resumen.get("categoria", ""),
                    "calificacion_prefijos": resumen.get("prefijos", ""),
                    "calificacion_sufijos": resumen.get("sufijos", ""),
                    "calificacion_signo": resumen.get("signo", ""),
                    "perspectiva": resumen.get("perspectiva", ""),
                    "rating_watch": resumen.get("rating_watch", ""),
                    "resultado_calificacion": resumen.get("resultado_calificacion", ""),
                    "instrumento": resumen.get("tipo_emision", ""),
                }
            )

        json_path = RESUMEN_JSON_DIR / f"{cuit}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

    def guardar_csv(self, registros: list[dict[str, Any]], modo_append: bool = False) -> None:
        """Guarda los registros en el CSV."""
        df = pd.DataFrame(registros, columns=CSV_COLUMNS)

        if modo_append and CSV_OUTPUT.exists():
            df.to_csv(CSV_OUTPUT, mode="a", header=False, index=False, encoding="utf-8")
            logger.debug("csv_appended", rows=len(registros))
        else:
            df.to_csv(CSV_OUTPUT, index=False, encoding="utf-8")
            logger.debug("csv_created", rows=len(registros))

    def get_estadisticas(self) -> dict[str, Any]:
        """Retorna estadísticas del estado actual."""
        return {
            "fecha_inicio": self.estado.get("fecha_inicio", "N/A"),
            "modo_ejecucion": self.estado.get("modo_ejecucion", "N/A"),
            "total_sociedades": self.estado.get("total_sociedades", 0),
            "sociedades_procesadas": self.estado.get("sociedades_procesadas", 0),
            "sociedades_pendientes": self.estado.get("sociedades_pendientes", 0),
            "calificaciones_encontradas": self.estado.get("total_calificaciones_encontradas", 0),
            "pdfs_descargados": self.estado.get("total_pdfs_descargados", 0),
            "errores": self.estado.get("total_errores", 0),
            "completado": self.estado.get("completado", False),
            "ultimo_cuit_procesado": self.estado.get("ultimo_cuit_procesado", "N/A"),
            "csv_ruta": self.estado.get("csv_ruta", "N/A"),
        }
