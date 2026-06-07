"""Modelos Pydantic para datos del Padrón A5."""

from pydantic import BaseModel


class Actividad(BaseModel):
    """Actividad económica de un contribuyente."""

    cuit_consultado: int
    id_actividad: str
    descripcion: str
    nomenclador: int | str = ""
    orden: int | str = ""
    periodo: int | str = ""
    regimen: str = ""  # "Régimen General" o "Monotributo"
    es_actividad_principal: int = 0  # 1 = principal, 0 = secundaria
