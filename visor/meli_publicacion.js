/* Reglas puras del estado de publicación usadas por el visor. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.MeliPublication = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function statusOf(product) {
    return product && product.publication_status === "published" ? "published" : "not_published";
  }

  function matchesFilter(product, filter) {
    return filter === "all" || statusOf(product) === filter;
  }

  function canSelect(product, includePublished) {
    return statusOf(product) !== "published" || includePublished === true;
  }

  function canExport(product, includePublished) {
    return !product?.descartado && canSelect(product, includePublished);
  }

  return { statusOf, matchesFilter, canSelect, canExport };
});
