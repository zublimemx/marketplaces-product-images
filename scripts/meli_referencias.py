"""Registro y comparación de esquemas de referencia de Mercado Libre."""
import hashlib
import json
import os
import tempfile
import datetime
import threading

try:
    from meli_plantilla_oficial import OfficialTemplate
except ModuleNotFoundError:
    from scripts.meli_plantilla_oficial import OfficialTemplate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(ROOT, "reference", "mercadolibre", "templates")
REGISTRY = os.path.join(REF_DIR, "registry.json")
MANIFEST = os.path.join(REF_DIR, "manifest.json")
_SCHEMA_CACHE = {}
_CACHE_LOCK = threading.RLock()
_CACHE_STATS = {"hits": 0, "misses": 0, "parses": 0}


def _read_registry_file(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data.get("templates", data.get("categories", [])) if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = [dict(value, category_id=value.get("category_id", key)) for key, value in rows.items()]
    entries = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["category_id"] = item.get("category_id") or item.get("id") or item.get("mlm_id")
        item["file"] = (item.get("file") or item.get("filename") or item.get("archivo")
                        or item.get("reference_file") or item.get("plantilla"))
        item["sha256"] = item.get("sha256") or item.get("checksum") or item.get("hash")
        item["updated_at"] = (item.get("updated_at") or item.get("updated")
                              or item.get("fecha_actualizacion") or item.get("fecha"))
        state = item.get("status") or item.get("state") or item.get("estado")
        if state is None:
            state = "active" if item.get("active", True) else "inactive"
        item["status"] = state
        item["name"] = item.get("name") or item.get("nombre") or item.get("category_name") or ""
        item["route"] = item.get("route") or item.get("ruta") or item.get("ruta_completa") or item.get("category_path") or ""
        if item.get("category_id"):
            entries[item["category_id"]] = item
    return entries


def _registry_overrides():
    """Return only locally managed overrides, excluding manifest base entries."""
    return _read_registry_file(REGISTRY)


def _registry():
    """Return the effective view: manifest base entries overridden by registry entries."""
    merged = _read_registry_file(MANIFEST)
    merged.update(_registry_overrides())
    return {"templates": list(merged.values())}


def clear_reference_cache():
    with _CACHE_LOCK:
        _SCHEMA_CACHE.clear()
        _CACHE_STATS.update(hits=0, misses=0, parses=0)


def cache_info():
    with _CACHE_LOCK:
        return {**_CACHE_STATS, "entries": len(_SCHEMA_CACHE)}


def _reference_path(item):
    relative = item.get("file") or ""
    if os.path.isabs(relative):
        return relative
    from_root = os.path.join(ROOT, relative)
    if os.path.isfile(from_root):
        return from_root
    return os.path.join(REF_DIR, relative)


def list_references():
    result = []
    for item in _registry().get("templates", []):
        relative = item.get("file") or ""
        path = _reference_path(item)
        active = str(item.get("status", "active")).casefold() in ("active", "activo", "enabled", "true")
        exists = bool(path and os.path.isfile(path))
        state = "activa" if active and exists else ("archivo faltante" if active else "inactiva")
        checksum = item.get("sha256") or ""
        if active and exists and checksum:
            with open(path, "rb") as fh:
                actual_checksum = hashlib.sha256(fh.read()).hexdigest()
            if checksum.casefold().removeprefix("sha256:") != actual_checksum:
                state = "checksum distinto"
        result.append({"category_id": item["category_id"], "name": item.get("name") or item.get("nombre") or "",
                       "route": item.get("route") or item.get("ruta") or "", "checksum": checksum,
                       "updated_at": item.get("updated_at") or "", "status": state, "file": relative})
    return sorted(result, key=lambda x: (x.get("name", "").casefold(), x["category_id"]))


def _schema(template, category_id):
    matches = [s for s in template.schema() if s["category_id"] == category_id]
    if len(matches) != 1:
        raise ValueError("El archivo debe contener exactamente una hoja oficial identificable para esa categoría")
    return matches[0]


def _differences(old, new):
    differences = []
    if old["route"] != new["route"]:
        differences.append({"type": "ruta", "before": old["route"], "after": new["route"]})
    old_headers, new_headers = set(old["headers"].values()), set(new["headers"].values())
    differences.extend({"type": "encabezado agregado", "header": h} for h in sorted(new_headers - old_headers))
    differences.extend({"type": "encabezado eliminado", "header": h} for h in sorted(old_headers - new_headers))
    old_required, new_required = set(old["required"]), set(new["required"])
    differences.extend({"type": "campo ahora obligatorio", "header": h} for h in sorted(new_required - old_required))
    differences.extend({"type": "campo dejó de ser obligatorio", "header": h} for h in sorted(old_required - new_required))
    for key, title in (("formula_columns", "fórmula"), ("formulas", "fórmula"),
                       ("internal_columns", "columna interna"), ("validations", "validación")):
        if old.get(key) != new.get(key):
            differences.append({"type": f"cambio de {title}", "before": old.get(key), "after": new.get(key)})
    return differences


def inspect_operational(content):
    operational = content if isinstance(content, OfficialTemplate) else OfficialTemplate(content=content)
    registry = {item["category_id"]: item for item in _registry().get("templates", [])}
    results = []
    supported = set()
    for schema in operational.schema():
        item = registry.get(schema["category_id"])
        if not item or str(item.get("status", "active")).casefold() not in ("active", "activo", "enabled", "true"):
            results.append({"category_id": schema["category_id"], "name": schema["visible_name"],
                            "status": "Categoría sin referencia", "changes": []})
            continue
        try:
            ref_schema = _cached_schema(item)
        except ValueError as exc:
            results.append({"category_id": schema["category_id"], "name": schema["visible_name"],
                            "status": "Referencia inválida", "changes": [{"type": "checksum", "detail": str(exc)}]})
            continue
        if ref_schema is None:
            results.append({"category_id": schema["category_id"], "name": schema["visible_name"],
                            "status": "Categoría sin referencia", "changes": []})
            continue
        changes = _differences(ref_schema, schema)
        status = "Plantilla compatible" if not changes else "Mercado Libre modificó esta categoría respecto a la referencia"
        results.append({"category_id": schema["category_id"], "name": schema["visible_name"],
                        "status": status, "changes": changes})
        if not changes:
            supported.add(schema["category_id"])
    meta = dict(operational.metadata)
    meta["sha256"] = operational.sha256
    return {"metadata": meta, "categories": results, "supported_categories": sorted(supported)}


def _cached_schema(item):
    path = _reference_path(item)
    if not os.path.isfile(path):
        return None
    stat = os.stat(path)
    active = str(item.get("status", "active")).casefold() in ("active", "activo", "enabled", "true")
    with open(path, "rb") as fh:
        content = fh.read()
    actual_checksum = hashlib.sha256(content).hexdigest()
    expected_checksum = (item.get("sha256") or item.get("checksum") or "").casefold().removeprefix("sha256:")
    if expected_checksum and expected_checksum != actual_checksum:
        raise ValueError(f"El checksum de la referencia {item.get('category_id')} no coincide con su manifiesto")
    key = (item.get("category_id"), os.path.realpath(path), item.get("sha256") or item.get("checksum"),
           actual_checksum, stat.st_mtime_ns, stat.st_size, active)
    with _CACHE_LOCK:
        cached = _SCHEMA_CACHE.get(item["category_id"])
        if cached and cached[0] == key:
            _CACHE_STATS["hits"] += 1
            return cached[1]
    if not active:
        return None
    with _CACHE_LOCK:
        _CACHE_STATS["misses"] += 1
    template = OfficialTemplate(content=content)
    with _CACHE_LOCK:
        _CACHE_STATS["parses"] += 1
    schema = _schema(template, item["category_id"])
    with _CACHE_LOCK:
        _SCHEMA_CACHE[item["category_id"]] = (key, schema)
    return schema


def ensure_current(metadata):
    if metadata.get("status") == "vencida":
        raise ValueError("La planilla oficial está vencida. Descarga una nueva desde Mercado Libre.")
    return True


def replace_reference(content, expected_category_id=None):
    template = OfficialTemplate(content=content)
    if len(template.sheets) != 1:
        raise ValueError("La referencia individual debe contener una sola hoja de categoría")
    schema = template.schema()[0]
    category_id = schema["category_id"]
    if not category_id or (expected_category_id and expected_category_id != category_id):
        raise ValueError("No se pudo validar el ID/ruta de categoría de la referencia")
    os.makedirs(REF_DIR, exist_ok=True)
    filename = f"{category_id}.xlsx"
    destination = os.path.join(REF_DIR, filename)
    fd, temp_path = tempfile.mkstemp(prefix=".ref-", suffix=".xlsx", dir=REF_DIR)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        effective = {x["category_id"]: x for x in _registry()["templates"]}
        entry = effective.get(category_id)
        old = _cached_schema(entry) if entry else None
        new = _schema(template, category_id)
        os.replace(temp_path, destination)
        relative = os.path.relpath(destination, ROOT)
        record = {"category_id": category_id, "name": schema["visible_name"], "route": schema["route"],
                  "file": relative, "sha256": hashlib.sha256(content).hexdigest(),
                  "updated_at": datetime.date.today().isoformat(), "status": "active"}
        overrides = _registry_overrides()
        overrides[category_id] = record
        os.makedirs(os.path.dirname(REGISTRY), exist_ok=True)
        with open(REGISTRY, "w", encoding="utf-8") as fh:
            json.dump({"templates": list(overrides.values())}, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        clear_reference_cache()
        return {"template": record, "changes": _differences(old, new) if old else [], "replaced": old is not None}
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
