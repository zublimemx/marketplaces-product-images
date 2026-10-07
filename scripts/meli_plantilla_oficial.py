#!/usr/bin/env python3
"""Inspecciona y rellena la plantilla XLSX oficial de Mercado Libre sin reconstruirla."""
import csv
import hashlib
import io
import json
import math
import os
import posixpath
import re
import datetime
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATEGORIES = os.path.join(ROOT, "reference", "mercadolibre", "categorias_mlm_hojas_publicables.csv")
TRANSFORMS = os.path.join(ROOT, "config", "mercadolibre_plantilla.json")
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": DOC_REL_NS}
ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", DOC_REL_NS)

INTERNAL_HEADERS = {"BUYBOX_FORMULA", "HIDDEN_PICTURES"}
HEADER_ALIASES = {
    "Código de catálogo ML": ("ID de catálogo ML",),
    "Stock": ("Cantidad",),
    "Precio": ("Precio [$]",),
    "Fabricante": ("Fabricante / Laboratorio",),
    "Laboratorio": ("Fabricante / Laboratorio",),
    "Modelo": ("Variante / Modelo",),
}
PLACEHOLDERS = {"seleccionar", "escribe o elige un valor", "elige un valor"}
VALUE_ALIASES = {
    "Costo de envío": {
        "Envío gratis (obligatorio en Mercado Libre)": "Ofreces envío gratis",
    },
}


def _col(ref):
    return "".join(ch for ch in ref if ch.isalpha())


def _row(ref):
    return int("".join(ch for ch in ref if ch.isdigit()))


def _col_index(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch.upper()) - 64
    return n


def _text(node):
    return "".join(t.text or "" for t in node.iter(f"{{{MAIN_NS}}}t"))


class _FormulaParser:
    """Evalúa el subconjunto de fórmulas Excel usado por las plantillas oficiales."""
    TOKEN = re.compile(r'\s*(?:(\$?[A-Z]{1,3}\$?\d+)|("(?:[^"]|"")*")|(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_.]*)|(<>|<=|>=|[=<>+&*/-])|([(),]))', re.I)

    def __init__(self, formula, row, column, cell_value):
        self.tokens = []
        position = 0
        while position < len(formula):
            match = self.TOKEN.match(formula, position)
            if not match:
                raise ValueError(f"Fórmula condicional no compatible: {formula}")
            position = match.end()
            reference, string, number, identifier, operator, punctuation = match.groups()
            if reference:
                self.tokens.append(("ref", reference))
            elif string:
                self.tokens.append(("string", string[1:-1].replace('""', '"')))
            elif number:
                self.tokens.append(("number", float(number) if "." in number else int(number)))
            elif identifier:
                self.tokens.append(("identifier", identifier.upper()))
            else:
                self.tokens.append(("symbol", operator or punctuation))
        self.position = 0
        self.row = row
        self.column = column
        self.cell_value = cell_value

    def _peek(self, value=None):
        if self.position >= len(self.tokens):
            return False if value is not None else None
        token = self.tokens[self.position]
        return token[1] == value if value is not None else token

    def _take(self, value=None):
        token = self._peek()
        if token is None or (value is not None and token[1] != value):
            raise ValueError("Fórmula condicional incompleta")
        self.position += 1
        return token

    def evaluate(self):
        value = self._comparison()
        if self.position != len(self.tokens):
            raise ValueError("Fórmula condicional no compatible")
        return value

    def _comparison(self):
        value = self._concatenation()
        while self._peek() and self._peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            operator = self._take()[1]
            right = self._concatenation()
            left_cmp, right_cmp = value, right
            if isinstance(left_cmp, str) and isinstance(right_cmp, str):
                left_cmp, right_cmp = left_cmp.casefold(), right_cmp.casefold()
            elif isinstance(left_cmp, bool) or isinstance(right_cmp, bool):
                left_cmp, right_cmp = bool(left_cmp), bool(right_cmp)
            try:
                value = {"=": lambda: left_cmp == right_cmp, "<>": lambda: left_cmp != right_cmp,
                         "<": lambda: left_cmp < right_cmp, ">": lambda: left_cmp > right_cmp,
                         "<=": lambda: left_cmp <= right_cmp, ">=": lambda: left_cmp >= right_cmp}[operator]()
            except TypeError:
                value = False
        return value

    def _concatenation(self):
        value = self._addition()
        while self._peek("&"):
            self._take("&")
            value = str(value or "") + str(self._addition() or "")
        return value

    def _addition(self):
        value = self._primary()
        while self._peek() and self._peek()[1] in ("+", "-"):
            operator = self._take()[1]
            right = self._primary()
            value = value + right if operator == "+" else value - right
        return value

    def _primary(self):
        token = self._take()
        kind, value = token
        if kind == "symbol" and value == "(":
            result = self._comparison()
            self._take(")")
            return result
        if kind in ("string", "number"):
            return value
        if kind == "ref":
            return self.cell_value(_col(value))
        if kind != "identifier":
            raise ValueError("Fórmula condicional no compatible")
        if value in ("TRUE", "FALSE") and not self._peek("("):
            return value == "TRUE"
        if not self._peek("("):
            raise ValueError(f"Nombre de fórmula no compatible: {value}")
        self._take("(")
        args = []
        if not self._peek(")"):
            while True:
                args.append(self._comparison())
                if not self._peek(","):
                    break
                self._take(",")
        self._take(")")
        return self._function(value, args)

    def _function(self, name, args):
        if name == "ROW":
            return self.row
        if name == "COLUMN":
            return _col_index(self.column)
        if name == "ADDRESS" and len(args) >= 2:
            number = int(args[1])
            letters = ""
            while number:
                number, remainder = divmod(number - 1, 26)
                letters = chr(65 + remainder) + letters
            return f"${letters}${int(args[0])}"
        if name == "INDIRECT" and args:
            match = re.fullmatch(r"\$?([A-Z]{1,3})\$?\d+", str(args[0]), re.I)
            if not match:
                raise ValueError("Referencia INDIRECT no compatible")
            return self.cell_value(match.group(1).upper())
        if name == "TRIM" and args:
            return " ".join(str(args[0] or "").split())
        if name == "AND":
            return all(bool(value) for value in args)
        if name == "OR":
            return any(bool(value) for value in args)
        if name == "IF" and len(args) == 3:
            return args[1] if bool(args[0]) else args[2]
        if name == "LEN" and args:
            return len(str(args[0] or ""))
        if name == "ISTEXT" and args:
            return isinstance(args[0], str)
        if name == "ISNUMBER" and args:
            return isinstance(args[0], (int, float, Decimal)) and not isinstance(args[0], bool)
        raise ValueError(f"Función condicional no compatible: {name}")


