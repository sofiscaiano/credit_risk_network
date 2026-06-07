"""CLI principal para CNV Scraper usando Typer y Rich."""

import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from tqdm import tqdm

from scraper_cnv.config import (
    CSV_OUTPUT,
    ESTADO_FILE,
    INFORMES_DIR,
    LOGS_DIR,
    MODOS,
)
from scraper_cnv.logging_config import configure_logging, get_logger
from scraper_cnv.pdf_downloader import PDFDownloader
from scraper_cnv.scraper import CNVScraper

app = typer.Typer(
    name="scraper-cnv",
    help="Scraper para calificaciones de riesgo de la CNV Argentina",
    rich_markup_mode="rich",
)

console = Console()
logger = get_logger("cli")


class ModoEjecucion(str, Enum):
    """Modos de ejecución del scraper."""

    PRUEBA = "prueba"
    COMPLETO = "completo"
    REANUDAR = "reanudar"


def print_header():
    """Imprime el header de la aplicación."""
    header = Panel.fit(
        Text("CNV SCRAPER - CALIFICACIONES DE RIESGO", style="bold cyan", justify="center"),
        subtitle="Categoría Empresas",
        border_style="cyan",
    )
    console.print(header)
    console.print()


@app.command()
def scrape(
    modo: ModoEjecucion = typer.Argument(
        ModoEjecucion.PRUEBA,
        help="Modo de ejecución: prueba, completo o reanudar",
    ),
    limite: Optional[int] = typer.Option(
        None,
        "--limite",
        "-l",
        help="Límite de sociedades a procesar (solo modo prueba)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Habilitar modo debug con logs detallados",
    ),
):
    """Ejecuta el scraper en el modo especificado."""
    # Configurar logging
    configure_logging(LOGS_DIR, debug=debug)

    print_header()

    scraper = CNVScraper()

    # Obtener sociedades
    with console.status("[bold green]Obteniendo lista de sociedades..."):
        sociedades = scraper.obtener_sociedades()

    if not sociedades:
        console.print("[red]No se pudieron obtener sociedades[/red]")
        raise typer.Exit(1)

    # Filtrar por categoría Empresas
    with console.status("[bold green]Filtrando sociedades con categoría Empresas..."):
        sociedades_empresas = scraper.filtrar_sociedades_empresas(sociedades)

    if not sociedades_empresas:
        console.print("[red]No se encontraron sociedades con categoría Empresas[/red]")
        raise typer.Exit(1)

    # Aplicar límite si es modo prueba
    if modo == ModoEjecucion.PRUEBA:
        if limite is None:
            limite = typer.prompt("¿Cuántas sociedades desea procesar?", type=int)
        sociedades_empresas = sociedades_empresas[:limite]
        console.print(f"[yellow]Modo PRUEBA: Procesando solo {limite} sociedades[/yellow]")

    # Estimar calificaciones y PDFs
    with console.status("[bold green]Estimando calificaciones y PDFs..."):
        estimacion_califs = 0
        estimacion_pdfs = 0

        for sociedad in sociedades_empresas[:3]:
            califs = scraper.extraer_calificaciones_tabla(sociedad["cuit"])
            estimacion_califs += len(califs)

            urls_vistas = set()
            for c in califs:
                clave = f"{c.get('fecha', '')}|{c.get('url_formulario', '')}"
                urls_vistas.add(clave)
            estimacion_pdfs += len(urls_vistas)

        if len(sociedades_empresas[:3]) > 0:
            avg_califs = estimacion_califs / len(sociedades_empresas[:3])
            avg_pdfs = estimacion_pdfs / len(sociedades_empresas[:3])
            total_estimado_califs = int(avg_califs * len(sociedades_empresas))
            total_estimado_pdfs = int(avg_pdfs * len(sociedades_empresas))
        else:
            total_estimado_califs = 0
            total_estimado_pdfs = 0

    # Mostrar preview
    preview_table = Table(title="Preview de Ejecución", show_header=True)
    preview_table.add_column("Métrica", style="cyan")
    preview_table.add_column("Valor", style="green")

    preview_table.add_row("Total de sociedades", str(len(sociedades_empresas)))
    preview_table.add_row("Calificaciones estimadas", f"~{total_estimado_califs}")
    preview_table.add_row("PDFs únicos a descargar", f"~{total_estimado_pdfs}")
    preview_table.add_row(
        "Tiempo estimado (scraping)",
        f"~{len(sociedades_empresas) * 2 // 60} minutos",
    )
    preview_table.add_row(
        "Tiempo estimado (PDFs)",
        f"~{total_estimado_pdfs * 3 // 60} minutos",
    )
    preview_table.add_row(
        "TOTAL ESTIMADO",
        f"~{(len(sociedades_empresas) * 2 + total_estimado_pdfs * 3) // 60} minutos",
    )
    preview_table.add_row("Espacio en disco estimado", f"~{total_estimado_pdfs * 0.5:.0f} MB")

    console.print(preview_table)
    console.print()

    # Confirmar
    if not typer.confirm("¿Desea continuar?"):
        console.print("[yellow]Operación cancelada.[/yellow]")
        raise typer.Exit()

    # Configurar estado
    modo_str = modo.value.upper()
    scraper.estado["fecha_inicio"] = datetime.now().isoformat()
    scraper.estado["modo_ejecucion"] = modo_str
    scraper.estado["total_sociedades"] = len(sociedades_empresas)
    scraper.estado["completado"] = False

    # Determinar punto de inicio (para reanudar)
    indice_inicio = 0
    if modo == ModoEjecucion.REANUDAR and scraper.estado.get("ultimo_cuit_procesado"):
        for i, soc in enumerate(sociedades_empresas):
            if soc["cuit"] == scraper.estado["ultimo_cuit_procesado"]:
                indice_inicio = i + 1
                break
        console.print(f"[blue]Reanudando desde la sociedad {indice_inicio + 1}[/blue]")

    # Crear CSV si es nueva ejecución
    if modo != ModoEjecucion.REANUDAR or not CSV_OUTPUT.exists():
        scraper.guardar_csv([], modo_append=False)
        console.print(f"[green]CSV creado: {CSV_OUTPUT}[/green]")

    # Inicializar PDF Downloader
    with console.status("[bold green]Inicializando PDF Downloader (Playwright)..."):
        try:
            pdf_downloader = PDFDownloader(str(INFORMES_DIR))
            console.print("[green]✓ PDF Downloader listo[/green]")
        except Exception as e:
            console.print(f"[red]Error inicializando PDF Downloader: {e}[/red]")
            console.print(
                "[yellow]Asegúrese de haber ejecutado: playwright install chromium[/yellow]"
            )
            raise typer.Exit(1)

    # Procesar sociedades
    console.print()
    console.rule("[bold green]Procesando Sociedades")
    console.print()

    tiempo_inicio = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Procesando 0/{len(sociedades_empresas)} sociedades...", total=None
        )

        for i, sociedad in enumerate(sociedades_empresas[indice_inicio:]):
            indice_actual = indice_inicio + i

            progress.update(
                task,
                description=f"Procesando {indice_actual + 1}/{len(sociedades_empresas)}: {sociedad['razon_social'][:40]}...",
            )

            try:
                resultados = scraper.procesar_sociedad_con_playwright(sociedad, pdf_downloader)

                if resultados:
                    scraper.guardar_csv(resultados, modo_append=True)

                scraper.estado["sociedades_procesadas"] += 1
                scraper.estado["ultimo_cuit_procesado"] = sociedad["cuit"]
                scraper.estado["ultimo_indice"] = indice_actual
                scraper.estado["sociedades_pendientes"] = (
                    len(sociedades_empresas) - indice_actual - 1
                )

                if (indice_actual + 1) % 10 == 0:
                    scraper._guardar_estado()

            except Exception as e:
                logger.error("error_processing_company", cuit=sociedad["cuit"], error=str(e))
                scraper.estado["total_errores"] += 1
                scraper.estado["errores_detalle"].append(
                    {
                        "cuit": sociedad["cuit"],
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

    # Finalizar
    tiempo_total = time.time() - tiempo_inicio
    scraper.estado["completado"] = True
    scraper._guardar_estado()

    console.print()
    console.rule("[bold green]Scraper Completado")
    console.print()

    results_table = Table(title="Resultados", show_header=True)
    results_table.add_column("Métrica", style="cyan")
    results_table.add_column("Valor", style="green")

    results_table.add_row("Sociedades procesadas", str(scraper.estado["sociedades_procesadas"]))
    results_table.add_row(
        "Calificaciones encontradas", str(scraper.estado["total_calificaciones_encontradas"])
    )
    results_table.add_row("PDFs descargados", str(scraper.estado["total_pdfs_descargados"]))
    results_table.add_row("Errores", str(scraper.estado["total_errores"]))
    results_table.add_row("Tiempo total", f"{tiempo_total / 60:.1f} minutos")
    results_table.add_row("CSV guardado en", str(CSV_OUTPUT))

    console.print(results_table)


@app.command()
def stats(
    debug: bool = typer.Option(False, "--debug", "-d", help="Habilitar modo debug"),
):
    """Muestra estadísticas del scraper."""
    configure_logging(LOGS_DIR, debug=debug)

    print_header()

    if not ESTADO_FILE.exists():
        console.print("[yellow]No hay estado guardado. Ejecute el scraper primero.[/yellow]")
        raise typer.Exit()

    scraper = CNVScraper()
    estadisticas = scraper.get_estadisticas()

    stats_table = Table(title="Estadísticas del Scraper", show_header=True)
    stats_table.add_column("Campo", style="cyan")
    stats_table.add_column("Valor", style="green")

    stats_table.add_row("Fecha de inicio", str(estadisticas["fecha_inicio"]))
    stats_table.add_row("Modo de ejecución", str(estadisticas["modo_ejecucion"]))
    stats_table.add_row("Total de sociedades", str(estadisticas["total_sociedades"]))
    stats_table.add_row("Sociedades procesadas", str(estadisticas["sociedades_procesadas"]))
    stats_table.add_row("Sociedades pendientes", str(estadisticas["sociedades_pendientes"]))
    stats_table.add_row(
        "Calificaciones encontradas", str(estadisticas["calificaciones_encontradas"])
    )
    stats_table.add_row("PDFs descargados", str(estadisticas["pdfs_descargados"]))
    stats_table.add_row("Errores", str(estadisticas["errores"]))
    stats_table.add_row(
        "Completado", "[green]Sí[/green]" if estadisticas["completado"] else "[red]No[/red]"
    )
    stats_table.add_row("Último CUIT procesado", str(estadisticas["ultimo_cuit_procesado"]))
    stats_table.add_row("CSV de salida", str(estadisticas["csv_ruta"]))

    console.print(stats_table)


@app.command()
def download(
    cuit: str = typer.Argument(..., help="CUIT de la empresa a descargar"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Habilitar modo debug"),
):
    """Descarga los PDFs de una empresa específica por CUIT."""
    configure_logging(LOGS_DIR, debug=debug)

    print_header()

    scraper = CNVScraper()

    # Buscar la sociedad en el cache
    sociedades = scraper.obtener_sociedades()
    sociedad = next((s for s in sociedades if s["cuit"] == cuit), None)

    if not sociedad:
        console.print(f"[red]No se encontró la sociedad con CUIT {cuit}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Procesando: {cuit} - {sociedad['razon_social']}[/green]")

    # Inicializar PDF Downloader
    try:
        pdf_downloader = PDFDownloader(str(INFORMES_DIR))
    except Exception as e:
        console.print(f"[red]Error inicializando PDF Downloader: {e}[/red]")
        raise typer.Exit(1)

    # Procesar
    with console.status("[bold green]Descargando PDFs..."):
        resultados = scraper.procesar_sociedad_con_playwright(sociedad, pdf_downloader)

    if resultados:
        scraper.guardar_csv(resultados, modo_append=True)
        console.print(f"[green]✓ {len(resultados)} calificaciones procesadas[/green]")
        for r in resultados:
            if r["ruta_pdf_descargado"]:
                console.print(f"  [cyan]PDF:[/cyan] {r['ruta_pdf_descargado']}")
    else:
        console.print("[yellow]No se encontraron calificaciones[/yellow]")


@app.callback()
def callback():
    """CNV Scraper - Herramienta para extraer calificaciones de riesgo."""
    pass


if __name__ == "__main__":
    app()
