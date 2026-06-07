"""PDF Downloader usando Playwright."""

import re
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from scraper_cnv.logging_config import get_logger

logger = get_logger("pdf_downloader")


class PDFDownloader:
    """Maneja la descarga de PDFs usando Playwright."""

    def __init__(self, download_dir: str):
        """Inicializa el downloader.

        Args:
            download_dir: Directorio donde guardar los PDFs
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def descargar_pdf(
        self,
        url: str,
        cuit: str,
        fecha: str,
        empresa: str,
        max_intentos: int = 3,
    ) -> str:
        """Descarga PDF usando Playwright en modo headless.

        Args:
            url: URL de la página de presentación
            cuit: CUIT de la empresa
            fecha: Fecha de consejo
            empresa: Nombre de la empresa
            max_intentos: Número máximo de intentos

        Returns:
            Ruta al archivo descargado

        Raises:
            Exception: Si no se puede descargar después de todos los intentos
        """
        nombre_archivo = f"{cuit}_{fecha}_{self._limpiar_nombre(empresa)}.pdf"
        ruta_destino = self.download_dir / nombre_archivo

        # Si ya existe, no descargar de nuevo
        if ruta_destino.exists():
            logger.info("pdf_already_exists", filename=nombre_archivo)
            return str(ruta_destino)

        # Intentar descargar
        for intento in range(1, max_intentos + 1):
            try:
                logger.info(
                    "downloading_pdf_attempt",
                    attempt=intento,
                    max_attempts=max_intentos,
                    url=url,
                )
                return self._descargar_con_playwright(url, ruta_destino, intento == max_intentos)
            except Exception as e:
                logger.warning("pdf_download_attempt_failed", attempt=intento, error=str(e))
                if intento == max_intentos:
                    raise Exception(
                        f"No se pudo descargar PDF después de {max_intentos} intentos: {e}"
                    )
                time.sleep(2 * intento)  # Espera creciente entre intentos

        # Este punto nunca debería alcanzarse, pero por si acaso
        raise Exception("Error inesperado en descarga de PDF")

    def _descargar_con_playwright(self, url: str, ruta_destino: Path, ultimo_intento: bool) -> str:
        """Realiza la descarga usando Playwright.

        Args:
            url: URL de la página
            ruta_destino: Ruta donde guardar el archivo
            ultimo_intento: Si es el último intento, usar modo headed para debug

        Returns:
            Ruta al archivo descargado
        """
        with sync_playwright() as p:
            # Usar headless=True normalmente, headed solo en último intento para debug
            headless = not ultimo_intento

            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                accept_downloads=True,
                viewport={"width": 1280, "height": 720},
            )

            # Configurar página
            page = context.new_page()

            try:
                # Cargar página
                logger.debug("loading_page", url=url)
                page.goto(url, wait_until="networkidle", timeout=30000)

                # Esperar a que cargue el botón de descarga
                logger.debug("waiting_for_download_button")
                page.wait_for_selector(".downloadFile", timeout=10000)

                # Verificar que el botón tiene data-guid
                download_button = page.locator(".downloadFile").first
                guid = download_button.get_attribute("data-guid")
                nombre_archivo_original = download_button.get_attribute("data-name")

                if not guid:
                    raise Exception("Botón de descarga no tiene atributo data-guid")

                logger.debug(
                    "download_button_found",
                    guid=guid,
                    original_filename=nombre_archivo_original,
                )

                # Configurar manejador de descarga y hacer clic
                logger.debug("initiating_download")

                with page.expect_download(timeout=30000) as download_info:
                    download_button.click()

                download = download_info.value

                # Guardar archivo
                download.save_as(ruta_destino)

                # Verificar que se descargó correctamente
                if not ruta_destino.exists():
                    raise Exception("El archivo no se guardó correctamente")

                file_size = ruta_destino.stat().st_size
                if file_size == 0:
                    ruta_destino.unlink()
                    raise Exception("El archivo descargado está vacío")

                logger.info(
                    "pdf_downloaded_successfully",
                    filename=ruta_destino.name,
                    size_bytes=file_size,
                )

                browser.close()
                return str(ruta_destino)

            except PlaywrightTimeout as e:
                browser.close()
                raise Exception(f"Timeout: {e}")
            except Exception as e:
                browser.close()
                raise e

    def _limpiar_nombre(self, nombre: str) -> str:
        """Limpia el nombre de la empresa para usar en archivo.

        Args:
            nombre: Nombre de la empresa

        Returns:
            Nombre limpio para archivo
        """
        # Convertir a mayúsculas
        nombre = nombre.upper()

        # Reemplazar espacios por guiones bajos
        nombre = nombre.replace(" ", "_")

        # Eliminar caracteres especiales excepto alfanuméricos y guiones bajos
        nombre = re.sub(r"[^A-Z0-9_]", "", nombre)

        # Eliminar múltiples guiones bajos consecutivos
        nombre = re.sub(r"_+", "_", nombre)

        # Eliminar guiones bajos al inicio y final
        nombre = nombre.strip("_")

        # Limitar longitud
        if len(nombre) > 50:
            nombre = nombre[:50]

        return nombre
