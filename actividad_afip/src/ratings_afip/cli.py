#!/usr/bin/env python3
"""
CLI principal con Typer para consultar actividades económicas vía AFIP SDK.
"""

import csv
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ratings_afip.config import RAW_JSON_DIR, RESULTS_CSV
from ratings_afip.services import connect_afip, procesar_lote

app = typer.Typer(help="Consulta actividades económicas de CUITs via AFIP Padrón A5")
console = Console()


def _leer_cuits_csv(path: Path) -> list[int]:
    """Lee columna 'cuit' de un CSV y devuelve lista única ordenada."""
    cuits = set()
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("cuit", "").strip()
            if raw:
                cuits.add(int(raw))
    return sorted(cuits)


def _cuits_en_raw() -> set[int]:
    """Devuelve CUITs que ya tienen archivo JSON crudo en RAW_JSON_DIR."""
    cuits = set()
    RAW_JSON_DIR.mkdir(parents=True, exist_ok=True)
    for p in RAW_JSON_DIR.glob("*.json"):
        try:
            cuits.add(int(p.stem))
        except ValueError:
            pass
    return cuits


@app.command()
def resumen(
    input_csv: Path = typer.Argument(
        ..., help="CSV de entrada con columna 'cuit'",
        exists=True, readable=True
    ),
    exportar_faltantes: Path = typer.Option(
        None, "--exportar-faltantes", "-e",
        help="Exportar CUITs faltantes a un CSV (ej: data/faltantes.csv)"
    ),
    exportar_sin_info: Path = typer.Option(
        None, "--exportar-sin-info", "-s",
        help="Exportar CUITs consultados pero sin datos (null en AFIP)"
    )
):
    """Muestra resumen de CUITs: total, ya consultados, faltantes, sin información."""
    total = _leer_cuits_csv(input_csv)
    ya = _cuits_en_raw()
    faltantes = [c for c in total if c not in ya]

    # Detectar CUITs que devolvieron null (sin info en padrón AFIP)
    sin_info: list[int] = []
    for cuit in sorted(ya):
        try:
            data = json.loads((RAW_JSON_DIR / f"{cuit}.json").read_text())
            if data is None:
                sin_info.append(cuit)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    table = Table(title=f"Resumen para {input_csv.name}")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", style="magenta")
    table.add_row("Total CUITs", str(len(total)))
    table.add_row("Ya consultados (cache)", str(len(ya)))
    table.add_row("  - Con datos válidos", str(len(ya) - len(sin_info)))
    table.add_row("  - Sin info en padrón (null)", str(len(sin_info)))
    table.add_row("Faltantes por consultar", str(len(faltantes)))
    console.print(table)

    if faltantes:
        console.print(f"\n[bold green]Para consultar los faltantes ({len(faltantes)}):[/bold green]")
        console.print(f"  uv run ratings-afip consultar {input_csv}")

        if len(faltantes) <= 20:
            console.print(f"\n[dim]CUITs faltantes:[/dim]")
            for c in faltantes:
                console.print(f"  {c}")
        else:
            for c in faltantes[:10]:
                console.print(f"  {c}")
            console.print(f"  ... y {len(faltantes) - 10} más")

        if exportar_faltantes:
            Path(exportar_faltantes).parent.mkdir(parents=True, exist_ok=True)
            with open(exportar_faltantes, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["cuit"])
                writer.writeheader()
                writer.writerows([{"cuit": c} for c in faltantes])
            console.print(f"\n[bold green]📁 Faltantes exportados a: {exportar_faltantes}[/bold green]")

    if sin_info:
        console.print(f"\n[bold yellow]CUITs consultados pero sin info en padrón ({len(sin_info)}):[/bold yellow]")
        for c in sin_info[:10]:
            console.print(f"  {c}")
        if len(sin_info) > 10:
            console.print(f"  ... y {len(sin_info) - 10} más")

        if exportar_sin_info:
            Path(exportar_sin_info).parent.mkdir(parents=True, exist_ok=True)
            with open(exportar_sin_info, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["cuit"])
                writer.writeheader()
                writer.writerows([{"cuit": c} for c in sin_info])
            console.print(f"\n[bold green]📁 Sin-info exportados a: {exportar_sin_info}[/bold green]")


@app.command()
def consultar(
    input_csv: Path = typer.Argument(
        ..., help="CSV de entrada con columna 'cuit'",
        exists=True, readable=True
    ),
    solo_faltantes: bool = typer.Option(
        True, "--solo-faltantes/--todos",
        help="Consultar solo CUITs sin datos previos (default) o forzar re-consulta"
    )
):
    """Consulta AFIP Padrón A5 para cada CUIT del CSV y guarda JSONs crudos."""
    all_cuits = _leer_cuits_csv(input_csv)
    ya = _cuits_en_raw()

    if solo_faltantes:
        cuits = [c for c in all_cuits if c not in ya]
        console.print(f"[cyan]Consultando {len(cuits)} CUITs faltantes de {len(all_cuits)} total...[/cyan]")
    else:
        cuits = all_cuits
        console.print(f"[cyan]Consultando TODOS los {len(cuits)} CUITs (forzado)...[/cyan]")

    if not cuits:
        console.print("[bold green]No hay CUITs para consultar. Todo listo.[/bold green]")
        return

    afip = connect_afip()
    resumen = procesar_lote(cuits, afip)

    console.print(f"[cyan]Resumen:[/cyan] {resumen['consultados']} consultados a AFIP, {resumen['desde_cache']} desde cache, {resumen['errores']} errores")

    console.print("[bold green]✅ Consulta finalizada. JSONs crudos y errores guardados.[/bold green]")

    if typer.confirm("¿Deseas regenerar el CSV de actividades desde el cache ahora?", default=True):
        _exportar_actividades(RESULTS_CSV)


def _exportar_actividades(output_path: Path) -> None:
    """Reconstruye CSV de actividades a partir de los archivos JSON guardados."""
    from ratings_afip.parser import parse_response

    RAW_JSON_DIR.mkdir(parents=True, exist_ok=True)
    resultados: list[dict] = []

    for p in sorted(RAW_JSON_DIR.glob("*.json")):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data is not None:
            resultados.extend(parse_response(data, int(p.stem)))

    if not resultados:
        console.print("[bold yellow]No hay archivos JSON válidos para exportar.[/bold yellow]")
        return

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "cuit_consultado", "id_actividad", "descripcion",
            "nomenclador", "orden", "periodo", "regimen", "es_actividad_principal"
        ])
        writer.writeheader()
        writer.writerows(resultados)

    console.print(f"[bold green]✅ Exportado desde cache: {output_path} ({len(resultados)} filas)[/bold green]")


@app.command()
def exportar(
    output_path: Path = typer.Option(RESULTS_CSV, "--output", "-o", help="Ruta del CSV a generar")
):
    """Reconstruye CSV de actividades a partir de los archivos JSON guardados."""
    _exportar_actividades(output_path)


if __name__ == "__main__":
    app()
