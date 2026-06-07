"""Servicio de conexión a AFIP SDK para consultar el Padrón A5."""

import csv
import json
import time
from pathlib import Path

from afip import Afip

from ratings_afip.config import (
    AFIP_ACCESS_TOKEN,
    AFIP_CUIT,
    CERT_PATH,
    ERRORS_CSV,
    KEY_PATH,
    RAW_JSON_DIR,
    SLEEP_SECONDS,
)


def connect_afip() -> Afip:
    """Crea una instancia conectada a AFIP SDK en producción."""
    cert = CERT_PATH.read_text()
    key = KEY_PATH.read_text()
    return Afip({
        "CUIT": AFIP_CUIT,
        "cert": cert,
        "key": key,
        "access_token": AFIP_ACCESS_TOKEN,
        "production": True,
    })


def consultar_cuit(afip: Afip, cuit: int) -> dict | None:
    """Consulta un CUIT en el Padrón A5.

    Retorna None si no existe. Guarda la respuesta cruda en RAW_JSON_DIR.
    """
    response = afip.RegisterInscriptionProof.getTaxpayerDetails(cuit)

    raw_path = RAW_JSON_DIR / f"{cuit}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, default=str, ensure_ascii=False)

    return response


def procesar_lote(cuits: list[int], afip: Afip | None = None) -> dict:
    """Procesa una lista de CUITs guardando JSONs crudos y errores.

    Verifica automáticamente si ya existe el raw para no re-consultar.
    Retorna un resumen de la ejecución.
    """
    if afip is None:
        afip = connect_afip()

    errores: list[dict] = []
    total = len(cuits)
    consultados = 0
    desde_cache = 0

    for idx, cuit in enumerate(cuits, 1):
        print(f"[{idx}/{total}] {cuit} …", end=" ")

        raw_path = RAW_JSON_DIR / f"{cuit}.json"
        response = None
        from_cache = False

        if raw_path.exists():
            with open(raw_path, "r", encoding="utf-8") as f:
                response = json.load(f)
            from_cache = True
            print("(cache)", end=" ")
        else:
            try:
                response = consultar_cuit(afip, cuit)
                consultados += 1
            except Exception as exc:
                print(f"❌ Error: {exc}")
                errores.append({
                    "cuit": cuit,
                    "error": str(exc),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                time.sleep(SLEEP_SECONDS)
                continue

        if response is None:
            print("⚠️ No encontrado")
            errores.append({
                "cuit": cuit,
                "error": "No encontrado en padrón (null)",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            time.sleep(SLEEP_SECONDS)
            continue

        if from_cache:
            desde_cache += 1
        print("✅ Guardado")

        if not from_cache and idx < total:
            time.sleep(SLEEP_SECONDS)

    # Acumular errores (append)
    Path(ERRORS_CSV).parent.mkdir(parents=True, exist_ok=True)
    if Path(ERRORS_CSV).exists():
        with open(ERRORS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existentes = list(reader)
    else:
        existentes = []

    existentes.extend(errores)
    with open(ERRORS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cuit", "error", "timestamp"])
        writer.writeheader()
        writer.writerows(existentes)

    return {
        "total": total,
        "consultados": consultados,
        "desde_cache": desde_cache,
        "errores": len(errores),
    }
