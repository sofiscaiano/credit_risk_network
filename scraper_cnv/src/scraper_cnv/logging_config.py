"""Configuración de logging con structlog."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from structlog.stdlib import LoggerFactory
from structlog.processors import JSONRenderer, TimeStamper


def configure_logging(logs_dir: Path, debug: bool = False) -> None:
    """Configura structlog con los procesadores apropiados.

    Args:
        logs_dir: Directorio donde guardar los logs
        debug: Si es True, usa nivel DEBUG y salida pretty; si es False, usa INFO y JSON
    """
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Configurar logging estándar primero
    level = logging.DEBUG if debug else logging.INFO
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = logs_dir / f"scraper_{timestamp}.log"

    # Handlers
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Configurar logging estándar
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[file_handler, console_handler],
        force=True,
    )

    # Procesadores compartidos
    shared_processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        TimeStamper(fmt="iso"),
    ]

    if debug:
        # Modo desarrollo: pretty console
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # Modo producción: JSON
        processors = shared_processors + [structlog.processors.dict_tracebacks, JSONRenderer()]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "scraper_cnv") -> structlog.stdlib.BoundLogger:
    """Obtiene un logger configurado con structlog.

    Args:
        name: Nombre del logger

    Returns:
        BoundLogger configurado
    """
    return structlog.get_logger(name)
