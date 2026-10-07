#!/usr/bin/env python3
"""Sirve el visor en localhost y genera el XLSX oficial de Mercado Libre."""
import json
import os
import sys
import base64
import zipfile
import datetime
import glob
import re
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

try:
    import meli_plantilla_oficial as meli
    import meli_referencias as referencias
    import meli_publicacion as publicacion
except ModuleNotFoundError:
    from scripts import meli_plantilla_oficial as meli
    from scripts import meli_referencias as referencias
    from scripts import meli_publicacion as publicacion

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLICATION_LOCK = threading.Lock()


def publication_statuses():
    """Lee el estado persistente desde products/*/product.json; los productos antiguos son no publicados."""
    result = {}
    for path in glob.glob(os.path.join(ROOT, "products", "*", "product.json")):
        gtin = os.path.basename(os.path.dirname(path))
        if not re.fullmatch(r"\d{8,14}", gtin):
            continue
        try:
            result[gtin] = _publication_record(gtin)
        except (OSError, json.JSONDecodeError):
            continue
    return result


def _publication_record(gtin):
    path = os.path.join(ROOT, "products", gtin, "product.json")
    with open(path, encoding="utf-8") as fh:
        product = json.load(fh)
    market = product.get("marketplaces", {}).get("mercadolibre", {})
    status = publicacion.status_of(market)
    return {"publication_status": status, "published_at": market.get("published_at"),
            "meli_item_id": market.get("meli_item_id")}


def publication_export_errors(columns, rows, include_published=False):
    if include_published:
        return []
    normalized_columns = [str(column).strip().casefold() for column in columns]
    gtin_index = next((normalized_columns.index(name) for name in ("sku", "gtin", "código universal de producto")
                       if name in normalized_columns), 0)
    errors = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or gtin_index >= len(row):
            continue
        gtin = str(row[gtin_index] or "")
        if not re.fullmatch(r"\d{8,14}", gtin):
            continue
        try:
            state = _publication_record(gtin)
        except (OSError, json.JSONDecodeError):
            continue
        if not publicacion.can_export(state, include_published):
            errors.append({"gtin": gtin, "field": "Estado de publicación",
                           "category": "Mercado Libre",
                           "message": "El producto ya está marcado como publicado. Activa explícitamente la inclusión de publicados para continuar."})
    return errors


