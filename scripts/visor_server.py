#!/usr/bin/env python3
"""Sirve el visor en localhost y genera el XLSX oficial de Mercado Libre."""
import json
import os
import sys
import base64
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

try:
    import meli_plantilla_oficial as meli
    import meli_referencias as referencias
except ModuleNotFoundError:
    from scripts import meli_plantilla_oficial as meli
    from scripts import meli_referencias as referencias

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def process_payload(path, payload):
    if path == "/api/meli/references":
        encoded_reference = payload.get("xlsx", "")
        if not encoded_reference:
            raise ValueError("Selecciona un XLSX individual de referencia")
        content = base64.b64decode(encoded_reference, validate=True)
        return referencias.replace_reference(content, payload.get("category_id") or None), 200
    encoded = payload.get("operational_xlsx", "")
    if not encoded:
        raise ValueError("Selecciona la planilla operativa descargada de Mercado Libre")
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
                       "endpoints": {"GET": ["/api/meli/references"],
                                     "POST": ["/api/meli/inspect", "/api/meli/layout", "/api/meli/references"]}}
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
        super().do_GET()

    def do_POST(self):
        if self.path not in ("/api/meli/layout", "/api/meli/inspect", "/api/meli/references"):
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
