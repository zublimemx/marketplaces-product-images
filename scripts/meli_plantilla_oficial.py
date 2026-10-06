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
        self.gray_styles = self._gray_style_ids()
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
            data_formulas = set()
            formulas = {}
            for row_number, row_node in rows.items():
                if row_number < 8:
                    continue
                for c in row_node:
                    if c.find("m:f", NS) is not None:
                        col = _col(c.attrib["r"])
                        data_formulas.add(col)
                        formulas.setdefault(col, set()).add(c.findtext("m:f", namespaces=NS) or "")
            locked = set()
            for c in rows.get(8, []):
                if int(c.attrib.get("s", "0")) in self.gray_styles:
                    locked.add(_col(c.attrib["r"]))
            internals = {col for col, h in headers.items() if h.strip() in INTERNAL_HEADERS} | data_formulas | locked
            col_defs = root.find("m:cols", NS)
            if col_defs is not None:
                for definition in col_defs:
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
            for c in rows.get(8, []):
                col = _col(c.attrib["r"])
                value = self._cell_value(c)
                if value != "":
                    defaults[col] = value
            validations = []
            dvs = root.find("m:dataValidations", NS)
            if dvs is not None:
                for dv in dvs:
                    validations.append({"type": dv.attrib.get("type", ""), "sqref": dv.attrib.get("sqref", ""),
                                       "formula1": dv.findtext("m:formula1", namespaces=NS) or "",
                                       "formula2": dv.findtext("m:formula2", namespaces=NS) or ""})
            sheets.append({"name": name, "path": path, "route": a1, "visible_name": a2,
                           "category_id": category_id, "headers": headers, "required": required,
                           "internal": internals, "data_start": 8, "data_end": data_end,
                           "formula_columns": data_formulas, "locked_columns": locked, "defaults": defaults,
                           "validations": validations, "formulas": formulas})
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
                 "data_start": s["data_start"], "capacity": s["data_end"] - s["data_start"] + 1,
                 "formula_columns": sorted(s["formula_columns"], key=_col_index),
                 "internal_columns": sorted(s["internal"], key=_col_index), "validations": s["validations"],
                 "formulas": {k: sorted(v) for k, v in s["formulas"].items()}}
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
            for col in schema["required"]:
                if col in schema["internal"]:
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
            prepared.setdefault(schema["name"], []).append((p, schema, mapped))
        for name, rows in prepared.items():
            schema = rows[0][1]
            capacity = schema["data_end"] - schema["data_start"] + 1
            for p, _, _ in rows[capacity:]:
                errors.append({"gtin": p.get("gtin", ""), "category": schema["visible_name"], "field": "Capacidad",
                               "message": f"La hoja admite {capacity} productos por archivo."})
        return prepared, errors

    @staticmethod
    def _set_cell(row, col, row_number, value):
        ref = f"{col}{row_number}"
        cell = next((c for c in row if c.attrib.get("r") == ref), None)
        if cell is None:
            cell = ET.Element(f"{{{MAIN_NS}}}c", {"r": ref})
            index = 0
            for i, existing in enumerate(row):
                if _col(existing.attrib.get("r", "")) and _col_index(_col(existing.attrib["r"])) > _col_index(col):
                    index = i
                    break
                index = i + 1
            row.insert(index, cell)
        if cell.find("m:f", NS) is not None:
            raise ValueError(f"Intento de sobrescribir fórmula en {ref}")
        for child in list(cell):
            if child.tag in (f"{{{MAIN_NS}}}v", f"{{{MAIN_NS}}}is", f"{{{MAIN_NS}}}f"):
                cell.remove(child)
        if isinstance(value, bool):
            cell.set("t", "b")
            ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = "1" if value else "0"
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            cell.attrib.pop("t", None)
            ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = str(value)
        else:
            cell.set("t", "inlineStr")
            inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
            text = ET.SubElement(inline, f"{{{MAIN_NS}}}t")
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            text.text = str(value)

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
        for name, product_rows in prepared.items():
            schema = product_rows[0][1]
            root = self._xml(schema["path"])
            sheet_data = root.find("m:sheetData", NS)
            rows = {int(r.attrib["r"]): r for r in sheet_data.findall("m:row", NS)}
            for offset, (product, _, values) in enumerate(product_rows):
                row_number = schema["data_start"] + offset
                row = rows.get(row_number)
                if row is None:
                    raise ValueError(f"La plantilla no tiene preparada la fila {row_number} de {name}")
                for col, value in values.items():
                    if col in schema["internal"]:
                        continue
                    self._set_cell(row, col, row_number, value)
            modified[schema["path"]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
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
