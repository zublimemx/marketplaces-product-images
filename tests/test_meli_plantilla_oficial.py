import unittest
import zipfile
import xml.etree.ElementTree as ET
import base64
import hashlib
import json
import os
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

    def test_detects_category_sheets_dynamically(self):
        self.assertEqual(35, len(self.template.sheets))
        self.assertEqual(35, len(self.template.by_id))
        self.assertFalse({"Ayuda", "extra info", "Legales"} & {s["name"] for s in self.template.sheets})
        self.assertEqual(8, self.template.by_id["MLM189058"]["data_start"])
        self.assertNotEqual(len(self.template.by_id["MLM189058"]["headers"]),
                            len(self.template.by_id["MLM194260"]["headers"]))

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
        self.assertEqual({self.template.by_id["MLM189058"]["path"]}, changed_parts)
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
            with patch.object(meli_referencias, "REGISTRY", registry_path):
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
        with patch.object(meli_referencias, "REGISTRY", "/tmp/meli-registry-no-existe.json"):
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
