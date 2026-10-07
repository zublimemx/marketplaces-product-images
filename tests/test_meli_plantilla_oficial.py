import unittest
import io
import zipfile
import xml.etree.ElementTree as ET
import base64
import hashlib
import json
import os
import re
import tempfile
from unittest.mock import patch

from scripts.meli_plantilla_oficial import OfficialTemplate, MAIN_NS, NS, export_rows
from scripts import meli_plantilla_oficial as meli
from scripts import meli_referencias
from scripts import visor_server


TEMPLATE = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "mercadolibre",
    "Publicar-10-06-04_20_10.xlsx",
)
OUTPUT = "/tmp/layout_meli_oficial_prueba.xlsx"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def workbook_metrics(path):
    with zipfile.ZipFile(path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        names, formulas, validations, merges, dimensions = [], {}, {}, {}, {}
        for sheet in wb.find("m:sheets", NS):
            name = sheet.attrib["name"]
            names.append(name)
            target = targets[sheet.attrib[f"{{{NS_REL}}}id"]]
            path_xml = target.lstrip("/") if target.startswith("/") else "xl/" + target
            path_xml = path_xml.replace("xl/xl/", "xl/")
            root = ET.fromstring(zf.read(path_xml))
            formulas[name] = {(c.attrib["r"], c.findtext("m:f", namespaces=NS))
                              for c in root.findall(".//m:c[m:f]", NS)}
            dv = root.find("m:dataValidations", NS)
            validations[name] = ET.tostring(dv, encoding="utf-8") if dv is not None else b""
            mc = root.find("m:mergeCells", NS)
            merges[name] = [c.attrib["ref"] for c in mc] if mc is not None else []
            dim = root.find("m:dimension", NS)
            dimensions[name] = dim.attrib.get("ref") if dim is not None else None
        return {"names": names, "styles": zf.read("xl/styles.xml"), "formulas": formulas,
                "validations": validations, "merges": merges, "dimensions": dimensions,
                "entries": {n: zf.read(n) for n in zf.namelist()}}


def find_value(path, sheet_name, cell_ref):
    with zipfile.ZipFile(path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in s.iter(f"{{{MAIN_NS}}}t")) for s in shared_root.findall("m:si", NS)]
        sheet = next(s for s in wb.find("m:sheets", NS) if s.attrib["name"] == sheet_name)
        target = targets[sheet.attrib[f"{{{NS_REL}}}id"]]
        path_xml = target.lstrip("/") if target.startswith("/") else "xl/" + target
        path_xml = path_xml.replace("xl/xl/", "xl/")
        root = ET.fromstring(zf.read(path_xml))
        cell = root.find(f".//m:c[@r='{cell_ref}']", NS)
        if cell is None:
            return ""
        if cell.attrib.get("t") == "inlineStr":
            return "".join(t.text or "" for t in cell.find("m:is", NS).iter(f"{{{MAIN_NS}}}t"))
        value = cell.findtext("m:v", namespaces=NS)
        if cell.attrib.get("t") == "s" and value is not None:
            return strings[int(value)]
        return value


def xml_cell_signature(root, cell_ref):
    cell = root.find(f".//m:c[@r='{cell_ref}']", NS)
    if cell is None:
        return None

    def node_signature(node):
        return (node.tag, tuple(sorted(node.attrib.items())), node.text,
                tuple(node_signature(child) for child in node), node.tail)

    return node_signature(cell)


def find_value_from_root(root, cell_ref, shared_strings=()):
    cell = root.find(f".//m:c[@r='{cell_ref}']", NS)
    if cell is None:
        return ""
    if cell.attrib.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.find("m:is", NS).iter(f"{{{MAIN_NS}}}t"))
    value = cell.findtext("m:v", namespaces=NS) or ""
    if cell.attrib.get("t") == "s" and value:
        return shared_strings[int(value)]
    return value


def shared_string_values(archive):
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
            for item in root.findall("m:si", NS)]


def remove_cell_elements(xml_bytes, cell_refs):
    spans = []
    start_tag = re.compile(rb'<(?P<name>(?:[A-Za-z_][A-Za-z0-9_.-]*:)?c)\b')
    for match in start_tag.finditer(xml_bytes):
        quote = None
        tag_end = match.start() + 1
        while tag_end < len(xml_bytes):
            char = xml_bytes[tag_end]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in (34, 39):
                quote = char
            elif char == 62:
                tag_end += 1
                break
            tag_end += 1
        opening = xml_bytes[match.start():tag_end]
        ref = re.search(rb'\br\s*=\s*(["\'])(.*?)\1', opening)
        if not ref or ref.group(2).decode("ascii") not in cell_refs:
            continue
        if opening[:-1].rstrip().endswith(b"/"):
            spans.append((match.start(), tag_end))
        else:
            closing = re.search(rb'</' + re.escape(match.group("name")) + rb'\s*>', xml_bytes[tag_end:])
            if not closing:
                raise AssertionError(f"No se encontró cierre de {ref.group(2)!r}")
            spans.append((match.start(), tag_end + closing.end()))
    result = xml_bytes
    for start, end in reversed(spans):
        result = result[:start] + result[end:]
    return result


def normalized_shared_strings_parts(xml_bytes):
    root = re.search(rb'<(?:[A-Za-z_][A-Za-z0-9_.-]*:)?sst\b[^>]*>', xml_bytes)
    close_start = xml_bytes.rfind(b"</sst>")
    if root is None or close_start < root.end():
        raise AssertionError("sharedStrings.xml no tiene una raíz sst esperada")
    attributes = re.sub(rb'\s+(?:count|uniqueCount)="\d+"', b"", root.group(0))
    return attributes, xml_bytes[root.end():close_start], xml_bytes[close_start + len(b"</sst>"):]


class OfficialTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = OfficialTemplate(path=TEMPLATE)
        with open(TEMPLATE, "rb") as fh:
            cls.operational = fh.read()

    def sample(self, category_id="MLM189058", catalog_id="MLM123456"):
        schema = self.template.by_id[category_id]
        fields = {
            "SKU": "7501234567890", "Categoría (ID)": category_id,
            "Categoría (ruta)": schema["route"], "Título": "Fórmula infantil de prueba",
            "Código universal de producto": "7501234567890", "ID de catálogo ML": catalog_id,
            "Precio [$]": 149.0, "Cantidad": 3, "Condición": "Nuevo",
            "Tipo de publicación": "Clásica", "Forma de envío": "Mercado Envíos",
            "Costo de envío": "A cargo del comprador", "Retiro en persona": "No acepto",
            "Tipo de garantía": "Sin garantía", "Marca": "Marca de prueba",
            "Fabricante / Laboratorio": "Fabricante de prueba", "Presentación": "Lata en polvo",
            "Edad / Etapa": "6 a 12 meses", "Descripción": "Descripción de prueba",
            "Imagen 1": "https://ejemplo.invalid/7501234567890_1.jpg",
            "Imagen 2": "https://ejemplo.invalid/7501234567890_2.jpg",
        }
        return {"gtin": fields["SKU"], "category_id": category_id,
                "category_route": schema["route"], "fields": fields}

    def operational_with_notice_row9(self, category_id="MLM167989"):
        schema = self.template.by_id[category_id]
        output = io.BytesIO()
        range_pattern = re.compile(r"(\$?[A-Z]+\$?)(\d+)(?::(\$?[A-Z]+\$?)(\d+))?", re.I)
        cell_ref_pattern = re.compile(r"(?<![A-Z0-9_])(\$?[A-Z]{1,3}\$?)8(?!\d)", re.I)
        with zipfile.ZipFile(io.BytesIO(self.operational)) as source, zipfile.ZipFile(
                output, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == schema["path"]:
                    root = ET.fromstring(data)
                    row8 = root.find(".//m:sheetData/m:row[@r='8']", NS)
                    for cell in list(row8):
                        row8.remove(cell)
                    notice = ET.Element(f"{{{MAIN_NS}}}c", {"r": "A8", "t": "inlineStr"})
                    inline = ET.SubElement(notice, f"{{{MAIN_NS}}}is")
                    ET.SubElement(inline, f"{{{MAIN_NS}}}t").text = (
                        "Revisa las condiciones de venta que completamos por ti, a partir de tus publicaciones anteriores.")
                    row8.append(notice)

                    def shift_range(value):
                        updated = []
                        for area in value.split():
                            match = range_pattern.fullmatch(area)
                            if match and int(match.group(2)) == 8:
                                left, _, right, bottom = match.groups()
                                area = left + "9" + ((":" + right + bottom) if right else "")
                            updated.append(area)
                        return " ".join(updated)

                    for validation in root.findall("m:dataValidations/m:dataValidation", NS):
                        validation.set("sqref", shift_range(validation.attrib.get("sqref", "")))
                    for formatting in root.findall("m:conditionalFormatting", NS):
                        formatting.set("sqref", shift_range(formatting.attrib.get("sqref", "")))
                        for formula in formatting.findall("m:cfRule/m:formula", NS):
                            formula.text = cell_ref_pattern.sub(r"\g<1>9", formula.text or "")
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                target.writestr(info, data)
        return output.getvalue()

    def test_detects_category_sheets_dynamically(self):
        self.assertEqual(35, len(self.template.sheets))
        self.assertEqual(35, len(self.template.by_id))
        self.assertFalse({"Ayuda", "extra info", "Legales"} & {s["name"] for s in self.template.sheets})
        self.assertEqual(8, self.template.by_id["MLM189058"]["data_start"])
        self.assertNotEqual(len(self.template.by_id["MLM189058"]["headers"]),
                            len(self.template.by_id["MLM194260"]["headers"]))

    def test_dynamic_data_start_supports_rows_8_and_9_and_preserves_notice(self):
        old_schema = self.template.by_id["MLM167989"]
        self.assertEqual(8, old_schema["data_start"])
        old_product = self.sample("MLM167989")
        old_xlsx, old_errors, old_count = self.template.export([old_product])
        self.assertEqual([], old_errors)
        self.assertEqual(1, old_count)
        old_row = old_schema["data_start"]

        updated = OfficialTemplate(content=self.operational_with_notice_row9())
        schema = updated.by_id["MLM167989"]
        self.assertEqual(9, schema["data_start"])
        currency_col = next(col for col, header in schema["headers"].items() if header == "Moneda")
        self.assertEqual("$", schema["defaults"][currency_col])

        first = self.sample("MLM167989")
        second = self.sample("MLM167989")
        second["gtin"] = second["fields"]["SKU"] = "7501234567891"
        xlsx, errors, count = updated.export([first, second])
        self.assertEqual([], errors)
        self.assertFalse(any(error["field"] == "Moneda" for error in errors))
        self.assertEqual(2, count)
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "fila_9.xlsx")
            with open(path, "wb") as fh:
                fh.write(xlsx)
            self.assertIn("Revisa las condiciones de venta", find_value(path, schema["name"], "A8"))
            sku_col = next(col for col, header in schema["headers"].items() if header == "SKU")
            currency_col = next(col for col, header in schema["headers"].items() if header == "Moneda")
            self.assertEqual("7501234567890", find_value(path, schema["name"], f"{sku_col}9"))
            self.assertEqual("7501234567891", find_value(path, schema["name"], f"{sku_col}10"))
            self.assertEqual("$", find_value(path, schema["name"], f"{currency_col}9"))
            new_values = [find_value(path, schema["name"], f"{col}9") for col in (sku_col, currency_col)]
        with tempfile.TemporaryDirectory() as temp:
            old_path = os.path.join(temp, "fila_8.xlsx")
            with open(old_path, "wb") as fh:
                fh.write(old_xlsx)
            old_values = [find_value(old_path, old_schema["name"], f"{col}{old_row}")
                          for col in (next(c for c, h in old_schema["headers"].items() if h == "SKU"),
                                      next(c for c, h in old_schema["headers"].items() if h == "Moneda"))]
        self.assertEqual(old_values, new_values)

        reference_schema = next(item for item in self.template.schema() if item["category_id"] == "MLM167989")
        operational_schema = next(item for item in updated.schema() if item["category_id"] == "MLM167989")
        self.assertEqual([], meli_referencias._differences(reference_schema, operational_schema))

    def test_inconsistent_validation_start_rows_are_rejected(self):
        content = self.operational_with_notice_row9()
        schema = self.template.by_id["MLM167989"]
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == schema["path"]:
                    root = ET.fromstring(data)
                    validation = root.find("m:dataValidations/m:dataValidation", NS)
                    validation.set("sqref", validation.attrib["sqref"].replace("9", "10", 1))
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                target.writestr(info, data)
        with self.assertRaisesRegex(ValueError, "validaciones comienzan en filas distintas"):
            OfficialTemplate(content=output.getvalue())

    def test_data_start_without_validations_or_structural_defaults_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "No se pudo determinar la primera fila"):
            self.template._detect_data_start({}, {}, [], "Hoja de prueba")

    def test_category_transformations_and_required_validation(self):
        product = self.sample()
        schema = self.template.by_id[product["category_id"]]
        mapped = self.template._mapped_values(product, schema)
        by_name = {schema["headers"][c]: v for c, v in mapped.items()}
        self.assertEqual("En polvo", by_name["Formato de la fórmula infantil"])
        self.assertEqual("Lata", by_name["Tipo de envase"])
        self.assertEqual("6", by_name["Edad mínima recomendada"])
        self.assertEqual("meses", by_name["Unidad de Edad mínima recomendada"])
        self.assertEqual("12", by_name["Edad máxima recomendada"])
        self.assertEqual("meses", by_name["Unidad de Edad máxima recomendada"])
        self.assertEqual([], self.template._validate([product])[1])

    def test_photos_are_joined_only_when_template_cell_is_editable(self):
        schema = next(s for s in self.template.sheets
                      if "Fotos" in s["headers"].values() and
                      next(c for c, h in s["headers"].items() if h == "Fotos") not in s["formula_columns"])
        product = self.sample(schema["category_id"], catalog_id="")
        mapped = self.template._mapped_values(product, schema)
        photo_col = next(c for c, h in schema["headers"].items() if h == "Fotos")
        self.assertEqual("https://ejemplo.invalid/7501234567890_1.jpg,https://ejemplo.invalid/7501234567890_2.jpg",
                         mapped[photo_col])

    def test_shipping_cost_is_normalized_in_official_xlsx_by_header(self):
        legacy = "Envío gratis (obligatorio en Mercado Libre)"
        free = self.sample()
        free["fields"].update({"Precio [$]": 399.0, "Costo de envío": legacy})
        buyer = self.sample()
        buyer["gtin"] = buyer["fields"]["SKU"] = "7501234567891"
        schema = self.template.by_id[free["category_id"]]
        column = next(col for col, header in schema["headers"].items() if header == "Costo de envío")
        xlsx, errors, count = self.template.export([free, buyer])
        self.assertEqual([], errors)
        self.assertEqual(2, count)
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "envio_oficial.xlsx")
            with open(path, "wb") as fh:
                fh.write(xlsx)
            values = [find_value(path, schema["name"], f"{column}{schema['data_start'] + offset}")
                      for offset in range(count)]
        self.assertEqual(["Ofreces envío gratis", "A cargo del comprador"], values)
        self.assertNotIn(legacy, values)
        # La misma normalización se aplica a todas las hojas que tengan ese encabezado.
        for category in self.template.sheets:
            shipping = next((col for col, header in category["headers"].items()
                             if header == "Costo de envío" and col not in category["internal"]), None)
            if shipping:
                with self.subTest(category_id=category["category_id"]):
                    mapped = self.template._mapped_values(free, category)
                    self.assertEqual("Ofreces envío gratis", mapped[shipping])

    def test_numeric_validations_write_numbers_and_identifiers_stay_text(self):
        product = self.sample()
        product["fields"].update({"Edad / Etapa": "2 a 6 meses", "Cantidad": "3", "Precio [$]": "149.50",
                                  "SKU": "0001234567890", "Código universal de producto": "0001234567890",
                                  "ID de catálogo ML": "", "Imagen 1": "", "Imagen 2": ""})
        schema = self.template.by_id[product["category_id"]]
        xlsx, errors, count = self.template.export([product])
        self.assertEqual([], errors)
        self.assertEqual(1, count)
        with zipfile.ZipFile(io.BytesIO(xlsx)) as zf:
            root = ET.fromstring(zf.read(schema["path"]))
            strings = shared_string_values(zf)
        for header, expected in (("Edad mínima recomendada", "2"), ("Edad máxima recomendada", "6"),
                                 ("Stock", "3"), ("Precio", "149.50")):
            col = next(c for c, h in schema["headers"].items() if h == header)
            with self.subTest(header=header, cell=f"{col}8"):
                cell = root.find(f".//m:c[@r='{col}8']", NS)
                self.assertNotIn("t", cell.attrib)
                self.assertIsNone(cell.find("m:is", NS))
                self.assertEqual(expected, cell.findtext("m:v", namespaces=NS))
        self.assertEqual("6", root.findtext(".//m:c[@r='AJ8']/m:v", namespaces=NS))
        self.assertEqual("2", root.findtext(".//m:c[@r='AD8']/m:v", namespaces=NS))
        for header in ("SKU", "Código universal de producto"):
            col = next(c for c, h in schema["headers"].items() if h == header)
            cell = root.find(f".//m:c[@r='{col}8']", NS)
            self.assertEqual("s", cell.attrib["t"])
            self.assertEqual("0001234567890", strings[int(cell.findtext("m:v", namespaces=NS))])

    def test_numeric_conversion_respects_validation_ranges_and_safe_content(self):
        schema = {"validations": [{"type": "whole", "sqref": "B8:B10 D8:E9"},
                                  {"type": "decimal", "sqref": "$C$8:$C$10"}]}
        self.assertEqual("whole", self.template._numeric_validation(schema, "E", 9))
        self.assertIsNone(self.template._numeric_validation(schema, "B", 11))
        for value, numeric_type, expected_type in (("6", "whole", "n"), ("6.5", "whole", "s"),
                                                   ("6.5", "decimal", "n"), ("NaN", "decimal", "s"),
                                                   ("1,000", "decimal", "s")):
            with self.subTest(value=value, numeric_type=numeric_type):
                cell_type, _ = self.template._coerce_cell_value(value, numeric_type=numeric_type)
                self.assertEqual(expected_type, cell_type)

    def test_catalog_conditional_formatting_skips_gray_cells_but_writes_editable_fields(self):
        product = self.sample("MLM167989")
        schema = self.template.by_id["MLM167989"]
        mapped = self.template._mapped_values(product, schema)
        row_values = self.template._formula_values(schema, mapped)
        controlled = self.template._catalog_controlled_columns(schema, 8, row_values,
                                                               product["fields"]["ID de catálogo ML"])
        self.assertIn("B", controlled)   # Regla gris directa por Código de catálogo ML.
        self.assertIn("AA", controlled)  # Regla gris basada en BUYBOX_FORMULA.
        self.assertTrue(any(rule["gray"] and "ADDRESS(ROW(),1)" in rule["formula"]
                            for formatting in schema["conditional_formatting"]
                            if "B8:B1001" in formatting["sqref"] for rule in formatting["rules"]))
        self.assertTrue(all(col not in controlled for col in ("H", "I", "J")))

        with zipfile.ZipFile(io.BytesIO(self.operational)) as source:
            source_root = ET.fromstring(source.read(schema["path"]))
        xlsx, errors, count = self.template.export([product])
        self.assertEqual([], errors)
        self.assertEqual(1, count)
        with zipfile.ZipFile(io.BytesIO(xlsx)) as output:
            output_root = ET.fromstring(output.read(schema["path"]))
            strings = shared_string_values(output)
        for col in controlled:
            with self.subTest(controlled_cell=f"{col}8"):
                self.assertEqual(xml_cell_signature(source_root, f"{col}8"),
                                 xml_cell_signature(output_root, f"{col}8"))
        self.assertEqual("7501234567890", find_value_from_root(output_root, "H8", strings))
        self.assertEqual("3", find_value_from_root(output_root, "I8"))
        self.assertEqual("149.0", find_value_from_root(output_root, "J8"))

    def test_required_gray_catalog_fields_do_not_raise_missing_value_errors(self):
        product = self.sample("MLM167989")
        product["fields"].update({"Título": "", "Marca": ""})
        _, errors = self.template._validate([product])
        fields = [error["field"] for error in errors if "obligatorio" in error["message"].casefold()]
        self.assertFalse(any(field.startswith("Título:") for field in fields))
        self.assertNotIn("Marca", fields)

    def test_products_without_catalog_code_do_not_apply_catalog_gray_rules(self):
        product = self.sample("MLM167989", catalog_id="")
        product["fields"].update({"Título": "Producto editable sin catálogo", "Imagen 1": "", "Imagen 2": ""})
        schema = self.template.by_id["MLM167989"]
        mapped = self.template._mapped_values(product, schema)
        controlled = self.template._catalog_controlled_columns(schema, 8, self.template._formula_values(schema, mapped), "")
        self.assertEqual(set(), controlled)
        xlsx, errors, count = self.template.export([product])
        self.assertEqual([], errors)
        self.assertEqual(1, count)
        with zipfile.ZipFile(io.BytesIO(xlsx)) as output:
            root = ET.fromstring(output.read(schema["path"]))
            strings = shared_string_values(output)
        self.assertEqual("Producto editable sin catálogo", find_value_from_root(root, "B8", strings))

    def test_buybox_formula_is_resolved_by_header_across_different_category_columns(self):
        columns = []
        for category_id in ("MLM167989", "MLM189058"):
            schema = self.template.by_id[category_id]
            buybox_col = next(col for col, header in schema["headers"].items() if header == "BUYBOX_FORMULA")
            columns.append(buybox_col)
            product = self.sample(category_id)
            mapped = self.template._mapped_values(product, schema)
            values = self.template._formula_values(schema, mapped)
            formula_targets = set()
            for formatting in schema["conditional_formatting"]:
                for rule in formatting["rules"]:
                    if rule["gray"] and re.search(rf"\$?{buybox_col}\$?8\b", rule["formula"], re.I):
                        formula_targets.update(col for col in schema["headers"]
                                               if self.template._conditional_range_contains(formatting["sqref"], 8, col))
            target = next(col for col in formula_targets if col not in schema["internal"])
            self.assertTrue(self.template.is_catalog_controlled_cell(
                schema, 8, target, {"values": values, "catalog_code": "MLM123456"}))
        self.assertNotEqual(columns[0], columns[1])

    def test_catalog_controlled_formula_cell_is_preserved(self):
        schema = self.template.by_id["MLM167989"]
        source = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.operational)) as original, \
             zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as modified:
            for info in original.infolist():
                data = original.read(info.filename)
                if info.filename == schema["path"]:
                    root = ET.fromstring(data)
                    row = root.find(".//m:sheetData/m:row[@r='8']", NS)
                    cell = ET.Element(f"{{{MAIN_NS}}}c", {"r": "B8", "t": "str"})
                    ET.SubElement(cell, f"{{{MAIN_NS}}}f").text = '"Fórmula protegida"'
                    ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = "Fórmula protegida"
                    row.append(cell)
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                modified.writestr(info, data)
        template = OfficialTemplate(content=source.getvalue())
        template.by_id["MLM167989"]["internal"].discard("B")
        product = self.sample("MLM167989")
        result, errors, count = template.export([product])
        self.assertEqual([], errors)
        self.assertEqual(1, count)
        with zipfile.ZipFile(io.BytesIO(result)) as output:
            root = ET.fromstring(output.read(schema["path"]))
        cell = root.find(".//m:c[@r='B8']", NS)
        self.assertEqual('"Fórmula protegida"', cell.findtext("m:f", namespaces=NS))
        self.assertEqual("Fórmula protegida", cell.findtext("m:v", namespaces=NS))

    def test_generated_catalog_row_leaves_every_conditional_gray_cell_unchanged(self):
        product = self.sample("MLM167989")
        schema = self.template.by_id["MLM167989"]
        mapped = self.template._mapped_values(product, schema)
        controlled = self.template._catalog_controlled_columns(
            schema, 8, self.template._formula_values(schema, mapped), product["fields"]["ID de catálogo ML"])
        with zipfile.ZipFile(io.BytesIO(self.operational)) as original:
            before = ET.fromstring(original.read(schema["path"]))
        xlsx, errors, _ = self.template.export([product])
        self.assertFalse(errors)
        with zipfile.ZipFile(io.BytesIO(xlsx)) as generated:
            after = ET.fromstring(generated.read(schema["path"]))
        for col in controlled:
            self.assertEqual(xml_cell_signature(before, f"{col}8"), xml_cell_signature(after, f"{col}8"), col)

    def test_xlsx_writer_patches_only_written_cells_and_shared_strings_minimally(self):
        product = self.sample(catalog_id="")
        product["fields"].update({"Imagen 1": "", "Imagen 2": ""})
        schema = self.template.by_id[product["category_id"]]
        mapped = self.template._mapped_values(product, schema)
        row_values = self.template._formula_values(schema, mapped)
        controlled = self.template._catalog_controlled_columns(schema, 8, row_values, "")
        modified_cells = {f"{col}8" for col in mapped
                          if col not in schema["internal"] and col not in controlled}
        xlsx, errors, count = self.template.export([product])
        self.assertEqual([], errors)
        self.assertEqual(1, count)
        with zipfile.ZipFile(io.BytesIO(self.operational)) as original, \
             zipfile.ZipFile(io.BytesIO(xlsx)) as generated:
            original_sheet = original.read(schema["path"])
            generated_sheet = generated.read(schema["path"])
            self.assertEqual(remove_cell_elements(original_sheet, modified_cells),
                             remove_cell_elements(generated_sheet, modified_cells))
            self.assertEqual(original.namelist(), generated.namelist())
            for name in original.namelist():
                if name not in (schema["path"], "xl/sharedStrings.xml"):
                    self.assertEqual(original.read(name), generated.read(name), name)
            original_root, original_strings, original_tail = normalized_shared_strings_parts(
                original.read("xl/sharedStrings.xml"))
            generated_root, generated_strings, generated_tail = normalized_shared_strings_parts(
                generated.read("xl/sharedStrings.xml"))
            self.assertEqual(original_root, generated_root)
            self.assertTrue(generated_strings.startswith(original_strings))
            self.assertGreater(len(generated_strings), len(original_strings))
            self.assertEqual(original_tail, generated_tail)

    def test_formula_photos_without_catalog_id_are_controlled_errors(self):
        product = self.sample(catalog_id="")
        _, errors = self.template._validate([product])
        self.assertIn("Fotos", [e["field"] for e in errors])
        xlsx, errors, count = self.template.export([product], skip_invalid=True)
        self.assertIsNone(xlsx)
        self.assertEqual(0, count)

    def test_unavailable_category_is_reported_and_not_added(self):
        valid = self.sample()
        invalid = {"gtin": "0000000000000", "category_id": "MLM000000",
                   "category_route": "Categoría sin plantilla", "fields": {"SKU": "0000000000000"}}
        xlsx, errors, count = self.template.export([valid, invalid], skip_invalid=True)
        self.assertEqual(1, count)
        self.assertTrue(xlsx.startswith(b"PK"))
        self.assertEqual("Categoría", errors[0]["field"])
        before = workbook_metrics(TEMPLATE)
        after_path = OUTPUT
        with open(after_path, "wb") as fh:
            fh.write(xlsx)
        after = workbook_metrics(after_path)
        self.assertEqual(before["names"], after["names"])
        self.assertEqual(38, len(after["names"]))

    def test_real_xlsx_preserves_structure_and_maps_values(self):
        product = self.sample()
        product["fields"].update({"ID de catálogo ML": "", "Imagen 1": "", "Imagen 2": ""})
        columns = list(product["fields"])
        row = [product["fields"][h] for h in columns]
        xlsx, errors, count = export_rows(columns, [row], self.operational,
                                          allowed_categories={product["category_id"]}, skip_invalid=True)
        self.assertEqual([], errors)
        self.assertEqual(1, count)
        with open(OUTPUT, "wb") as fh:
            fh.write(xlsx)
        before, after = workbook_metrics(TEMPLATE), workbook_metrics(OUTPUT)
        self.assertEqual(before["names"], after["names"])
        self.assertEqual(before["styles"], after["styles"])
        self.assertEqual(before["formulas"], after["formulas"])
        self.assertEqual(before["validations"], after["validations"])
        self.assertEqual(before["merges"], after["merges"])
        self.assertEqual(before["dimensions"], after["dimensions"])
        changed_parts = {name for name in before["entries"] if before["entries"][name] != after["entries"][name]}
        self.assertEqual({self.template.by_id["MLM189058"]["path"], "xl/sharedStrings.xml"}, changed_parts)
        self.assertEqual("7501234567890", find_value(OUTPUT, "Leche para Bebés", "E8"))
        self.assertEqual("3", find_value(OUTPUT, "Leche para Bebés", "I8"))
        self.assertEqual("149.0", find_value(OUTPUT, "Leche para Bebés", "J8"))
        self.assertEqual("En polvo", find_value(OUTPUT, "Leche para Bebés", "AC8"))
        self.assertEqual("Lata", find_value(OUTPUT, "Leche para Bebés", "AH8"))
        self.assertEqual("6", find_value(OUTPUT, "Leche para Bebés", "AD8"))
        self.assertEqual("12", find_value(OUTPUT, "Leche para Bebés", "AJ8"))
        self.assertIn("xl/media/image1.png", after["entries"])
        self.assertEqual(before["entries"]["xl/styles.xml"], after["entries"]["xl/styles.xml"])

    def _one_category_workbook(self, content, category_id):
        source = OfficialTemplate(content=content)
        category = source.by_id[category_id]
        output = __import__("io").BytesIO()
        with zipfile.ZipFile(__import__("io").BytesIO(content)) as zin, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "xl/workbook.xml":
                    root = ET.fromstring(data)
                    sheets = root.find("m:sheets", NS)
                    for sheet in list(sheets):
                        if sheet.attrib["name"] != category["name"]:
                            sheets.remove(sheet)
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                elif info.filename == "xl/_rels/workbook.xml.rels":
                    # Los vínculos restantes pueden apuntar a partes conservadas sin que aparezcan como hojas.
                    pass
                zout.writestr(info, data)
        return output.getvalue()

    def test_operational_file_is_explicit_input_and_metadata_auxiliary_is_preserved(self):
        product = self.sample()
        xlsx, errors, count = export_rows(list(product["fields"]), [list(product["fields"].values())],
                                          self.operational, {product["category_id"]}, skip_invalid=True)
        self.assertEqual(1, count)
        self.assertFalse(errors)
        with zipfile.ZipFile(__import__("io").BytesIO(self.operational)) as original, zipfile.ZipFile(__import__("io").BytesIO(xlsx)) as generated:
            extra_path = dict(self.template._sheet_targets())["extra info"]
            self.assertEqual(original.read(extra_path), generated.read(extra_path))
            self.assertEqual(original.namelist(), generated.namelist())

    def test_compatible_reference_passes_and_missing_reference_is_marked(self):
        one = self._one_category_workbook(self.operational, "MLM189058")
        with tempfile.TemporaryDirectory() as temp:
            registry_path = os.path.join(temp, "registry.json")
            reference_path = os.path.join(temp, "MLM189058.xlsx")
            with open(reference_path, "wb") as fh:
                fh.write(one)
            with open(registry_path, "w", encoding="utf8") as fh:
                json.dump({"templates": [{"category_id": "MLM189058", "file": os.path.relpath(reference_path, meli_referencias.ROOT), "status": "active"}]}, fh)
            with patch.object(meli_referencias, "REGISTRY", registry_path), \
                 patch.object(meli_referencias, "MANIFEST", os.path.join(temp, "manifest-ausente.json")):
                result = meli_referencias.inspect_operational(self.operational)
            statuses = {x["category_id"]: x["status"] for x in result["categories"]}
            self.assertEqual("Plantilla compatible", statuses["MLM189058"])
            self.assertIn("Categoría sin referencia", statuses.values())
            self.assertEqual(["MLM189058"], result["supported_categories"])

    def test_list_references_shows_manifest_metadata(self):
        one = self._one_category_workbook(self.operational, "MLM189058")
        with tempfile.TemporaryDirectory() as temp:
            ref = os.path.join(temp, "MLM189058.xlsx")
            registry = os.path.join(temp, "registry.json")
            manifest = os.path.join(temp, "manifest.json")
            with open(ref, "wb") as fh:
                fh.write(one)
            with open(manifest, "w", encoding="utf8") as fh:
                json.dump({"categories": [{"id": "MLM189058", "nombre": "Leche para Bebés", "ruta": "Ruta prueba",
                                            "filename": ref, "checksum": hashlib.sha256(one).hexdigest(), "updated": "2026-10-06", "state": "active"}]}, fh)
            with patch.object(meli_referencias, "REGISTRY", registry), patch.object(meli_referencias, "MANIFEST", manifest):
                row = meli_referencias.list_references()[0]
        self.assertEqual("MLM189058", row["category_id"])
        self.assertEqual("Leche para Bebés", row["name"])
        self.assertEqual(hashlib.sha256(one).hexdigest(), row["checksum"])
        self.assertEqual("2026-10-06", row["updated_at"])
        self.assertEqual("activa", row["status"])

    def test_reference_schema_cache_hits_and_invalidates_on_all_identity_inputs(self):
        one = self._one_category_workbook(self.operational, "MLM189058")
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "MLM189058.xlsx")
            other = os.path.join(temp, "MLM189058-next.xlsx")
            with open(path, "wb") as fh:
                fh.write(one)
            with open(other, "wb") as fh:
                fh.write(one)
            checksum = hashlib.sha256(one).hexdigest()
            item = {"category_id": "MLM189058", "file": path, "sha256": checksum, "status": "active"}
            meli_referencias.clear_reference_cache()
            with patch.object(meli_referencias, "OfficialTemplate", wraps=OfficialTemplate) as parser:
                self.assertIsNotNone(meli_referencias._cached_schema(item))
                self.assertIsNotNone(meli_referencias._cached_schema(item))
                self.assertEqual(1, parser.call_count)
                self.assertEqual(1, meli_referencias.cache_info()["hits"])
                item["sha256"] = "different"
                with self.assertRaisesRegex(ValueError, "checksum"):
                    meli_referencias._cached_schema(item)
                self.assertEqual(1, parser.call_count)
                item["sha256"] = checksum
                item["file"] = other
                meli_referencias._cached_schema(item)
                self.assertEqual(2, parser.call_count)
                stat = os.stat(other)
                os.utime(other, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
                meli_referencias._cached_schema(item)
                self.assertEqual(3, parser.call_count)
                item["status"] = "inactive"
                self.assertIsNone(meli_referencias._cached_schema(item))
                self.assertEqual(3, parser.call_count)
            meli_referencias.clear_reference_cache()

    def test_layout_endpoint_reuses_operational_parser(self):
        product = self.sample()
        payload = {"operational_xlsx": base64.b64encode(self.operational).decode("ascii"),
                   "columns": list(product["fields"]), "rows": [list(product["fields"].values())]}
        validation = {"metadata": {"status": "indeterminada"}, "supported_categories": [product["category_id"]],
                      "categories": []}
        with patch.object(meli, "OfficialTemplate", wraps=OfficialTemplate) as parser, \
             patch.object(meli_referencias, "inspect_operational", return_value=validation):
            result, status = visor_server.process_payload("/api/meli/layout", payload)
        self.assertEqual(200, status)
        self.assertIsNotNone(result["xlsx"])
        self.assertEqual(1, parser.call_count)

    def test_incompatible_reference_reports_header_change(self):
        one = self._one_category_workbook(self.operational, "MLM189058")
        # Cambia el encabezado en la copia de referencia sin modificar el XLSX operativo.
        output = __import__("io").BytesIO()
        new_shared_index = len(self.template.shared)
        with zipfile.ZipFile(__import__("io").BytesIO(one)) as zin, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == self.template.by_id["MLM189058"]["path"]:
                    root = ET.fromstring(data)
                    cell = root.find(".//m:c[@r='E3']/m:v", NS)
                    cell.text = str(new_shared_index)
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                elif info.filename == "xl/sharedStrings.xml":
                    root = ET.fromstring(data)
                    item = ET.SubElement(root, f"{{{MAIN_NS}}}si")
                    ET.SubElement(item, f"{{{MAIN_NS}}}t").text = "Encabezado modificado"
                    root.set("count", str(int(root.attrib.get("count", "0")) + 1))
                    root.set("uniqueCount", str(int(root.attrib.get("uniqueCount", "0")) + 1))
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                zout.writestr(info, data)
        changed = output.getvalue()
        with tempfile.TemporaryDirectory() as temp:
            ref = os.path.join(temp, "ref.xlsx")
            reg = os.path.join(temp, "registry.json")
            with open(ref, "wb") as fh:
                fh.write(changed)
            with open(reg, "w") as fh:
                json.dump({"templates": [{"category_id": "MLM189058", "file": os.path.relpath(ref, meli_referencias.ROOT), "status": "active"}]}, fh)
            with patch.object(meli_referencias, "REGISTRY", reg):
                result = meli_referencias.inspect_operational(self.operational)
        category = next(x for x in result["categories"] if x["category_id"] == "MLM189058")
        self.assertIn("Mercado Libre modificó esta categoría respecto a la referencia", category["status"])
        self.assertTrue(any(x["type"] == "encabezado agregado" for x in category["changes"]))

    def test_replacing_reference_updates_registry_checksum_and_reports_differences(self):
        one = self._one_category_workbook(self.operational, "MLM189058")
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(meli_referencias, "REF_DIR", temp), patch.object(meli_referencias, "REGISTRY", os.path.join(temp, "registry.json")):
                request = {"xlsx": base64.b64encode(one).decode("ascii")}
                first, first_status = visor_server.process_payload("/api/meli/references", request)
                second, second_status = visor_server.process_payload("/api/meli/references", request)
                with open(meli_referencias.REGISTRY, encoding="utf8") as fh:
                    registry = json.load(fh)
            self.assertEqual(200, first_status)
            self.assertEqual(200, second_status)
            self.assertFalse(first["replaced"])
            self.assertTrue(second["replaced"])
            self.assertEqual(hashlib.sha256(one).hexdigest(), registry["templates"][0]["sha256"])

    def test_reference_replacement_persists_only_overrides_and_keeps_manifest_live(self):
        category_ids = ["MLM189058", "MLM194260", "MLM194512"]
        with tempfile.TemporaryDirectory() as temp:
            manifest_path = os.path.join(temp, "manifest.json")
            registry_path = os.path.join(temp, "registry.json")
            records = []
            category_files = {}
            for category_id in category_ids:
                content = self._one_category_workbook(self.operational, category_id)
                path = os.path.join(temp, f"{category_id}.xlsx")
                with open(path, "wb") as fh:
                    fh.write(content)
                category_files[category_id] = content
                category_schema = self.template.by_id[category_id]
                records.append({"category_id": category_id, "name": category_schema["visible_name"],
                                "route": category_schema["route"], "file": path,
                                "sha256": hashlib.sha256(content).hexdigest(),
                                "updated_at": "2026-10-01", "status": "active"})
            with open(manifest_path, "w", encoding="utf8") as fh:
                json.dump({"templates": records}, fh)
            with open(registry_path, "w", encoding="utf8") as fh:
                json.dump({"templates": []}, fh)

            with patch.object(meli_referencias, "REF_DIR", temp), \
                 patch.object(meli_referencias, "MANIFEST", manifest_path), \
                 patch.object(meli_referencias, "REGISTRY", registry_path):
                self.assertEqual(0, len(meli_referencias._registry_overrides()))
                self.assertEqual(3, len(meli_referencias._registry()["templates"]))

                meli_referencias.replace_reference(category_files["MLM189058"])
                with open(registry_path, encoding="utf8") as fh:
                    overrides = json.load(fh)["templates"]
                self.assertEqual(["MLM189058"], [item["category_id"] for item in overrides])
                effective = {item["category_id"]: item for item in meli_referencias._registry()["templates"]}
                self.assertEqual(3, len(effective))
                self.assertEqual("Leche para Bebés", effective["MLM189058"]["name"])

                records[1]["name"] = "Nombre actualizado desde el manifest"
                records[1]["updated_at"] = "2026-10-07"
                with open(manifest_path, "w", encoding="utf8") as fh:
                    json.dump({"templates": records}, fh)
                effective = {item["category_id"]: item for item in meli_referencias._registry()["templates"]}
                self.assertEqual("Nombre actualizado desde el manifest", effective["MLM194260"]["name"])
                self.assertEqual("2026-10-07", effective["MLM194260"]["updated_at"])

                meli_referencias.replace_reference(category_files["MLM194512"])
                with open(registry_path, encoding="utf8") as fh:
                    override_ids = {item["category_id"] for item in json.load(fh)["templates"]}
                self.assertEqual({"MLM189058", "MLM194512"}, override_ids)
                effective = {item["category_id"]: item for item in meli_referencias._registry()["templates"]}
                self.assertEqual(3, len(effective))
                self.assertEqual("Nombre actualizado desde el manifest", effective["MLM194260"]["name"])

    def test_expired_operational_is_detectable_and_blocks_export_endpoint_policy(self):
        template = OfficialTemplate(content=self.operational)
        self.assertEqual("2026-11-06", template.metadata["expiry"])
        expired_io = __import__("io").BytesIO()
        with zipfile.ZipFile(__import__("io").BytesIO(self.operational)) as zin:
            sheet_meta = ET.fromstring(zin.read("xl/worksheets/sheet2.xml"))
            date_index = int(sheet_meta.findtext(".//m:c[@r='B1']/m:v", namespaces=NS))
            shared = ET.fromstring(zin.read("xl/sharedStrings.xml"))
            shared.findall("m:si", NS)[date_index].find("m:t", NS).text = "2000-01-01"
            expired_shared = ET.tostring(shared, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(__import__("io").BytesIO(self.operational)) as zin, zipfile.ZipFile(expired_io, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "xl/sharedStrings.xml":
                    data = expired_shared
                zout.writestr(info, data)
        expired = OfficialTemplate(content=expired_io.getvalue())
        self.assertEqual("2000-01-01", expired.metadata["expiry"])
        self.assertEqual("vencida", expired.metadata["status"])
        with self.assertRaisesRegex(ValueError, "Descarga una nueva"):
            meli_referencias.ensure_current(expired.metadata)
        with self.assertRaisesRegex(ValueError, "Descarga una nueva"):
            meli_referencias.ensure_current({"status": "vencida", "expiry": "2000-01-01"})
        self.assertTrue(meli_referencias.ensure_current({"status": "indeterminada", "expiry": None}))
        payload = {"operational_xlsx": base64.b64encode(self.operational).decode("ascii"), "columns": [], "rows": []}
        with patch.object(meli_referencias, "inspect_operational", return_value={"metadata": {"status": "vencida"}}):
            with self.assertRaisesRegex(ValueError, "Descarga una nueva"):
                visor_server.process_payload("/api/meli/layout", payload)

    def test_categories_in_one_operational_file_are_validated_independently(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(meli_referencias, "REGISTRY", os.path.join(temp, "registry-ausente.json")), \
             patch.object(meli_referencias, "MANIFEST", os.path.join(temp, "manifest-ausente.json")):
            result = meli_referencias.inspect_operational(self.operational)
        self.assertEqual(35, len(result["categories"]))
        self.assertTrue(all(x["status"] == "Categoría sin referencia" for x in result["categories"]))
        self.assertEqual([], result["supported_categories"])

    def test_operational_metadata_is_reported_even_when_vigency_is_unknown(self):
        result = meli_referencias.inspect_operational(self.operational)
        self.assertTrue(result["metadata"]["detected"])
        self.assertEqual("vigente", result["metadata"]["status"])
        self.assertEqual("3559665083-bulk-sell-37385e35de05", result["metadata"]["batch_id"])
        self.assertEqual("22f95b16-100e-479d-be7a-823e9e89ce0f", result["metadata"]["uuid"])
        self.assertEqual(35, len(result["metadata"]["categories"]))

    def test_api_inspects_uploaded_operational_file_without_repository_master_template(self):
        payload = {"operational_xlsx": base64.b64encode(self.operational).decode("ascii")}
        result, status = visor_server.process_payload("/api/meli/inspect", payload)
        self.assertEqual(200, status)
        self.assertEqual(35, len(result["categories"]))
        self.assertEqual("2026-11-06", result["metadata"]["expiry"])


if __name__ == "__main__":
    unittest.main()
