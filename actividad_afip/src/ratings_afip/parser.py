"""Parser para extraer actividades del Padrón A5 (ws_sr_constancia_inscripcion)."""

from ratings_afip.models import Actividad


def _es_principal(act: dict) -> bool:
    """Devuelve True si la actividad es la principal según AFIP (orden == 1)."""
    orden = act.get("orden")
    if orden is None:
        return False
    return str(orden).strip() == "1"


def _parse_single_activity(
    act: dict, *, is_main: bool, regimen_name: str, cuit: int
) -> Actividad | None:
    """Convierte un objeto de actividad de AFIP en modelo interno."""
    act_id = act.get("idActividad") or act.get("idActividadPrincipal")
    if not act_id:
        return None

    return Actividad(
        cuit_consultado=cuit,
        id_actividad=str(act_id).strip(),
        descripcion=(act.get("descripcionActividad") or act.get("descripcionActividadPrincipal") or "").strip(),
        nomenclador=act.get("nomenclador", ""),
        orden=act.get("orden", ""),
        periodo=act.get("periodo", ""),
        regimen=regimen_name,
        es_actividad_principal=1 if is_main else 0,
    )


def parse_response(response: dict, cuit: int) -> list[dict]:
    """Extrae TODAS las actividades del Padrón A5, marcando la principal (orden=1)."""
    activities: list[Actividad] = []
    seen_ids: set[str] = set()
    seen: set[str] = set()  # key: reg+id

    # --- Régimen General ---
    drg = response.get("datosRegimenGeneral")
    if isinstance(drg, dict):
        acts = drg.get("actividad")
        if isinstance(acts, list):
            for a in acts:
                parsed = _parse_single_activity(a, is_main=_es_principal(a), regimen_name="Régimen General", cuit=cuit)
                if parsed:
                    key = f"RG-{parsed.id_actividad}"
                    if key not in seen:
                        activities.append(parsed)
                        seen.add(key)
                        seen_ids.add(parsed.id_actividad)
        elif isinstance(acts, dict):
            parsed = _parse_single_activity(acts, is_main=_es_principal(acts), regimen_name="Régimen General", cuit=cuit)
            if parsed:
                key = f"RG-{parsed.id_actividad}"
                if key not in seen:
                    activities.append(parsed)
                    seen.add(key)

    # --- Monotributo ---
    dm = response.get("datosMonotributo")
    if isinstance(dm, dict):
        act_mon = dm.get("actividadMonotributista")
        if isinstance(act_mon, dict):
            parsed = _parse_single_activity(act_mon, is_main=_es_principal(act_mon), regimen_name="Monotributo", cuit=cuit)
            if parsed:
                key = f"M-{parsed.id_actividad}"
                if key not in seen and parsed.id_actividad not in seen_ids:
                    activities.append(parsed)
                    seen.add(key)
                    seen_ids.add(parsed.id_actividad)

        acts_mon = dm.get("actividad")
        if isinstance(acts_mon, list):
            for a in acts_mon:
                parsed = _parse_single_activity(a, is_main=_es_principal(a), regimen_name="Monotributo", cuit=cuit)
                if parsed:
                    key = f"M-{parsed.id_actividad}"
                    if key not in seen and parsed.id_actividad not in seen_ids:
                        activities.append(parsed)
                        seen.add(key)
                        seen_ids.add(parsed.id_actividad)
        elif isinstance(acts_mon, dict):
            parsed = _parse_single_activity(acts_mon, is_main=_es_principal(acts_mon), regimen_name="Monotributo", cuit=cuit)
            if parsed:
                key = f"M-{parsed.id_actividad}"
                if key not in seen and parsed.id_actividad not in seen_ids:
                    activities.append(parsed)
                    seen.add(key)
                    seen_ids.add(parsed.id_actividad)

    return [a.model_dump() for a in activities]