class OfficialTemplate:
    def __init__(self, path=None, content=None):
        if content is None and path is None:
            raise ValueError("Se requiere una planilla XLSX proporcionada por el usuario")
        self.path = path
        self.sha256 = hashlib.sha256(content).hexdigest() if content is not None else None
        source = io.BytesIO(content) if content is not None else path
        with zipfile.ZipFile(source) as zf:
            self.parts = {info.filename: (info, zf.read(info.filename)) for info in zf.infolist()}
            self.comment = zf.comment
        self.shared = self._shared_strings()
        self.shared_string_indices = {}
        for index, value in enumerate(self.shared):
            self.shared_string_indices.setdefault(value, index)
        self.gray_styles = self._gray_style_ids()
        self.gray_dxf_ids = self._gray_differential_style_ids()
        self.routes = self._load_routes()
        self.sheets = self._read_sheets()
        self.by_id = {s["category_id"]: s for s in self.sheets if s.get("category_id")}
        self.metadata = self._operational_metadata()

    def _xml(self, name):
        return ET.fromstring(self.parts[name][1])

    def _shared_strings(self):
        if "xl/sharedStrings.xml" not in self.parts:
            return []
        root = self._xml("xl/sharedStrings.xml")
        return [_text(si) for si in root.findall("m:si", NS)]

    def _gray_style_ids(self):
        if "xl/styles.xml" not in self.parts:
            return set()
        root = self._xml("xl/styles.xml")
        fills = root.find("m:fills", NS)
        xfs = root.find("m:cellXfs", NS)
        gray_fill_ids = set()
        if fills is not None:
            for i, fill in enumerate(fills):
                pattern = fill.find("m:patternFill", NS)
                color = pattern.find("m:fgColor", NS) if pattern is not None else None
                rgb = (color.attrib.get("rgb", "") if color is not None else "")[-6:].upper()
                if pattern is not None and pattern.attrib.get("patternType") == "solid" and len(rgb) == 6:
                    try:
                        red, green, blue = (int(rgb[i:i + 2], 16) for i in (0, 2, 4))
                    except ValueError:
                        continue
                    if max(red, green, blue) - min(red, green, blue) <= 8 and min(red, green, blue) >= 185:
                        gray_fill_ids.add(i)
        if xfs is None:
            return set()
        return {i for i, xf in enumerate(xfs) if int(xf.attrib.get("fillId", 0)) in gray_fill_ids}

    def _gray_differential_style_ids(self):
        if "xl/styles.xml" not in self.parts:
            return set()
        dxfs = self._xml("xl/styles.xml").find("m:dxfs", NS)
        if dxfs is None:
            return set()
        gray_ids = set()
        for index, dxf in enumerate(dxfs):
            pattern = dxf.find("m:fill/m:patternFill", NS)
            if pattern is None or pattern.attrib.get("patternType") != "solid":
                continue
            for color in (pattern.find("m:fgColor", NS), pattern.find("m:bgColor", NS)):
                rgb = color.attrib.get("rgb", "")[-6:].upper() if color is not None else ""
                if len(rgb) != 6:
                    continue
                try:
                    red, green, blue = (int(rgb[i:i + 2], 16) for i in (0, 2, 4))
                except ValueError:
                    continue
                if max(red, green, blue) - min(red, green, blue) <= 8 and min(red, green, blue) >= 185:
                    gray_ids.add(index)
                    break
        return gray_ids

    def _load_routes(self):
        routes = {}
        with open(CATEGORIES, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                routes[row["ID"]] = row["Ruta completa"]
        return routes

    def _sheet_targets(self):
        wb = self._xml("xl/workbook.xml")
        rels = ET.fromstring(self.parts["xl/_rels/workbook.xml.rels"][1])
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        result = []
        for sheet in wb.find("m:sheets", NS):
            rel_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
            target = targets[rel_id]
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            result.append((sheet.attrib["name"], path))
        return result

    def _cell_value(self, cell):
        if cell is None or cell.find("m:f", NS) is not None:
            return ""
        if cell.attrib.get("t") == "inlineStr":
            return _text(cell.find("m:is", NS))
        v = cell.find("m:v", NS)
        if v is None or v.text is None:
            return ""
        if cell.attrib.get("t") == "s":
            try:
                return self.shared[int(v.text)]
            except (ValueError, IndexError):
                return ""
        return v.text

    def _detect_data_start(self, rows, headers, validations, category_name):
        starts = []
        for validation in validations:
            for area in validation["sqref"].split():
                match = re.fullmatch(r"\$?[A-Z]+\$?(\d+)(?::\$?[A-Z]+\$?\d+)?", area, re.I)
                if match:
                    starts.append(int(match.group(1)))
        if starts:
            distinct = sorted(set(starts))
            if len(distinct) != 1:
                raise ValueError(
                    f"No se pudo determinar la primera fila de productos de {category_name}: "
                    f"las validaciones comienzan en filas distintas ({', '.join(map(str, distinct))})."
                )
            return distinct[0]

        # Respaldo para plantillas sin validaciones: reconocer defaults de campos
        # semánticos en la primera fila que reúna varias señales independientes.
        marker_columns = {}
        for col, header in headers.items():
            canonical = self._canonical_header(header)
            if canonical in {"Condición", "Moneda", "Tipo de publicación", "Forma de envío"}:
                marker_columns[col] = canonical
        expected = {
            "Condición": {"nuevo"},
            "Moneda": {"$", "mxn"},
            "Tipo de publicación": {"clasica", "premium"},
            "Forma de envío": {"mercado envios"},
        }
        for row_number in sorted(rows):
            if row_number < 5:
                continue
            row = rows[row_number]
            signals = set()
            for col, header in marker_columns.items():
                value = self._cell_value(self._cell(row, col)).strip().casefold()
                normalized = value.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                if normalized in expected[header]:
                    signals.add(header)
            if len(signals) >= 2:
                return row_number
        raise ValueError(f"No se pudo determinar la primera fila de productos de {category_name}.")

    def _read_sheets(self):
        sheets = []
        for name, path in self._sheet_targets():
            if path not in self.parts:
                continue
            root = self._xml(path)
            rows = {int(r.attrib["r"]): r for r in root.findall("m:sheetData/m:row", NS)}
            a1 = self._cell_value(self._cell(rows.get(1), "A"))
            a2 = self._cell_value(self._cell(rows.get(2), "A"))
            row3 = rows.get(3)
            if not a1 or " > " not in a1 or not a2 or row3 is None:
                continue
            headers = {}
            for c in row3:
                value = self._cell_value(c)
                if value:
                    headers[_col(c.attrib["r"])] = value
            if not headers:
                continue
            row4 = rows.get(4)
            required = set()
            if row4 is not None:
                for c in row4:
                    if self._cell_value(c).strip().casefold() == "obligatorio":
                        required.add(_col(c.attrib["r"]))
            validations = []
            dvs = root.find("m:dataValidations", NS)
            if dvs is not None:
                for dv in dvs:
                    validations.append({"type": dv.attrib.get("type", ""), "sqref": dv.attrib.get("sqref", ""),
                                       "formula1": dv.findtext("m:formula1", namespaces=NS) or "",
                                       "formula2": dv.findtext("m:formula2", namespaces=NS) or ""})
            data_start = self._detect_data_start(rows, headers, validations, a2)
            data_formulas = set()
            formulas = {}
            formula_expressions = {}
            for row_number, row_node in rows.items():
                if row_number < data_start:
                    continue
                for c in row_node:
                    if c.find("m:f", NS) is not None:
                        col = _col(c.attrib["r"])
                        data_formulas.add(col)
                        formula = c.findtext("m:f", namespaces=NS) or ""
                        formulas.setdefault(col, set()).add(formula)
                        if row_number == data_start:
                            formula_expressions[col] = formula
            locked = set()
            for c in rows.get(data_start, []):
                if int(c.attrib.get("s", "0")) in self.gray_styles:
                    locked.add(_col(c.attrib["r"]))
            internals = {col for col, h in headers.items() if h.strip() in INTERNAL_HEADERS} | data_formulas | locked
            col_defs = root.find("m:cols", NS)
            column_styles = {}
            if col_defs is not None:
                for definition in col_defs:
                    if "style" in definition.attrib:
                        for index in range(int(definition.attrib.get("min", "1")),
                                           int(definition.attrib.get("max", definition.attrib.get("min", "1"))) + 1):
                            n, letters = index, ""
                            while n:
                                n, rem = divmod(n - 1, 26)
                                letters = chr(65 + rem) + letters
                            column_styles[letters] = int(definition.attrib["style"])
                    if definition.attrib.get("hidden") in ("1", "true"):
                        for index in range(int(definition.attrib.get("min", "1")), int(definition.attrib.get("max", "1")) + 1):
                            n, letters = index, ""
                            while n:
                                n, rem = divmod(n - 1, 26)
                                letters = chr(65 + rem) + letters
                            internals.add(letters)
            candidates = [cid for cid, route in self.routes.items() if route == a1]
            category_id = candidates[0] if len(candidates) == 1 else None
            data_end = max(rows) if rows else 7
            defaults = {}
            for c in rows.get(data_start, []):
                col = _col(c.attrib["r"])
                value = self._cell_value(c)
                if value != "":
                    defaults[col] = value
            conditional_formatting = []
            for formatting in root.findall("m:conditionalFormatting", NS):
                rules = []
                for rule in formatting.findall("m:cfRule", NS):
                    dxf_id = rule.attrib.get("dxfId")
                    try:
                        dxf_index = int(dxf_id)
                    except (TypeError, ValueError):
                        dxf_index = None
                    rules.append({"type": rule.attrib.get("type", ""), "operator": rule.attrib.get("operator", ""),
                                  "formula": rule.findtext("m:formula", namespaces=NS) or "",
                                  "dxf_id": dxf_index,
                                  "gray": dxf_index in self.gray_dxf_ids if dxf_index is not None else False})
                conditional_formatting.append({"sqref": formatting.attrib.get("sqref", ""), "rules": rules})
            sheets.append({"name": name, "path": path, "route": a1, "visible_name": a2,
                           "category_id": category_id, "headers": headers, "required": required,
                           "internal": internals, "data_start": data_start, "data_end": data_end,
                           "formula_columns": data_formulas, "locked_columns": locked, "defaults": defaults,
                           "validations": validations, "formulas": formulas,
                           "formula_expressions": formula_expressions,
                           "conditional_formatting": conditional_formatting,
                           "column_styles": column_styles})
        return sheets

    def _operational_metadata(self):
        texts = []
        texts.extend(self.shared)
        extra_cells = []
        for sheet_name, sheet_path in self._sheet_targets():
            if sheet_name.strip().casefold() == "extra info" and sheet_path in self.parts:
                root = self._xml(sheet_path)
                rows = {int(r.attrib["r"]): r for r in root.findall("m:sheetData/m:row", NS)}
                for row_no in (1,):
                    row = rows.get(row_no)
                    if row is not None:
                        for cell in row:
                            extra_cells.append((cell.attrib.get("r", ""), self._cell_value(cell)))
        for name, (_, data) in self.parts.items():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                try:
                    texts.extend(t.text or "" for t in ET.fromstring(data).iter() if t.tag.endswith("}t"))
                except ET.ParseError:
                    continue
        combined = " | ".join(texts)
        dates = re.findall(r"(?i)(?:vigencia|vencimiento|válid[oa] hasta|valida hasta)[^0-9]{0,40}(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})", combined)
        # MeLi actualmente coloca vigencia, identificador de lote y UUID en A1:C1 de "extra info".
        dates.extend(value for cell, value in extra_cells if cell[:1] == "B" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
        expiry = None
        for candidate in dates:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
                try:
                    expiry = datetime.datetime.strptime(candidate, fmt).date()
                    break
                except ValueError:
                    pass
            if expiry:
                break
        identifiers = re.findall(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", combined)
        batch_id = next((value for cell, value in extra_cells if cell == "A1" and value), None)
        return {"detected": bool(self.sheets), "expiry": expiry.isoformat() if expiry else None,
                "status": ("vencida" if expiry < datetime.date.today() else "vigente") if expiry else "indeterminada",
                "uuid": identifiers[0] if identifiers else None, "batch_id": batch_id,
                "categories": [{"category_id": s["category_id"], "name": s["visible_name"], "route": s["route"]} for s in self.sheets]}

    @staticmethod
    def _cell(row, column):
        if row is None:
            return None
        return next((c for c in row if _col(c.attrib.get("r", "")) == column), None)

    def schema(self):
        return [{"name": s["name"], "visible_name": s["visible_name"], "route": s["route"],
                 "category_id": s["category_id"], "headers": s["headers"],
                 "required": [s["headers"][c] for c in s["required"] if c in s["headers"]],
                 "data_start": s["data_start"], "data_start_row": s["data_start"],
                 "capacity": s["data_end"] - s["data_start"] + 1,
                 "formula_columns": sorted(s["formula_columns"], key=_col_index),
                 "internal_columns": sorted(s["internal"], key=_col_index), "validations": s["validations"],
                 "formulas": {k: sorted(v) for k, v in s["formulas"].items()},
                 "conditional_formatting": [{"sqref": item["sqref"],
                                              "rules": [{key: rule[key] for key in ("type", "operator", "formula", "gray")}
                                                        for rule in item["rules"]]}
                                             for item in s["conditional_formatting"]]}
                for s in self.sheets]

    def _transform_rules(self):
        if not os.path.exists(TRANSFORMS):
            return {}
        with open(TRANSFORMS, encoding="utf-8") as fh:
            return json.load(fh).get("categories", {})

    @staticmethod
    def _clean(value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _canonical_header(header):
        if header.startswith("Título:"):
            return "Título"
        return header.strip()

    def _mapped_values(self, product, schema):
        fields = product["fields"]
        headers = schema["headers"]
        result = {}
        reverse = {}
        for target, source_names in HEADER_ALIASES.items():
            reverse[target] = source_names
        for col, raw_header in headers.items():
            header = self._canonical_header(raw_header)
            if header in INTERNAL_HEADERS or col in schema["internal"]:
                continue
            if header == "Fotos":
                photos = [self._clean(fields.get(f"Imagen {i}")) for i in range(1, 7)]
                value = ",".join(str(x) for x in photos if x)
            else:
                sources = reverse.get(header, (header,))
                value = next((self._clean(fields.get(src)) for src in sources if self._clean(fields.get(src)) not in ("", None)), "")
                if header == "Línea" and not value:
                    value = self._clean(fields.get("Línea de origen"))
            if value not in ("", None):
                if isinstance(value, str):
                    value = VALUE_ALIASES.get(header, {}).get(value, value)
                result[col] = value

        rules = self._transform_rules().get(product["category_id"], {})
        source = str(self._clean(fields.get(rules.get("presentation_source", "Presentación"))))
        if rules.get("powder_can") and "lata en polvo" in source.casefold():
            for target, value in rules["powder_can"].items():
                for col, header in headers.items():
                    if self._canonical_header(header) == target and col not in schema["internal"]:
                        result[col] = value
        age = str(self._clean(fields.get(rules.get("age_source", "Edad / Etapa"))))
        if rules.get("age_range"):
            match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:a|[-–])\s*(\d+(?:[.,]\d+)?)\s*(mes(?:es)?|años?|semanas?)", age, re.I)
            if match:
                low, high, unit = match.groups()
                unit = "meses" if unit.casefold().startswith("mes") else ("años" if unit.casefold().startswith("año") or unit.casefold().startswith("ano") else "semanas")
                values = {"Edad mínima recomendada": low.replace(",", "."),
                          "Unidad de Edad mínima recomendada": unit,
                          "Edad máxima recomendada": high.replace(",", "."),
                          "Unidad de Edad máxima recomendada": unit}
                for target, value in values.items():
                    for col, header in headers.items():
                        if self._canonical_header(header) == target and col not in schema["internal"]:
                            result[col] = value
        return result

    def _template_row(self, sheet_xml, row_number):
        return next((r for r in sheet_xml.findall("m:sheetData/m:row", NS)
                     if int(r.attrib["r"]) == row_number), None)

    @staticmethod
    def _conditional_range_contains(sqref, row, column):
        for area in sqref.split():
            match = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?", area, re.I)
            if not match:
                continue
            left, top, right, bottom = match.groups()
            if (_col_index(left) <= _col_index(column) <= _col_index(right or left)
                    and int(top) <= row <= int(bottom or top)):
                return True
        return False

    def _evaluate_formula(self, formula, schema, row, column, values, stack=None):
        stack = set(stack or ())
        buybox_col = next((col for col, header in schema["headers"].items()
                           if header.strip() == "BUYBOX_FORMULA"), None)

        def cell_value(target_col):
            target_col = target_col.upper()
            expression = (schema["formula_expressions"].get(buybox_col) if target_col == buybox_col
                          else schema["formula_expressions"].get(target_col))
            if not expression or target_col in stack:
                return values.get(target_col, schema["defaults"].get(target_col, ""))
            return self._evaluate_formula(expression, schema, row, target_col, values, stack | {target_col})

        return _FormulaParser(formula, row, column, cell_value).evaluate()

    def is_catalog_controlled_cell(self, sheet, row, column, row_context):
        """Indica si una regla gris de la plantilla bloquea esta celda para un artículo con catálogo."""
        if isinstance(sheet, str):
            schema = next((item for item in self.sheets if item["name"] == sheet), None)
        else:
            schema = sheet
        if schema is None:
            return False
        values = row_context.get("values", row_context)
        catalog_code = row_context.get("catalog_code")
        if catalog_code is None:
            catalog_col = next((col for col, header in schema["headers"].items()
                                if self._canonical_header(header) == "Código de catálogo ML"), None)
            catalog_code = values.get(catalog_col, "") if catalog_col else ""
        if not str(catalog_code or "").strip():
            return False
        column = column.upper()
        for formatting in schema.get("conditional_formatting", []):
            if not self._conditional_range_contains(formatting["sqref"], row, column):
                continue
            for rule in formatting["rules"]:
                if not rule["gray"] or not rule["formula"]:
                    continue
                try:
                    active = self._evaluate_formula(rule["formula"], schema, row, column, values)
                except (ValueError, TypeError, ZeroDivisionError) as exc:
                    raise ValueError(f"No se pudo evaluar el formato condicional de {schema['visible_name']}!{column}{row}: {exc}") from exc
                if bool(active):
                    return True
        return False

    def _catalog_controlled_columns(self, schema, row, values, catalog_code):
        if not str(catalog_code or "").strip():
            return set()
        context = {"values": values, "catalog_code": catalog_code}
        candidates = set()
        for col in schema["headers"]:
            if any(rule["gray"] and self._conditional_range_contains(formatting["sqref"], row, col)
                   for formatting in schema.get("conditional_formatting", [])
                   for rule in formatting["rules"]):
                candidates.add(col)
        return {col for col in candidates if self.is_catalog_controlled_cell(schema, row, col, context)}

    @staticmethod
    def _formula_values(schema, mapped):
        values = dict(mapped)
        for col, value in schema["defaults"].items():
            values.setdefault(col, value)
        return values

    def _validate(self, products):
        errors = []
        prepared = {}
        for p in products:
            category_id = str(p.get("category_id") or "")
            route = str(p.get("category_route") or "")
            schema = self.by_id.get(category_id)
            if not schema or schema["route"] != route:
                errors.append({"gtin": p.get("gtin", ""), "category_id": category_id,
                               "category": route or category_id, "field": "Categoría",
                               "message": "La categoría no tiene una hoja oficial compatible en esta plantilla."})
                continue
            mapped = self._mapped_values(p, schema)
            photo_col = next((c for c, h in schema["headers"].items()
                              if self._canonical_header(h) == "Fotos"), None)
            photos = [p["fields"].get(f"Imagen {i}") for i in range(1, 7) if p["fields"].get(f"Imagen {i}")]
            catalog_id = p["fields"].get("ID de catálogo ML")
            if photo_col in schema["formula_columns"] and photos and not catalog_id:
                errors.append({"gtin": p.get("gtin", ""), "category_id": category_id,
                               "category": schema["visible_name"], "field": "Fotos",
                               "message": "La plantilla calcula esta columna y la hoja no ofrece una celda editable para URLs; no se modificó la fórmula."})
            offset = len(prepared.get(schema["name"], []))
            row_number = schema["data_start"] + offset
            row_values = self._formula_values(schema, mapped)
            catalog_col = next((c for c, h in schema["headers"].items()
                                if self._canonical_header(h) == "Código de catálogo ML"), None)
            catalog_code = row_values.get(catalog_col, "") if catalog_col else ""
            try:
                controlled = self._catalog_controlled_columns(schema, row_number, row_values, catalog_code)
            except ValueError as exc:
                errors.append({"gtin": p.get("gtin", ""), "category_id": category_id,
                               "category": schema["visible_name"], "field": "Formato condicional",
                               "message": str(exc)})
                continue
            for col in schema["required"]:
                if col in schema["internal"] or col in controlled:
                    continue
                value = mapped.get(col, "")
                header = self._canonical_header(schema["headers"].get(col, col))
                if value in ("", None) and header in {"Condición", "Moneda", "Formato de venta", "Tipo de publicación",
                                                       "Forma de envío", "Retiro en persona", "Tipo de garantía"}:
                    value = schema["defaults"].get(col, "")
                if value in ("", None) or (isinstance(value, str) and value.casefold() in PLACEHOLDERS):
                    errors.append({"gtin": p.get("gtin", ""), "category_id": category_id,
                                   "category": schema["visible_name"], "field": schema["headers"].get(col, col),
                                   "message": "Campo obligatorio sin valor o con selección pendiente."})
            prepared.setdefault(schema["name"], []).append((p, schema, mapped, controlled))
        for name, rows in prepared.items():
            schema = rows[0][1]
            capacity = schema["data_end"] - schema["data_start"] + 1
            for p, _, _, _ in rows[capacity:]:
                errors.append({"gtin": p.get("gtin", ""), "category": schema["visible_name"], "field": "Capacidad",
                               "message": f"La hoja admite {capacity} productos por archivo."})
        return prepared, errors

    @staticmethod
    def _numeric_validation(schema, col, row_number):
        for validation in schema["validations"]:
            if validation["type"] not in ("decimal", "whole"):
                continue
            for area in validation["sqref"].split():
                match = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?", area, re.I)
                if match:
                    left, top, right, bottom = match.groups()
                    if (_col_index(left) <= _col_index(col) <= _col_index(right or left)
                            and int(top) <= row_number <= int(bottom or top)):
                        return validation["type"]
        return None

    @staticmethod
    def _coerce_cell_value(value, numeric_type=None, force_text=False):
        if force_text:
            value = str(value)
        elif numeric_type and isinstance(value, str):
            candidate = value.strip()
            if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", candidate):
                try:
                    number = Decimal(candidate)
                    if (number.is_finite() and len(number.as_tuple().digits) <= 15
                            and (numeric_type != "whole" or number == number.to_integral_value())):
                        value = number
                except InvalidOperation:
                    pass
        if isinstance(value, bool):
            return "b", "1" if value else "0"
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            try:
                if math.isfinite(float(value)):
                    return "n", str(value)
            except (OverflowError, ValueError):
                pass
        return "s", str(value)

    @staticmethod
    def _xml_tag_end(data, start):
        quote = None
        for index in range(start + 1, len(data)):
            char = data[index]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in (34, 39):
                quote = char
            elif char == 62:
                return index + 1
        raise ValueError("Etiqueta XML incompleta")

    @staticmethod
    def _xml_attribute(tag, name):
        pattern = rb'(?<![A-Za-z0-9_.:-])' + re.escape(name) + rb'\s*=\s*(["\'])(.*?)\1'
        match = re.search(pattern, tag)
        return match.group(2) if match else None

    @classmethod
    def _set_xml_attribute(cls, tag, name, value):
        pattern = rb'(\s+)' + re.escape(name) + rb'(\s*=\s*)(["\'])(.*?)\3'
        match = re.search(pattern, tag)
        if match:
            if value is None:
                return tag[:match.start(1)] + tag[match.end():]
            return tag[:match.start(4)] + str(value).encode("ascii") + tag[match.end(4):]
        if value is None:
            return tag
        close = tag.rfind(b">")
        slash = close - 1
        while slash >= 0 and tag[slash] in b" \t\r\n":
            slash -= 1
        if slash >= 0 and tag[slash] == 47:
            insert_at = slash
        else:
            insert_at = close
        return tag[:insert_at] + b" " + name + b'="' + str(value).encode("ascii") + b'"' + tag[insert_at:]

    @classmethod
    def _xml_elements(cls, data, local_name, start=0, limit=None):
        limit = len(data) if limit is None else limit
        pattern = re.compile(rb'<(?P<name>(?:[A-Za-z_][A-Za-z0-9_.-]*:)?' +
                             re.escape(local_name.encode("ascii")) + rb')(?=[\s/>])')
        cursor = start
        while cursor < limit:
            match = pattern.search(data, cursor, limit)
            if match is None:
                return
            open_end = cls._xml_tag_end(data, match.start())
            opening_tag = data[match.start():open_end]
            qname = match.group("name")
            if opening_tag[:-1].rstrip().endswith(b"/"):
                yield match.start(), open_end, open_end, open_end, qname, opening_tag
                cursor = open_end
                continue
            closing_pattern = re.compile(rb'</' + re.escape(qname) + rb'\s*>')
            closing = closing_pattern.search(data, open_end, limit)
            if closing is None:
                raise ValueError(f"No se encontró el cierre XML de {qname.decode('ascii')}")
            yield match.start(), closing.end(), open_end, closing.start(), qname, opening_tag
            cursor = closing.end()

    @staticmethod
    def _cell_xml(qname, cell_ref, cell_type, value, style=None, opening_tag=None):
        if cell_type == "n":
            cell_type = None
        if opening_tag is None:
            attributes = f' r="{cell_ref}"'.encode("ascii")
            if style not in (None, 0):
                attributes += f' s="{style}"'.encode("ascii")
            if cell_type:
                attributes += b' t="' + cell_type.encode("ascii") + b'"'
            opening_tag = b"<" + qname + attributes + b">"
        else:
            opening_tag = OfficialTemplate._set_xml_attribute(opening_tag, b"t", cell_type)
            if style not in (None, 0) and OfficialTemplate._xml_attribute(opening_tag, b"s") is None:
                opening_tag = OfficialTemplate._set_xml_attribute(opening_tag, b"s", style)
            if opening_tag[:-1].rstrip().endswith(b"/"):
                slash = opening_tag.rfind(b"/", 0, -1)
                opening_tag = opening_tag[:slash].rstrip() + b">"
        text = str(value)
        if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
            raise ValueError(f"El valor de {cell_ref} contiene caracteres no válidos en XML")
        escaped = escape(text, {"\r": "&#13;"}).encode("utf-8")
        prefix = qname.rsplit(b":", 1)[0] + b":" if b":" in qname else b""
        value_element = b"<" + prefix + b"v>" + escaped + b"</" + prefix + b"v>"
        return opening_tag + value_element + b"</" + qname + b">"

    @classmethod
    def _patch_sheet_cells(cls, original, updates, column_styles):
        row_spans = {}
        for span in cls._xml_elements(original, "row"):
            row_no = cls._xml_attribute(span[5], b"r")
            if row_no is not None:
                row_spans[int(row_no)] = span
        patches = []
        removed_shared_refs = 0
        any_cell = next(cls._xml_elements(original, "c"), None)
        for row_no, row_updates in updates.items():
            row_span = row_spans.get(row_no)
            if row_span is None:
                raise ValueError(f"La plantilla no tiene preparada la fila {row_no}")
            row_start, row_end, row_open_end, row_close_start, row_qname, row_open = row_span
            cells = list(cls._xml_elements(original, "c", row_open_end, row_close_start))
            cells_by_ref = {cls._xml_attribute(cell[5], b"r").decode("ascii"): cell for cell in cells
                            if cls._xml_attribute(cell[5], b"r") is not None}
            pending = {}
            qname_default = cells[0][4] if cells else (any_cell[4] if any_cell else b"c")
            for col, (cell_type, value) in row_updates.items():
                ref = f"{col}{row_no}"
                existing = cells_by_ref.get(ref)
                if existing is None:
                    pending[_col_index(col)] = (col, ref, cell_type, value)
                else:
                    old_cell = original[existing[0]:existing[1]]
                    if re.search(rb'<(?:[A-Za-z_][A-Za-z0-9_.-]*:)?f(?=[\s/>])', old_cell):
                        raise ValueError(f"Intento de sobrescribir fórmula en {ref}")
                    if cls._xml_attribute(existing[5], b"t") == b"s":
                        removed_shared_refs += 1

            def inserted_xml(col, ref, cell_type, value):
                return cls._cell_xml(qname_default, ref, cell_type, value,
                                     style=column_styles.get(col))

            fragments = [original[row_start:row_open_end]]
            cursor = row_open_end
            for cell in cells:
                cell_start, cell_end, _, _, qname, opening_tag = cell
                col_ref = cls._xml_attribute(opening_tag, b"r")
                ref = col_ref.decode("ascii") if col_ref is not None else ""
                existing_col = _col_index(_col(ref)) if ref else 0
                fragments.append(original[cursor:cell_start])
                for index in sorted(key for key in pending if key < existing_col):
                    fragments.append(inserted_xml(*pending.pop(index)))
                if _col(ref) in row_updates:
                    cell_type, value = row_updates[_col(ref)]
                    fragments.append(cls._cell_xml(qname, ref, cell_type, value,
                                                   style=column_styles.get(_col(ref)), opening_tag=opening_tag))
                else:
                    fragments.append(original[cell_start:cell_end])
                cursor = cell_end
            fragments.append(original[cursor:row_close_start])
            for index in sorted(pending):
                fragments.append(inserted_xml(*pending[index]))
            if row_open[:-1].rstrip().endswith(b"/"):
                # Las filas de datos oficiales suelen existir; se cubre también una fila vacía autoconclusiva.
                slash = row_open.rfind(b"/", 0, -1)
                fragments[0] = original[row_start:row_start] + row_open[:slash].rstrip() + b">"
                fragments.append(b"</" + row_qname + b">")
            else:
                fragments.append(original[row_close_start:row_end])
            patches.append((row_start, row_end, b"".join(fragments)))
        result = original
        for start, end, replacement in sorted(patches, reverse=True):
            result = result[:start] + replacement + result[end:]
        return result, removed_shared_refs

    @classmethod
    def _patch_shared_strings(cls, original, new_values, reference_delta):
        if original is None:
            if new_values:
                raise ValueError("La plantilla oficial no contiene sharedStrings.xml para escribir textos")
            return None
        if not new_values and not reference_delta:
            return original
        root = next(cls._xml_elements(original, "sst"), None)
        if root is None or root[3] == root[2]:
            raise ValueError("No se pudo actualizar sharedStrings.xml de la plantilla oficial")
        start, end, open_end, close_start, qname, opening = root
        count = cls._xml_attribute(opening, b"count")
        unique_count = cls._xml_attribute(opening, b"uniqueCount")
        if count is not None and reference_delta:
            opening = cls._set_xml_attribute(opening, b"count", int(count) + reference_delta)
        if unique_count is not None and new_values:
            opening = cls._set_xml_attribute(opening, b"uniqueCount", int(unique_count) + len(new_values))
        prefix = qname.rsplit(b":", 1)[0] + b":" if b":" in qname else b""
        entries = []
        for value in new_values:
            text = str(value)
            if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
                raise ValueError("Una cadena contiene caracteres no válidos en XML")
            escaped = escape(text, {"\r": "&#13;"}).encode("utf-8")
            entries.append(b"<" + prefix + b"si><" + prefix +
                           b't xml:space="preserve">' + escaped + b"</" + prefix + b"t></" + prefix + b"si>")
        return (original[:start] + opening + original[open_end:close_start] + b"".join(entries) +
                original[close_start:end] + original[end:])

    def export(self, products, allow_errors=False, skip_invalid=False):
        prepared, errors = self._validate(products)
        invalid_gtins = {str(e.get("gtin")) for e in errors if e.get("gtin")}
        if errors and not allow_errors and not skip_invalid:
            return None, errors, 0
        if skip_invalid:
            prepared = {name: [item for item in items if str(item[0].get("gtin")) not in invalid_gtins]
                        for name, items in prepared.items()}
            prepared = {name: items for name, items in prepared.items() if items}
        count = sum(len(items) for items in prepared.values())
        if count == 0:
            return None, errors, 0
        modified = {}
        updates_by_sheet = {}
        schemas_by_path = {}
        shared_indices = dict(self.shared_string_indices)
        new_shared_values = []
        new_shared_references = 0
        for name, product_rows in prepared.items():
            schema = product_rows[0][1]
            sheet_updates = updates_by_sheet.setdefault(schema["path"], {})
            schemas_by_path[schema["path"]] = schema
            for offset, (product, _, values, controlled) in enumerate(product_rows):
                row_number = schema["data_start"] + offset
                row_updates = sheet_updates.setdefault(row_number, {})
                for col, value in values.items():
                    if col in schema["internal"] or col in controlled:
                        continue
                    header = self._canonical_header(schema["headers"].get(col, ""))
                    identifier = bool(re.search(r"\b(?:SKU|GTIN|EAN|UPC|ID|IDs|código|códigos|identificador)\b", header, re.I))
                    value_type, converted = self._coerce_cell_value(
                        value, numeric_type=self._numeric_validation(schema, col, row_number), force_text=identifier)
                    if value_type == "s":
                        if converted not in shared_indices:
                            shared_indices[converted] = len(self.shared) + len(new_shared_values)
                            new_shared_values.append(converted)
                        converted = str(shared_indices[converted])
                        new_shared_references += 1
                    row_updates[col] = (value_type, converted)
        removed_shared_references = 0
        for path, sheet_updates in updates_by_sheet.items():
            modified[path], removed = self._patch_sheet_cells(
                self.parts[path][1], sheet_updates, schemas_by_path[path]["column_styles"])
            removed_shared_references += removed
        shared_path = "xl/sharedStrings.xml"
        if shared_path in self.parts:
            modified[shared_path] = self._patch_shared_strings(
                self.parts[shared_path][1], new_shared_values,
                new_shared_references - removed_shared_references)
        elif new_shared_values:
            raise ValueError("La plantilla oficial no contiene sharedStrings.xml para escribir textos")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.comment = self.comment
            for name, (info, data) in self.parts.items():
                zf.writestr(info, modified.get(name, data))
        return output.getvalue(), errors, count


def export_rows(columns, rows, operational_content=None, allowed_categories=None, allow_errors=False,
                skip_invalid=False, operational_template=None):
    template = operational_template or OfficialTemplate(content=operational_content)
    products = []
    for row in rows:
        fields = dict(zip(columns, row))
        products.append({"gtin": fields.get("SKU", ""),
                         "category_id": fields.get("Categoría (ID)", ""),
                         "category_route": fields.get("Categoría (ruta)", ""),
                         "fields": fields})
    if allowed_categories is not None:
        template.by_id = {cid: schema for cid, schema in template.by_id.items() if cid in allowed_categories}
    return template.export(products, allow_errors=allow_errors, skip_invalid=skip_invalid)


if __name__ == "__main__":
    print("Proporciona una planilla XLSX operativa desde el visor para inspeccionarla.")