def update_publication_status(payload):
    gtin = str(payload.get("gtin") or "")
    status = payload.get("publication_status")
    if not re.fullmatch(r"\d{8,14}", gtin):
        raise ValueError("El GTIN del producto no es válido")
    if status not in ("published", "not_published"):
        raise ValueError("El estado debe ser published o not_published")
    if "meli_item_id" in payload:
        item_id = payload["meli_item_id"]
        if item_id is not None and (not isinstance(item_id, str) or not re.fullmatch(r"MLM\d+", item_id)):
            raise ValueError("meli_item_id debe ser un identificador MLM o null")

    path = os.path.join(ROOT, "products", gtin, "product.json")
    with PUBLICATION_LOCK:
        with open(path, encoding="utf-8") as fh:
            product = json.load(fh)
        market = product.setdefault("marketplaces", {}).get("mercadolibre")
        if not isinstance(market, dict):
            raise ValueError("El producto no tiene una sección marketplaces.mercadolibre válida")
        market["publication_status"] = status
        if status == "published":
            market["published_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        if "meli_item_id" in payload:
            market["meli_item_id"] = payload["meli_item_id"]

        fd, temporary = tempfile.mkstemp(prefix=".product-", suffix=".json", dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(product, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {"gtin": gtin, "publication_status": market["publication_status"],
            "published_at": market.get("published_at"), "meli_item_id": market.get("meli_item_id")}, 200


def update_publication_statuses(payload):
    """Actualiza en una petición los estados de los productos seleccionados."""
    gtins = payload.get("gtins")
    status = payload.get("publication_status")
    if not isinstance(gtins, list) or not gtins:
        raise ValueError("Selecciona al menos un producto")
    if status not in ("published", "not_published"):
        raise ValueError("El estado debe ser published o not_published")

    updated, errors = [], []
    for gtin in dict.fromkeys(str(value or "") for value in gtins):
        try:
            record, _ = update_publication_status({"gtin": gtin, "publication_status": status})
            updated.append(record)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"gtin": gtin, "error": str(exc)})
    return {"updated": updated, "errors": errors}, 200


def process_get(path):
    if path == "/api/meli/publication-status":
        return {"products": publication_statuses()}, 200
    if path == "/api/meli/references":
        return {"references": referencias.list_references()}, 200
    raise ValueError("Ruta GET desconocida")


def process_payload(path, payload):
    if path == "/api/meli/publication-status":
        if "gtins" in payload:
            return update_publication_statuses(payload)
        return update_publication_status(payload)
    if path == "/api/meli/references":
        encoded_reference = payload.get("xlsx", "")
        if not encoded_reference:
            raise ValueError("Selecciona un XLSX individual de referencia")
        content = base64.b64decode(encoded_reference, validate=True)
        return referencias.replace_reference(content, payload.get("category_id") or None), 200
    encoded = payload.get("operational_xlsx", "")
    if not encoded:
        raise ValueError("Selecciona la planilla operativa descargada de Mercado Libre")
    if path == "/api/meli/layout":
        if not isinstance(payload.get("columns"), list) or not isinstance(payload.get("rows"), list):
            raise ValueError("Faltan columnas o productos en la solicitud")
        duplicate_errors = publication_export_errors(payload["columns"], payload["rows"],
                                                      payload.get("include_published") is True)
        if duplicate_errors:
            return {"errores": duplicate_errors, "productos_exportados": 0, "metadata": {},
                    "categories": [], "xlsx": None}, 422
    content = base64.b64decode(encoded, validate=True)
    operational = meli.OfficialTemplate(content=content)
    validation = referencias.inspect_operational(operational)
    if path == "/api/meli/inspect":
        return validation, 200
    referencias.ensure_current(validation["metadata"])
    if not isinstance(payload.get("columns"), list) or not isinstance(payload.get("rows"), list):
        raise ValueError("Faltan columnas o productos en la solicitud")
    xlsx, errors, count = meli.export_rows(payload["columns"], payload["rows"],
                                          allowed_categories=set(validation["supported_categories"]),
                                          skip_invalid=True, operational_template=operational)
    return {"errores": errors, "productos_exportados": count, "metadata": validation["metadata"],
            "categories": validation["categories"],
            "xlsx": base64.b64encode(xlsx).decode("ascii") if xlsx is not None else None}, (200 if xlsx else 422)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        if self.path in ("/api/meli", "/api/meli/"):
            payload = {"servicio": "Mercado Libre", "estado": "activo",
                       "endpoints": {"GET": ["/api/meli/references", "/api/meli/publication-status"],
                                     "POST": ["/api/meli/inspect", "/api/meli/layout", "/api/meli/references",
                                              "/api/meli/publication-status"]}}
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/meli/references":
            body = json.dumps({"references": referencias.list_references()}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/meli/publication-status":
            payload, status = process_get(self.path)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        if self.path not in ("/api/meli/layout", "/api/meli/inspect", "/api/meli/references",
                             "/api/meli/publication-status"):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 40_000_000:
                self.send_error(413, "Tamaño de solicitud inválido")
                return
            payload = json.loads(self.rfile.read(size))
            result, status = process_payload(self.path, payload)
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, KeyError, json.JSONDecodeError, base64.binascii.Error, zipfile.BadZipFile) as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:  # el visor debe recibir un error controlado
            body = json.dumps({"error": f"No se pudo generar el XLSX: {exc}"}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main():
    host, port = "127.0.0.1", int(os.environ.get("VISOR_PORT", "8765"))
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        sys.exit(f"No se pudo iniciar el servidor local: {exc}")
    print(f"Visor: http://{host}:{port}/visor/")
    print("Generador oficial de Mercado Libre activo. Presiona Ctrl+C para salir.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
