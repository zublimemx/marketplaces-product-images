import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts import visor_server
from scripts import meli_publicacion as publicacion


class MeliPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.gtin = "7501234567890"
        self.product_path = os.path.join(self.root, "products", self.gtin, "product.json")
        os.makedirs(os.path.dirname(self.product_path))
        self.product = {
            "gtin": self.gtin,
            "marketplaces": {"mercadolibre": {"categoria_id": "MLM167989",
                                               "catalogo_id": "MLM17017667"}},
        }
        self._save()
        self.root_patch = patch.object(visor_server, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def _save(self):
        with open(self.product_path, "w", encoding="utf-8") as fh:
            json.dump(self.product, fh, ensure_ascii=False, indent=2)

    def _read(self):
        with open(self.product_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_legacy_product_defaults_to_not_published_without_migration(self):
        response, status = visor_server.process_get("/api/meli/publication-status")
        self.assertEqual(200, status)
        self.assertEqual("not_published", response["products"][self.gtin]["publication_status"])
        self.assertNotIn("publication_status", self._read()["marketplaces"]["mercadolibre"])
        self.assertEqual({"publication_status": "not_published", "published_at": None, "meli_item_id": None},
                         publicacion.viewer_fields(self._read()["marketplaces"]["mercadolibre"]))

    def test_mark_published_persists_and_keeps_catalog_id_independent(self):
        result, status = visor_server.process_payload("/api/meli/publication-status", {
            "gtin": self.gtin, "publication_status": "published", "meli_item_id": "MLM99887766",
        })
        self.assertEqual(200, status)
        self.assertEqual("published", result["publication_status"])
        self.assertIsNotNone(datetime.datetime.fromisoformat(result["published_at"]))
        saved = self._read()["marketplaces"]["mercadolibre"]
        self.assertEqual("MLM17017667", saved["catalogo_id"])
        self.assertEqual("MLM99887766", saved["meli_item_id"])

        reloaded, _ = visor_server.process_get("/api/meli/publication-status")
        self.assertEqual("published", reloaded["products"][self.gtin]["publication_status"])
        self.assertEqual("MLM99887766", reloaded["products"][self.gtin]["meli_item_id"])
        self.assertEqual("published", publicacion.viewer_fields(saved)["publication_status"])

    def test_unmarking_keeps_publication_history(self):
        published, _ = visor_server.process_payload("/api/meli/publication-status", {
            "gtin": self.gtin, "publication_status": "published", "meli_item_id": "MLM99887766",
        })
        result, status = visor_server.process_payload("/api/meli/publication-status", {
            "gtin": self.gtin, "publication_status": "not_published",
        })
        self.assertEqual(200, status)
        self.assertEqual("not_published", result["publication_status"])
        self.assertEqual(published["published_at"], result["published_at"])
        self.assertEqual("MLM99887766", result["meli_item_id"])
        self.assertEqual("MLM17017667", self._read()["marketplaces"]["mercadolibre"]["catalogo_id"])

    def test_bulk_marking_persists_selected_products_and_reports_invalid_gtins(self):
        second_gtin = "7501234567891"
        second_path = os.path.join(self.root, "products", second_gtin, "product.json")
        os.makedirs(os.path.dirname(second_path))
        with open(second_path, "w", encoding="utf-8") as fh:
            json.dump({"gtin": second_gtin, "marketplaces": {"mercadolibre": {"categoria_id": "MLM167989"}}}, fh)

        result, status = visor_server.process_payload("/api/meli/publication-status", {
            "gtins": [self.gtin, second_gtin, "bad-id", self.gtin],
            "publication_status": "published",
        })

        self.assertEqual(200, status)
        self.assertEqual([self.gtin, second_gtin], [item["gtin"] for item in result["updated"]])
        self.assertEqual("bad-id", result["errors"][0]["gtin"])
        self.assertEqual("published", self._read()["marketplaces"]["mercadolibre"]["publication_status"])
        with open(second_path, encoding="utf-8") as fh:
            second = json.load(fh)
        self.assertEqual("published", second["marketplaces"]["mercadolibre"]["publication_status"])

    def test_published_product_is_blocked_from_layout_unless_explicitly_included(self):
        visor_server.process_payload("/api/meli/publication-status", {
            "gtin": self.gtin, "publication_status": "published",
        })
        rows = [[self.gtin, self.gtin]]
        errors = visor_server.publication_export_errors(["SKU", "Título"], rows)
        self.assertEqual([self.gtin], [error["gtin"] for error in errors])
        self.assertEqual([], visor_server.publication_export_errors(["SKU", "Título"], rows, include_published=True))
        state = {"publication_status": "published"}
        self.assertFalse(publicacion.matches_filter(state, "not_published"))
        self.assertTrue(publicacion.matches_filter(state, "published"))
        self.assertTrue(publicacion.matches_filter(state, "all"))
        self.assertFalse(publicacion.can_select(state))
        self.assertTrue(publicacion.can_select(state, include_published=True))

    def test_legacy_product_is_selectable_and_matches_not_published_filter(self):
        legacy = {}
        self.assertEqual("not_published", publicacion.status_of(legacy))
        self.assertTrue(publicacion.matches_filter(legacy, "not_published"))
        self.assertTrue(publicacion.can_select(legacy))

    def test_visor_wires_publication_filters_badge_and_explicit_selection_override(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "visor", "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        with open(os.path.join(root, "visor", "app.js"), encoding="utf-8") as fh:
            app = fh.read()
        self.assertIn('class="grupo" id="f-publication-status"><legend>Estado en MeLi</legend>', html)
        self.assertNotIn('<select id="f-publication-status">', html)
        self.assertIn('grupoOpcionesExclusivas("f-publication-status", "filtroPublicacionMeli"', app)
        self.assertIn('<small data-cuenta="${clave}:${valor}">0</small>', app)
        self.assertIn('["not_published", "No publicados"]', app)
        self.assertIn('["published", "Publicados en MeLi"]', app)
        self.assertIn('id="meli-incluir-publicados"', html)
        self.assertIn('id="sel-publicados"', html)
        self.assertIn("marcarSeleccionPublicadaMeli", app)
        self.assertIn("gtins: productos.map((p) => p.gtin)", app)
        self.assertIn("MeliPublication.matchesFilter(p, estado.filtroPublicacionMeli)", app)
        self.assertIn("MeliPublication.canSelect(p, estado.incluirPublicados)", app)
        self.assertIn("MeliPublication.canExport(p, estado.incluirPublicados)", app)
        self.assertIn("Publicado en MeLi", app)

    def test_invalid_id_or_status_is_rejected_without_changing_catalog_fields(self):
        with self.assertRaisesRegex(ValueError, "GTIN"):
            visor_server.process_payload("/api/meli/publication-status", {
                "gtin": "../../bad", "publication_status": "published",
            })
        with self.assertRaisesRegex(ValueError, "estado"):
            visor_server.process_payload("/api/meli/publication-status", {
                "gtin": self.gtin, "publication_status": "pending",
            })
        with self.assertRaisesRegex(ValueError, "meli_item_id"):
            visor_server.process_payload("/api/meli/publication-status", {
                "gtin": self.gtin, "publication_status": "published", "meli_item_id": "MLM-x",
            })
        self.assertEqual("MLM17017667", self._read()["marketplaces"]["mercadolibre"]["catalogo_id"])


if __name__ == "__main__":
    unittest.main()
