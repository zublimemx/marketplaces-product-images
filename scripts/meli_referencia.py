#!/usr/bin/env python3
"""Lista o incorpora/reemplaza una plantilla técnica de referencia por categoría."""
import argparse
import json
import os

try:
    import meli_referencias
except ModuleNotFoundError:
    from scripts import meli_referencias


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", nargs="?", help="XLSX oficial individual de una categoría")
    parser.add_argument("--lista", action="store_true", help="mostrar el registro de referencias")
    parser.add_argument("--categoria", help="validar que el archivo corresponda a este ID MLM")
    args = parser.parse_args()
    if args.lista:
        print(json.dumps(meli_referencias._registry(), ensure_ascii=False, indent=2))
        return
    if not args.archivo:
        parser.error("indica un XLSX o usa --lista")
    path = os.path.abspath(args.archivo)
    with open(path, "rb") as fh:
        result = meli_referencias.replace_reference(fh.read(), args.categoria)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
