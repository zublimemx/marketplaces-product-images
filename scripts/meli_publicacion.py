"""Reglas de estado de publicación de Mercado Libre, compartidas por visor y backend."""

NOT_PUBLISHED = "not_published"
PUBLISHED = "published"
PUBLICATION_STATUSES = {NOT_PUBLISHED, PUBLISHED}


def status_of(product):
    return PUBLISHED if isinstance(product, dict) and product.get("publication_status") == PUBLISHED else NOT_PUBLISHED


def matches_filter(product, selected_filter="all"):
    return selected_filter == "all" or status_of(product) == selected_filter


def can_select(product, include_published=False):
    return status_of(product) != PUBLISHED or include_published is True


def can_export(product, include_published=False):
    return not (isinstance(product, dict) and product.get("descartado")) and can_select(product, include_published)


def viewer_fields(mercadolibre):
    return {"publication_status": status_of(mercadolibre),
            "published_at": mercadolibre.get("published_at"),
            "meli_item_id": mercadolibre.get("meli_item_id")}
