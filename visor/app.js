/* Visor del catálogo: filtros, cuadrícula, tabla, paginación y detalle.
   Datos: window.CATALOGO (visor/data/productos.js, generado por scripts/build_visor.py). */
(function () {
  "use strict";

  const DATA = window.CATALOGO || { productos: [], total: 0, reglas: {} };
  const P = DATA.productos;
  const $ = (id) => document.getElementById(id);
  const MXN = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });
  const ENT = new Intl.NumberFormat("es-MX");
  const PCT = new Intl.NumberFormat("es-MX", { style: "percent", maximumFractionDigits: 1 });
  const RANGO = { mala: 0, regular: 1, buena: 2, incompletos: 0, completos: 1 };

  const norm = (s) => (s || "").toString().normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const esc = (s) => (s == null ? "" : String(s)).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dinero = (v) => (v == null ? '<span class="sd">sin dato</span>' : MXN.format(v));

  P.forEach((p) => {
    p._nom = norm(p.titulo + " " + p.nombre_sistema);
    p._cat = norm(p.categoria_ruta);
    p._cod = (p.gtin + " " + (p.catalogo_id || "")).toLowerCase();
  });
  const porGtin = new Map(P.map((p) => [p.gtin, p]));

  // Pendientes, errores y mejoras por producto (catálogo en config/pendientes.json)
  const CATP = DATA.pendientes || { acciones: [], tipos: {}, pendientes: {} };
  const TIPOS = ["error", "pendiente", "mejora"];
  const TIPO_ETQ = { error: "Error", pendiente: "Pendiente", mejora: "Mejora" };
  const TIPO_PLURAL = { error: "errores", pendiente: "pendientes", mejora: "mejoras" };
  const ACCIONES = (CATP.acciones || []).map((a) => (typeof a === "string" ? { nombre: a, descripcion: "" } : a));
  const enriquecer = (x) => {
    const c = CATP.pendientes[x.c] || { tipo: "mejora", titulo: x.c, accion: "" };
    return { c: x.c, d: x.d, t: c.tipo, titulo: c.titulo, accion: c.accion };
  };
  const porTipo = (a, b) => TIPOS.indexOf(a.t) - TIPOS.indexOf(b.t);
  function contarPend(p) {
    p._n = { error: 0, pendiente: 0, mejora: 0 };
    p._pend.forEach((x) => { p._n[x.t] += 1; });
    p._grav = p._n.error * 10000 + p._n.pendiente * 100 + p._n.mejora;
  }
  P.forEach((p) => {
    p._pend = (p.pend || []).map(enriquecer).sort(porTipo);
    contarPend(p);
  });

  // Parámetros de precio editables (mismo cálculo que scripts/precios.py, en visor/precios.js)
  const CALC = DATA.calculo || null;
  const PM = window.PreciosMeli;
  const CAMPOS_PRECIO = [
    { id: "precio_venta", label: "Precio de venta (IVA incluido)", corto: "Precio venta" },
    { id: "costo_empaque", label: "Costo de empaque y logística", corto: "Empaque" },
    { id: "comision", label: "Comisión Meli (%, IVA incluido)", corto: "Comisión", pct: true },
    { id: "costo_envio", label: "Costo de envío si el precio queda en $299 o más", corto: "Envío si ≥ $299" },
    { id: "precio_promedio_otros", label: "Promedio otros vendedores (referencia)", corto: "Promedio otros" },
    { id: "precio_mejor_vendedor", label: "Precio mejor vendedor", corto: "Mejor vendedor" },
    { id: "descuento_mejor_vendedor", label: "Descuento contra mejor vendedor", corto: "Descuento" },
  ];
  const CAMPO = Object.fromEntries(CAMPOS_PRECIO.map((c) => [c.id, c]));

  // ---------------- Preferencias (solo en este navegador) ----------------
  const guardar = (k, v) => { try { localStorage.setItem("visor:" + k, JSON.stringify(v)); } catch (e) { /* sin almacenamiento */ } };
  const leer = (k, d) => { try { const v = localStorage.getItem("visor:" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };

  // ---------------- Estado ----------------
  const COLUMNAS = [
    { id: "fotos", label: "Fotos", sort: null },
    { id: "gtin", label: "Código", sort: (p) => p.gtin, mono: true },
    { id: "titulo", label: "Producto", sort: (p) => norm(p.titulo) },
    { id: "categoria", label: "Categoría", sort: (p) => norm(p.categoria) },
    { id: "linea", label: "Línea", sort: (p) => p.linea },
    { id: "stock", label: "Inventario", sort: (p) => p.stock, num: true },
    { id: "precio_venta", label: "Precio venta", sort: (p) => p.precios.precio_venta, num: true, money: true, edit: true },
    { id: "costo_empaque", label: "Empaque", sort: (p) => p.precios.costo_empaque, num: true, money: true, edit: true },
    { id: "precio_marketplaces", label: "Precio marketplaces", sort: (p) => p.precios.precio_marketplaces, num: true, money: true },
    { id: "comision", label: "Comisión", sort: (p) => p.precios.comision, num: true, edit: true },
    { id: "costo_envio", label: "Envío si ≥ $299", sort: (p) => p.precios.costo_envio, num: true, money: true, edit: true },
    { id: "precio_meli_calculado", label: "Precio Meli calculado", sort: (p) => p.precios.precio_meli_calculado, num: true, money: true },
    { id: "precio_promedio_otros", label: "Promedio otros vendedores", sort: (p) => p.precios.precio_promedio_otros, num: true, money: true, edit: true },
    { id: "precio_mejor_vendedor", label: "Precio mejor vendedor", sort: (p) => p.precios.precio_mejor_vendedor, num: true, money: true, edit: true },
    { id: "descuento_mejor_vendedor", label: "Descuento vs mejor", sort: (p) => p.precios.descuento_mejor_vendedor, num: true, money: true, edit: true },
    { id: "precio_meli_final", label: "Precio Meli final", sort: (p) => p.precios.precio_meli_final, num: true, money: true },
    { id: "ingreso_neto", label: "Ingreso neto", sort: (p) => p.precios.ingreso_neto, num: true, money: true },
    { id: "margen", label: "Margen", sort: (p) => p.precios.margen, num: true, money: true },
    { id: "ind_descripcion", label: "Descripción", sort: (p) => RANGO[p.ind.descripcion] },
    { id: "ind_fotos", label: "Calidad de fotos", sort: (p) => RANGO[p.ind.fotos] },
    { id: "ind_precios", label: "Precios", sort: (p) => RANGO[p.ind.precios] },
    { id: "pendientes", label: "Pendientes", sort: (p) => p._grav },
  ];
  const ORDENES = [
    { id: "orden", label: "Prioridad por ventas", sort: (p) => p.orden },
    ...COLUMNAS.filter((c) => c.sort),
  ];
  const estado = {
    seccion: leer("seccion", "catalogo"),
    sel: new Set(leer("sel", []).filter((g) => porGtin.has(g))),
    soloSel: false,
    accion: leer("accion", ""),
    vista: leer("vista", "cuadricula"),
    ordenId: "orden",
    asc: true,
    pagina: 1,
    porPagina: leer("porPagina", 48),
    ocultas: new Set(leer("ocultas2", ["linea", "costo_empaque", "precio_marketplaces", "comision", "descuento_mejor_vendedor", "ingreso_neto", "margen"])),
    ajustes: leer("ajustes", {}),
    f: { nombre: [], codigo: [], categoria: [], linea: new Set(), stock: new Set(), descripcion: new Set(), fotos: new Set(), precios: new Set(),
      publicacion: new Set(), tipo: new Set(), pend: new Set(), ajustes: new Set() },
  };

  // ---------------- Ajustes de precio (en este navegador; se versionan con «Exportar ajustes») ----------------
  const origenCampo = (p, k) => ((estado.ajustes[p.gtin] || {})[k] !== undefined ? "local" : (p.param_origen || {})[k] ? "repo" : "");
  const etiquetasAjuste = (p) => {
    const t = [];
    if (estado.ajustes[p.gtin]) t.push("local");
    if (p.param_origen && Object.keys(p.param_origen).length) t.push("repo");
    return t.length ? t : ["sin"];
  };
  function recalcular(p) {
    if (!CALC || !PM || !p.param) return;
    p.param = { ...p._parBase, ...(estado.ajustes[p.gtin] || {}) };
    p.precios = PM.calcular(p.param, CALC);
    const [ind, mot] = PM.indicador(p.precios, (DATA.reglas || {}).precios || {});
    p.ind.precios = ind;
    p.ind.precios_motivo = mot;
    if (!p.descartado) {
      const nuevos = PM.pendientes(p.precios, CATP.umbrales || {}).map(enriquecer);
      p._pend = p._pend.filter((x) => !PM.CODIGOS.has(x.c)).concat(nuevos).sort(porTipo);
    }
    contarPend(p);
  }
  function ajustar(p, campo, valor) {
    const aj = { ...(estado.ajustes[p.gtin] || {}) };
    const base = p._parBase[campo];
    if (valor == null || Number.isNaN(valor) || (base != null && Math.abs(valor - base) < 1e-9)) delete aj[campo];
    else aj[campo] = valor;
    if (Object.keys(aj).length) estado.ajustes[p.gtin] = aj; else delete estado.ajustes[p.gtin];
    guardar("ajustes", estado.ajustes);
    recalcular(p);
  }
  function restablecer(p) {
    delete estado.ajustes[p.gtin];
    guardar("ajustes", estado.ajustes);
    recalcular(p);
  }
  P.forEach((p) => {
    if (!p.param) return;
    p._parBase = { ...p.param };
    const aj = estado.ajustes[p.gtin];
    if (aj) {  // quita ajustes locales que ya son iguales a los datos (p. ej., ya se versionaron)
      Object.keys(aj).forEach((k) => { if (!(k in p._parBase) || (p._parBase[k] != null && Math.abs(aj[k] - p._parBase[k]) < 1e-9)) delete aj[k]; });
      if (!Object.keys(aj).length) delete estado.ajustes[p.gtin];
    }
    recalcular(p);
  });
  Object.keys(estado.ajustes).forEach((g) => { if (!porGtin.has(g)) delete estado.ajustes[g]; });
  guardar("ajustes", estado.ajustes);

  // ---------------- Filtrado y orden ----------------
  function coincide(p, sin) {
    const f = estado.f;
    if (sin !== "nombre" && f.nombre.length && !f.nombre.some((t) => (t.exact ? p.gtin === t.gtin : p._nom.includes(t.q)))) return false;
    if (sin !== "codigo" && f.codigo.length && !f.codigo.some((t) => p._cod.includes(t.q))) return false;
    if (sin !== "categoria" && f.categoria.length && !f.categoria.some((t) => (t.exact ? p.categoria_ruta === t.value : p._cat.includes(t.q)))) return false;
    if (sin !== "linea" && f.linea.size && !f.linea.has(p.linea)) return false;
    if (sin !== "stock" && f.stock.size && !f.stock.has(p.stock > 0 ? "con" : "sin")) return false;
    if (sin !== "descripcion" && f.descripcion.size && !f.descripcion.has(p.ind.descripcion)) return false;
    if (sin !== "fotos" && f.fotos.size && !f.fotos.has(p.ind.fotos)) return false;
    if (sin !== "precios" && f.precios.size && !f.precios.has(p.ind.precios)) return false;
    if (sin !== "publicacion" && f.publicacion.size && !f.publicacion.has(p.descartado ? "descartado" : "publica")) return false;
    if (sin !== "tipo" && f.tipo.size && !p._pend.some((x) => f.tipo.has(x.t))) return false;
    if (sin !== "pend" && f.pend.size && !p._pend.some((x) => f.pend.has(x.c))) return false;
    if (sin !== "ajustes" && f.ajustes.size && !etiquetasAjuste(p).some((t) => f.ajustes.has(t))) return false;
    if (estado.soloSel && !estado.sel.has(p.gtin)) return false;
    return true;
  }
  // Pendientes del producto que coinciden con los filtros de tipo y pendiente (todos si no hay esos filtros)
  function pendVisibles(p) {
    const f = estado.f;
    return p._pend.filter((x) => (!f.tipo.size || f.tipo.has(x.t)) && (!f.pend.size || f.pend.has(x.c)));
  }
  function comparador() {
    const o = ORDENES.find((x) => x.id === estado.ordenId) || ORDENES[0];
    const dir = estado.asc ? 1 : -1;
    return (a, b) => {
      const va = o.sort(a), vb = o.sort(b);
      if (va == null && vb == null) return a.orden - b.orden;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (va < vb) return -dir;
      if (va > vb) return dir;
      return a.orden - b.orden;
    };
  }
  function filtrados() {
    const enPend = estado.seccion === "pendientes";
    return P.filter((p) => coincide(p) && (!enPend || pendVisibles(p).length > 0)).sort(comparador());
  }

  // ---------------- Componentes ----------------
  function carrusel(imgs, { mini = false, onIndex = null } = {}) {
    const el = document.createElement("div");
    el.className = "carr" + (mini ? " carr-mini" : "");
    if (!imgs.length) {
      el.innerHTML = '<div class="carr-vacio">Sin fotos</div>';
      return el;
    }
    let i = 0;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.decoding = "async";
    el.appendChild(img);
    let cont, dots;
    if (imgs.length > 1) {
      const prev = document.createElement("button");
      prev.type = "button"; prev.className = "carr-btn carr-prev"; prev.setAttribute("aria-label", "Foto anterior"); prev.textContent = "‹";
      const next = document.createElement("button");
      next.type = "button"; next.className = "carr-btn carr-next"; next.setAttribute("aria-label", "Foto siguiente"); next.textContent = "›";
      prev.addEventListener("click", (e) => { e.stopPropagation(); ir(i - 1); });
      next.addEventListener("click", (e) => { e.stopPropagation(); ir(i + 1); });
      el.append(prev, next);
      cont = document.createElement("span"); cont.className = "carr-cont";
      dots = document.createElement("div"); dots.className = "carr-dots";
      dots.innerHTML = imgs.map(() => "<i></i>").join("");
      el.append(cont, dots);
    }
    function ir(n) {
      i = (n + imgs.length) % imgs.length;
      img.src = imgs[i].src;
      img.alt = `Foto ${i + 1} de ${imgs.length}`;
      if (cont) cont.textContent = `${i + 1}/${imgs.length}`;
      if (dots) [...dots.children].forEach((d, k) => d.classList.toggle("on", k === i));
      if (onIndex) onIndex(i);
    }
    el.ir = ir;
    ir(0);
    return el;
  }

  const ETQ = { descripcion: "Descripción", fotos: "Fotos", precios: "Precios" };
  function indicadores(p, completo = false) {
    return `<div class="inds">${["descripcion", "fotos", "precios"].map((k) =>
      `<span class="ind ind-${p.ind[k]}" title="${esc(p.ind[k + "_motivo"])}"><span class="k">${ETQ[k]}</span><span class="v">${p.ind[k]}</span></span>`
    ).join("")}</div>`;
  }

  function cuentaPend(p, lista = p._pend) {
    if (p.descartado) return `<div class="pcuenta"><span class="desc-badge" title="${esc(p.descartado.motivo)}">Descartado de Meli</span></div>`;
    if (!lista.length) return '<div class="pcuenta"><span class="pc pc-ok">Sin pendientes</span></div>';
    const n = { error: 0, pendiente: 0, mejora: 0 };
    lista.forEach((x) => { n[x.t] += 1; });
    return `<div class="pcuenta">${TIPOS.filter((t) => n[t]).map((t) =>
      `<span class="pc pc-${t}" title="${esc(CATP.tipos[t] || "")}">${n[t]} ${n[t] === 1 ? TIPO_ETQ[t].toLowerCase() : TIPO_PLURAL[t]}</span>`).join("")}</div>`;
  }
  function itemPend(x) {
    return `<li class="pi pi-${x.t}"><span class="pt">${TIPO_ETQ[x.t]}</span><div><b>${esc(x.titulo)}.</b> <span class="pd">${esc(x.d)}</span>${x.accion ? `<span class="pa">Acción sugerida: ${esc(x.accion)}</span>` : ""}</div></li>`;
  }

  // Selector múltiple con autocompletado
  function multiSelect(cont, { id, label, placeholder, sugerir, libre, clave }) {
    cont.innerHTML = `<label for="${id}">${label}</label>
      <div class="ms"><div class="ms-box"><input id="${id}" type="text" autocomplete="off" placeholder="${placeholder}"
        role="combobox" aria-expanded="false" aria-controls="${id}-lista" aria-autocomplete="list"></div>
      <ul class="ms-list" id="${id}-lista" role="listbox" hidden></ul></div>`;
    const input = cont.querySelector("input"), box = cont.querySelector(".ms-box"), lista = cont.querySelector("ul");
    let opciones = [], activa = -1;
    box.addEventListener("click", () => input.focus());
    function chips() {
      box.querySelectorAll(".chip").forEach((c) => c.remove());
      estado.f[clave].forEach((t, k) => {
        const c = document.createElement("span");
        c.className = "chip";
        c.innerHTML = `<span title="${esc(t.label)}">${esc(t.label)}</span><button type="button" aria-label="Quitar ${esc(t.label)}">×</button>`;
        c.querySelector("button").addEventListener("click", (e) => { e.stopPropagation(); estado.f[clave].splice(k, 1); chips(); aplicar(); });
        box.insertBefore(c, input);
      });
    }
    function mostrar() {
      const q = input.value.trim();
      opciones = sugerir(norm(q), q);
      if (libre && q) opciones.unshift({ libre: true, label: `Contiene «${q}»`, q: norm(q), value: q });
      activa = opciones.length ? 0 : -1;
      lista.innerHTML = opciones.map((o, k) =>
        `<li role="option" id="${id}-o${k}" aria-selected="${k === activa}"><div class="opt-main"><div>${esc(o.label)}</div>${o.sub ? `<small>${esc(o.sub)}</small>` : ""}</div>${o.n != null ? `<small>${ENT.format(o.n)}</small>` : ""}</li>`
      ).join("");
      lista.hidden = !opciones.length;
      input.setAttribute("aria-expanded", String(!lista.hidden));
      [...lista.children].forEach((li, k) => li.addEventListener("mousedown", (e) => { e.preventDefault(); elegir(k); }));
    }
    function marcar() {
      [...lista.children].forEach((li, k) => li.setAttribute("aria-selected", String(k === activa)));
      if (activa >= 0 && lista.children[activa]) {
        lista.children[activa].scrollIntoView({ block: "nearest" });
        input.setAttribute("aria-activedescendant", `${id}-o${activa}`);
      }
    }
    function elegir(k) {
      const o = opciones[k];
      if (!o) return;
      const t = o.libre ? { label: `contiene «${o.value}»`, q: o.q } : o.token;
      if (!estado.f[clave].some((x) => x.label === t.label)) estado.f[clave].push(t);
      input.value = "";
      lista.hidden = true;
      input.setAttribute("aria-expanded", "false");
      chips();
      aplicar();
    }
    input.addEventListener("input", mostrar);
    input.addEventListener("focus", mostrar);
    input.addEventListener("blur", () => setTimeout(() => { lista.hidden = true; input.setAttribute("aria-expanded", "false"); }, 120));
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); if (lista.hidden) mostrar(); activa = Math.min(activa + 1, opciones.length - 1); marcar(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); activa = Math.max(activa - 1, 0); marcar(); }
      else if (e.key === "Enter") { e.preventDefault(); if (activa >= 0) elegir(activa); }
      else if (e.key === "Escape") { lista.hidden = true; }
      else if (e.key === "Backspace" && !input.value && estado.f[clave].length) { estado.f[clave].pop(); chips(); aplicar(); }
    });
    return { chips };
  }

  function contar(arr) {
    const m = new Map();
    arr.forEach((v) => m.set(v, (m.get(v) || 0) + 1));
    return m;
  }

  const MS = {};
  function montarFiltros() {
    MS.nombre = multiSelect($("f-nombre"), {
      id: "in-nombre", label: "Nombre", placeholder: "Escribe un producto…", clave: "nombre", libre: true,
      sugerir: (q) => {
        if (!q) return [];
        return P.filter((p) => p._nom.includes(q)).slice(0, 10)
          .map((p) => ({ label: p.titulo, sub: p.gtin, token: { exact: true, gtin: p.gtin, label: p.titulo } }));
      },
    });
    MS.codigo = multiSelect($("f-codigo"), {
      id: "in-codigo", label: "Código", placeholder: "GTIN o ID de catálogo…", clave: "codigo", libre: true,
      sugerir: (q) => {
        if (!q) return [];
        return P.filter((p) => p._cod.includes(q)).slice(0, 10)
          .map((p) => ({ label: p.gtin, sub: p.titulo, token: { q: p.gtin, label: p.gtin } }));
      },
    });
    const cats = [...contar(P.map((p) => p.categoria_ruta)).entries()].sort((a, b) => b[1] - a[1]);
    MS.categoria = multiSelect($("f-categoria"), {
      id: "in-categoria", label: "Categoría", placeholder: "Categoría de Mercado Libre…", clave: "categoria", libre: true,
      sugerir: (q) => cats.filter(([r]) => !q || norm(r).includes(q)).slice(0, 12)
        .map(([r, n]) => {
          const hoja = r ? r.split(" > ").pop() : "Sin categoría";
          return { label: hoja, sub: r.split(" > ").slice(0, -1).join(" › "), n, token: { exact: true, value: r, label: hoja } };
        }),
    });
    grupoToggles("f-linea", "linea", [...new Set(P.map((p) => p.linea))].sort().map((v) => [v, v]));
    grupoToggles("f-stock", "stock", [["con", "Con existencia"], ["sin", "Sin existencia"]]);
    grupoToggles("f-ind-descripcion", "descripcion", [["buena", "Buena"], ["regular", "Regular"], ["mala", "Mala"]]);
    grupoToggles("f-ind-fotos", "fotos", [["buena", "Buenas"], ["regular", "Regulares"], ["mala", "Malas"]]);
    grupoToggles("f-ind-precios", "precios", [["completos", "Completos"], ["incompletos", "Incompletos"]]);
    grupoToggles("f-publicacion", "publicacion", [["publica", "Se publica"], ["descartado", "Descartado"]]);
    grupoToggles("f-ajustes", "ajustes", [["local", "Editados aquí"], ["repo", "Ajustados en el repositorio"], ["sin", "Sin ajustes"]]);
    grupoToggles("f-tipo", "tipo", [["error", "Errores"], ["pendiente", "Pendientes"], ["mejora", "Mejoras"]], (t) => "pt-" + t);
    const presentes = new Map();
    P.forEach((p) => new Set(p._pend.map((x) => x.c)).forEach((c) => presentes.set(c, (presentes.get(c) || 0) + 1)));
    const codigos = Object.entries(CATP.pendientes).filter(([c]) => presentes.get(c))
      .sort((a, b) => TIPOS.indexOf(a[1].tipo) - TIPOS.indexOf(b[1].tipo) || presentes.get(b[0]) - presentes.get(a[0]));
    grupoToggles("f-pend", "pend", codigos.map(([c, d]) => [c, d.titulo]), (c) => "pt-" + CATP.pendientes[c].tipo);
    $("limpiar").addEventListener("click", () => {
      Object.keys(estado.f).forEach((k) => { estado.f[k] = Array.isArray(estado.f[k]) ? [] : new Set(); });
      Object.values(MS).forEach((m) => m.chips());
      document.querySelectorAll("#panel-filtros input[type=checkbox]").forEach((c) => { c.checked = false; });
      estado.soloSel = false;
      aplicar();
    });
    $("reglas-texto").innerHTML = textoReglas();
  }

  const TOGGLES = [];
  function sincronizarChecks() {
    TOGGLES.forEach(({ idCont, clave }) => {
      $(idCont).querySelectorAll("input[type=checkbox]").forEach((c) => { c.checked = estado.f[clave].has(c.value); });
    });
  }
  function grupoToggles(idCont, clave, opciones, claseFn) {
    const fs = $(idCont);
    TOGGLES.push({ idCont, clave });
    opciones.forEach(([v, txt]) => {
      const lab = document.createElement("label");
      lab.className = "toggle" + (claseFn ? " " + claseFn(v) : "");
      lab.innerHTML = `<input type="checkbox" id="${idCont}-${v}" value="${esc(v)}"><span>${esc(txt)} <small data-cuenta="${clave}:${esc(v)}">0</small></span>`;
      lab.querySelector("input").addEventListener("change", (e) => {
        e.target.checked ? estado.f[clave].add(v) : estado.f[clave].delete(v);
        aplicar();
      });
      fs.appendChild(lab);
    });
  }

  function textoReglas() {
    const r = DATA.reglas || {};
    const d = r.descripcion || {}, f = r.fotos || {}, pr = r.precios || {};
    const req = pr.requeridos ? Object.values(pr.requeridos).join("; ") : "";
    return `<dl>
      <dt>Descripción</dt>
      <dd>Buena: verificada con confianza ${esc((d.buena?.confianza || []).join(", "))}, ${d.buena?.min_caracteres ?? "—"} caracteres o más y ${d.buena?.min_secciones ?? "—"} secciones o más. Regular: verificada con ${d.regular?.min_caracteres ?? "—"} caracteres o más. Mala: sin verificar o más corta.</dd>
      <dt>Fotos</dt>
      <dd>Buena: ${f.buena?.min_fotos ?? "—"} fotos o más y la principal con el producto de ${f.buena?.min_lado_util_principal ?? "—"} px o más, sin fondo gris. Regular: alguna foto con el producto de ${f.regular?.min_lado_util ?? "—"} px o más. Mala: sin fotos o todas más chicas.</dd>
      <dt>Precios</dt>
      <dd>Completos cuando se conocen: ${esc(req)}.</dd>
    </dl><p>Reglas en <code>config/indicadores.json</code>.</p>`;
  }

  // ---------------- Resumen y conteos ----------------
  function resumen(lista) {
    $("res-total").textContent = ENT.format(lista.length);
    $("res-de").textContent = `de ${ENT.format(P.length)} productos`;
    const grupos = [
      ["descripcion", "Descripción", ["buena", "regular", "mala"]],
      ["fotos", "Fotos", ["buena", "regular", "mala"]],
      ["precios", "Precios", ["completos", "incompletos"]],
    ];
    const nt = { error: 0, pendiente: 0, mejora: 0 };
    lista.forEach((p) => TIPOS.forEach((t) => { if (p._n[t]) nt[t] += 1; }));
    const nDesc = lista.filter((p) => p.descartado).length;
    const grupoPend = `<div class="res-grupo"><span>Pendientes</span>${TIPOS.map((t) =>
      `<button type="button" class="res-chip pc-${t}" data-k="tipo" data-v="${t}" aria-pressed="${estado.f.tipo.has(t)}" title="Productos con al menos un ${TIPO_ETQ[t].toLowerCase()}: ${esc(CATP.tipos[t] || "")}">${TIPO_PLURAL[t]} <b>${ENT.format(nt[t])}</b></button>`).join("")}${nDesc || estado.f.publicacion.has("descartado")
      ? `<button type="button" class="res-chip" data-k="publicacion" data-v="descartado" aria-pressed="${estado.f.publicacion.has("descartado")}">descartados <b>${ENT.format(nDesc)}</b></button>` : ""}</div>`;
    const stockTotal = lista.reduce((s, p) => s + p.stock, 0);
    const sinStock = lista.filter((p) => p.stock <= 0).length;
    $("resumen-grupos").innerHTML = grupos.map(([k, t, vals]) => {
      const c = contar(lista.map((p) => p.ind[k]));
      return `<div class="res-grupo"><span>${t}</span>${vals.map((v) =>
        `<button type="button" class="res-chip ind-${v}" data-k="${k}" data-v="${v}" aria-pressed="${estado.f[k].has(v)}">${v} <b>${ENT.format(c.get(v) || 0)}</b></button>`).join("")}</div>`;
    }).join("") + `<div class="res-grupo"><span>Inventario</span><span class="res-chip">${ENT.format(stockTotal)} piezas</span><button type="button" class="res-chip ind-mala" data-k="stock" data-v="sin" aria-pressed="${estado.f.stock.has("sin")}">sin existencia <b>${ENT.format(sinStock)}</b></button></div>` + grupoPend;
    $("resumen-grupos").querySelectorAll("button[data-k]").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.k, v = b.dataset.v;
      estado.f[k].has(v) ? estado.f[k].delete(v) : estado.f[k].add(v);
      sincronizarChecks();
      aplicar();
    }));
    // conteos de cada opción considerando los demás filtros
    const claves = {
      linea: (p) => p.linea, stock: (p) => (p.stock > 0 ? "con" : "sin"), descripcion: (p) => p.ind.descripcion, fotos: (p) => p.ind.fotos,
      precios: (p) => p.ind.precios, publicacion: (p) => (p.descartado ? "descartado" : "publica"),
      tipo: (p) => TIPOS.filter((t) => p._n[t]), pend: (p) => [...new Set(p._pend.map((x) => x.c))],
      ajustes: (p) => etiquetasAjuste(p),
    };
    Object.entries(claves).forEach(([k, fn]) => {
      const c = contar(P.filter((p) => coincide(p, k)).flatMap((p) => { const v = fn(p); return Array.isArray(v) ? v : [v]; }));
      document.querySelectorAll(`[data-cuenta^="${k}:"]`).forEach((el) => { el.textContent = ENT.format(c.get(el.dataset.cuenta.split(":")[1]) || 0); });
    });
  }

  // ---------------- Vistas ----------------
  // Casilla de selección que no abre el detalle al hacer clic
  function casillaSel(p, clase, alCambiar) {
    const lab = document.createElement("label");
    lab.className = clase;
    lab.innerHTML = `<input type="checkbox" ${estado.sel.has(p.gtin) ? "checked" : ""} aria-label="Seleccionar ${esc(p.titulo)}">`;
    const inp = lab.querySelector("input");
    lab.addEventListener("click", (e) => e.stopPropagation());
    inp.addEventListener("keydown", (e) => e.stopPropagation());
    inp.addEventListener("change", () => { if (alCambiar) alCambiar(inp.checked); alternarSel(p.gtin, inp.checked); });
    return lab;
  }

  // ---------------- Edición de precios ----------------
  const aNum = (s) => {
    const t = String(s == null ? "" : s).trim().replace(/[$,\s%]/g, "");
    if (!t) return null;
    const v = Number(t);
    return Number.isFinite(v) && v >= 0 ? v : NaN;
  };
  const valorCampo = (p, k) => {
    const v = p.precios[k];
    return v == null ? "" : CAMPO[k].pct ? String(Math.round(v * 10000) / 100) : String(v);
  };
  const ORIGEN_TXT = { local: "Editado en este navegador (se versiona con «Exportar ajustes»)", repo: "Ajustado en el repositorio (data/ajustes_precios.json)" };
  function marcarOrigen(inp, p, k) {
    const o = origenCampo(p, k);
    inp.classList.toggle("aj-local", o === "local");
    inp.classList.toggle("aj-repo", o === "repo");
    inp.title = ORIGEN_TXT[o] || "";
  }
  function inputPrecio(p, k, alCambiar) {
    const c = CAMPO[k];
    const inp = document.createElement("input");
    inp.type = "text";
    inp.inputMode = "decimal";
    inp.autocomplete = "off";
    inp.className = "num-in";
    inp.value = valorCampo(p, k);
    inp.placeholder = "—";
    inp.dataset.campo = k;
    inp.setAttribute("aria-label", `${c.label}: ${p.titulo}`);
    marcarOrigen(inp, p, k);
    ["click", "mousedown", "dblclick"].forEach((ev) => inp.addEventListener(ev, (e) => e.stopPropagation()));
    inp.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") inp.blur();
      if (e.key === "Escape") { inp.value = valorCampo(p, k); inp.blur(); }
    });
    inp.addEventListener("change", () => {
      let v = aNum(inp.value);
      if (v != null && c.pct) v = v >= 100 ? NaN : v / 100;
      if (Number.isNaN(v)) { inp.classList.add("invalido"); inp.setAttribute("aria-invalid", "true"); return; }
      inp.classList.remove("invalido");
      inp.removeAttribute("aria-invalid");
      ajustar(p, k, v);
      inp.value = valorCampo(p, k);
      marcarOrigen(inp, p, k);
      if (alCambiar) alCambiar(k);
    });
    return inp;
  }
  const textoEnvio = (p) => (p.envio ? `Estimado ${MXN.format(p.envio.estimado)} · ${p.envio.peso} kg (${p.envio.tamano}). ${p.envio.base}` : "");

  // Formulario de parámetros con resultados en vivo (detalle y editor de la cuadrícula)
  function formPrecios(p, alCambiar) {
    const el = document.createElement("div");
    el.className = "form-precios";
    const campos = document.createElement("div");
    campos.className = "fp-campos";
    const pistas = {
      comision: "Por omisión, según la categoría raíz",
      costo_envio: textoEnvio(p),
      precio_mejor_vendedor: p.metodo_mejor_vendedor ? `Fuente: ${p.metodo_mejor_vendedor}` : "Publicación del mismo producto con más ventas",
      descuento_mejor_vendedor: "Precio final = mejor vendedor − descuento",
      costo_empaque: "Se suma al precio de venta",
    };
    const res = document.createElement("dl");
    res.className = "kv fp-res";
    const pintar = () => {
      const pr = p.precios;
      const aplica = pr.precio_meli_final >= CALC.umbral;
      res.innerHTML = `
        <dt>Precio de venta marketplaces</dt><dd>${dinero(pr.precio_marketplaces)}</dd>
        <dt>Precio Meli calculado</dt><dd>${dinero(pr.precio_meli_calculado)}</dd>
        <dt class="fuerte">Precio Meli final <small class="regla">mejor vendedor − descuento, nunca abajo del calculado</small></dt><dd class="fuerte">${dinero(pr.precio_meli_final)}</dd>
        <dt>Diferencia contra mejor vendedor</dt><dd>${pr.diferencia_mejor_vendedor == null ? '<span class="sd">sin dato</span>' : PCT.format(pr.diferencia_mejor_vendedor)}</dd>
        <dt>Costo fijo Meli</dt><dd>${dinero(pr.costo_fijo)}</dd>
        <dt>Envío a cargo del vendedor ${aplica ? "" : '<small class="regla">no aplica: precio menor a $299</small>'}</dt><dd>${dinero(pr.envio_vendedor)}</dd>
        <dt>Ingreso neto estimado</dt><dd>${dinero(pr.ingreso_neto)}</dd>
        <dt>Margen sobre precio marketplaces</dt><dd class="${pr.margen < 0 ? "stock-0" : ""}">${dinero(pr.margen)}</dd>`;
      reset.hidden = !estado.ajustes[p.gtin];
    };
    const inputs = [];
    const cambio = (k) => { pintar(); if (alCambiar) alCambiar(k); };
    CAMPOS_PRECIO.forEach((c) => {
      const fila = document.createElement("label");
      fila.className = "fp-fila";
      fila.innerHTML = `<span class="fp-etq">${esc(c.label)}${pistas[c.id] ? `<small>${esc(pistas[c.id])}</small>` : ""}</span>`;
      const caja = document.createElement("span");
      caja.className = "fp-caja";
      caja.innerHTML = `<span class="fp-u">${c.pct ? "%" : "$"}</span>`;
      const inp = inputPrecio(p, c.id, cambio);
      caja.prepend(inp);
      inputs.push(inp);
      fila.appendChild(caja);
      campos.appendChild(fila);
    });
    const pie = document.createElement("div");
    pie.className = "fp-pie";
    pie.innerHTML = `<span class="fp-leyenda"><i class="aj-local"></i> editado aquí <i class="aj-repo"></i> ajustado en el repositorio</span>`;
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "btn-link";
    reset.textContent = "Deshacer lo editado en este producto";
    reset.addEventListener("click", () => {
      restablecer(p);
      inputs.forEach((inp) => { inp.value = valorCampo(p, inp.dataset.campo); marcarOrigen(inp, p, inp.dataset.campo); inp.classList.remove("invalido"); });
      cambio(null);
    });
    pie.appendChild(reset);
    el.append(campos, res, pie);
    pintar();
    return el;
  }

  function abrirEditor(p) {
    const d = $("editor-precios"), inner = $("ed-inner");
    inner.innerHTML = `<div class="det-head"><div><h2 id="ed-titulo">${esc(p.titulo)}</h2>
      <div class="det-sub"><span class="mono">${esc(p.gtin)}</span><span>${ENT.format(p.stock)} piezas</span><span>${esc(p.categoria)}</span></div></div>
      <div class="det-acciones"><button type="button" class="btn" id="ed-detalle">Ver detalle</button><button type="button" class="btn btn-primario" id="ed-listo">Listo</button></div></div>`;
    inner.appendChild(formPrecios(p));
    $("ed-listo").addEventListener("click", () => d.close());
    $("ed-detalle").addEventListener("click", () => { d.close(); abrir(p.gtin); });
    d.showModal();
  }

  const DERIVADAS = new Set(["precio_marketplaces", "precio_meli_calculado", "precio_meli_final", "ingreso_neto", "margen", "ind_precios", "pendientes"]);
  function actualizarFila(tr, p) {
    if (!tr) return;
    tr.querySelectorAll("td[data-col]").forEach((td) => {
      const col = td.dataset.col;
      if (col === "costo_envio") {
        const s = td.querySelector("small.sub");
        if (s) s.textContent = subEnvio(p);
      }
      if (!DERIVADAS.has(col)) return;
      const nuevo = celda(p, COLUMNAS.find((x) => x.id === col));
      nuevo.dataset.col = col;
      td.replaceWith(nuevo);
    });
    tr.classList.toggle("editado", !!estado.ajustes[p.gtin]);
    resumen(vistaActual.lista);
    actualizarBarra();
  }
  const subEnvio = (p) => (p.envio ? `${p.envio.peso} kg${CALC && p.precios.precio_meli_final >= CALC.umbral ? "" : " · no aplica"}` : "");

  function tarjeta(p) {
    const el = document.createElement("article");
    el.className = "card" + (estado.sel.has(p.gtin) ? " sel" : "");
    el.tabIndex = 0;
    el.setAttribute("aria-label", p.titulo);
    el.appendChild(casillaSel(p, "card-sel", (on) => el.classList.toggle("sel", on)));
    el.appendChild(carrusel(p.imagenes));
    const info = document.createElement("div");
    info.style.display = "contents";
    info.innerHTML = `
      <div class="meta"><span class="mono">${esc(p.gtin)}</span><span class="${p.stock > 0 ? "" : "stock-0"}">${ENT.format(p.stock)} pzas</span></div>
      <h3>${esc(p.titulo)}</h3>
      <div class="cat" title="${esc(p.categoria_ruta)}">${esc(p.categoria)}</div>
      <div class="precio"><strong>${dinero(p.precios.precio_meli_final)}</strong><small>venta ${dinero(p.precios.precio_venta)}</small></div>
      ${CALC ? `<div class="envio-linea${p.precios.precio_meli_final >= CALC.umbral ? " aplica" : ""}" title="${esc(textoEnvio(p))}">${p.precios.precio_meli_final >= CALC.umbral ? `Envío a tu cargo: <b>${MXN.format(p.precios.costo_envio)}</b>` : `Envío <b>${MXN.format(p.precios.costo_envio)}</b> si llega a $299`} · ${p.envio ? p.envio.peso : "—"} kg</div>` : ""}
      ${indicadores(p)}
      ${cuentaPend(p)}`;
    el.appendChild(info);
    if (CALC) {
      const pie = document.createElement("div");
      pie.className = "card-pie";
      pie.innerHTML = `${estado.ajustes[p.gtin] ? '<span class="tag-editado">precios editados</span>' : ""}<button type="button" class="btn-mini">Editar precios</button>`;
      pie.querySelector("button").addEventListener("click", (e) => { e.stopPropagation(); abrirEditor(p); });
      el.appendChild(pie);
    }
    el.addEventListener("click", () => abrir(p.gtin));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter") abrir(p.gtin); });
    return el;
  }

  function celda(p, c) {
    const td = document.createElement("td");
    if (c.num) td.className = "num";
    if (c.edit && CALC && p.param) {
      td.className = "num edit";
      td.appendChild(inputPrecio(p, c.id, () => actualizarFila(td.closest("tr"), p)));
      if (c.id === "costo_envio") td.insertAdjacentHTML("beforeend", `<small class="sub" title="${esc(textoEnvio(p))}">${esc(subEnvio(p))}</small>`);
      return td;
    }
    switch (c.id) {
      case "fotos": td.appendChild(carrusel(p.imagenes, { mini: true })); break;
      case "gtin": td.innerHTML = `<span class="mono">${esc(p.gtin)}</span>`; break;
      case "titulo": td.className = "prod"; td.innerHTML = `${esc(p.titulo)}<small>${esc(p.nombre_sistema)}</small>`; break;
      case "categoria": td.className = "cat"; td.title = p.categoria_ruta; td.textContent = p.categoria; break;
      case "linea": td.textContent = p.linea; break;
      case "stock": td.innerHTML = `<span class="${p.stock > 0 ? "" : "stock-0"}">${ENT.format(p.stock)}</span>`; break;
      case "ind_descripcion": case "ind_fotos": case "ind_precios": {
        const k = c.id.slice(4);
        td.innerHTML = `<span class="ind ind-${p.ind[k]}" title="${esc(p.ind[k + "_motivo"])}"><span class="v">${p.ind[k]}</span></span>`;
        break;
      }
      case "pendientes": td.innerHTML = cuentaPend(p); break;
      case "comision": td.textContent = PCT.format(p.precios.comision); break;
      default: td.innerHTML = dinero(p.precios[c.id]);
    }
    return td;
  }

  function cabecera() {
    const tr = $("tabla-head");
    tr.innerHTML = "";
    const thSel = document.createElement("th");
    thSel.scope = "col";
    thSel.className = "col-sel";
    thSel.innerHTML = '<input type="checkbox" id="sel-todos">';
    thSel.querySelector("input").addEventListener("change", (e) => {
      const lista = vistaActual.lista;
      const todos = lista.length && lista.every((p) => estado.sel.has(p.gtin));
      lista.forEach((p) => (todos ? estado.sel.delete(p.gtin) : estado.sel.add(p.gtin)));
      e.target.checked = !todos;
      guardarSel();
      render();
    });
    tr.appendChild(thSel);
    COLUMNAS.filter((c) => !estado.ocultas.has(c.id)).forEach((c) => {
      const th = document.createElement("th");
      th.scope = "col";
      if (c.num) th.className = "num";
      if (c.sort) {
        const activo = estado.ordenId === c.id;
        th.setAttribute("aria-sort", activo ? (estado.asc ? "ascending" : "descending") : "none");
        const b = document.createElement("button");
        b.type = "button";
        b.innerHTML = `${esc(c.label)}<span class="dir">${activo ? (estado.asc ? "▲" : "▼") : ""}</span>`;
        b.addEventListener("click", () => {
          if (estado.ordenId === c.id) estado.asc = !estado.asc; else { estado.ordenId = c.id; estado.asc = true; }
          $("orden").value = estado.ordenId;
          estado.pagina = 1;
          render();
        });
        th.appendChild(b);
      } else th.textContent = c.label;
      tr.appendChild(th);
    });
  }

  function menuColumnas() {
    const m = $("menu-columnas");
    m.innerHTML = COLUMNAS.map((c) => `<label><input type="checkbox" id="col-${c.id}" ${estado.ocultas.has(c.id) ? "" : "checked"}> ${esc(c.label)}</label>`).join("");
    m.querySelectorAll("input").forEach((i) => i.addEventListener("change", () => {
      const id = i.id.slice(4);
      i.checked ? estado.ocultas.delete(id) : estado.ocultas.add(id);
      guardar("ocultas2", [...estado.ocultas]);
      render();
    }));
  }

  function paginacion(total) {
    const nav = $("paginacion");
    const paginas = Math.max(1, Math.ceil(total / estado.porPagina));
    estado.pagina = Math.min(estado.pagina, paginas);
    if (paginas <= 1) { nav.innerHTML = ""; return; }
    const cur = estado.pagina;
    const nums = new Set([1, paginas, cur - 1, cur, cur + 1, cur - 2, cur + 2].filter((n) => n >= 1 && n <= paginas));
    const orden = [...nums].sort((a, b) => a - b);
    let html = `<button type="button" data-p="${cur - 1}" ${cur === 1 ? "disabled" : ""} aria-label="Página anterior">‹</button>`;
    orden.forEach((n, k) => {
      if (k && n - orden[k - 1] > 1) html += '<span class="gap">…</span>';
      html += `<button type="button" data-p="${n}" ${n === cur ? 'aria-current="page"' : ""}>${n}</button>`;
    });
    html += `<button type="button" data-p="${cur + 1}" ${cur === paginas ? "disabled" : ""} aria-label="Página siguiente">›</button>`;
    nav.innerHTML = html;
    nav.querySelectorAll("button[data-p]").forEach((b) => b.addEventListener("click", () => {
      estado.pagina = +b.dataset.p;
      render();
      $("resultados").scrollIntoView({ block: "start" });
    }));
  }

  // ---------------- Sección Pendientes ----------------
  let vistaActual = { lista: [], pagina: [] };
  let ayudaMsg = "";
  const guardarSel = () => guardar("sel", [...estado.sel]);

  function filaPend(p) {
    const el = document.createElement("article");
    el.className = "pfila" + (estado.sel.has(p.gtin) ? " sel" : "");
    const vis = pendVisibles(p);
    const chk = casillaSel(p, "psel", (on) => el.classList.toggle("sel", on));
    const foto = document.createElement("div");
    foto.className = "pfoto";
    foto.appendChild(carrusel(p.imagenes, { mini: true }));
    const info = document.createElement("div");
    info.className = "pinfo";
    info.innerHTML = `<div class="meta"><span class="mono">${esc(p.gtin)}</span><span>${esc(p.linea)}</span><span class="${p.stock > 0 ? "" : "stock-0"}">${ENT.format(p.stock)} pzas</span><span>#${ENT.format(p.orden)} en ventas</span></div>
      <h3><button type="button" class="plink">${esc(p.titulo)}</button></h3>
      <div class="cat" title="${esc(p.categoria_ruta)}">${esc(p.categoria)}</div>
      ${cuentaPend(p, vis)}${vis.length < p._pend.length ? `<small class="pmas">y ${p._pend.length - vis.length} más fuera del filtro</small>` : ""}`;
    info.querySelector(".plink").addEventListener("click", () => abrir(p.gtin));
    const ul = document.createElement("ul");
    ul.className = "plista";
    ul.innerHTML = vis.map(itemPend).join("");
    el.append(chk, foto, info, ul);
    return el;
  }

  function actualizarBarra() {
    const { lista, pagina } = vistaActual;
    const n = estado.sel.size;
    const nFil = lista.reduce((s, p) => s + (estado.sel.has(p.gtin) ? 1 : 0), 0);
    $("sel-n").textContent = ENT.format(n);
    $("sel-txt").textContent = (n === 1 ? "seleccionado" : "seleccionados") + (n && nFil !== n ? ` (${ENT.format(nFil)} con los filtros actuales)` : "");
    $("sel-filtrados").textContent = lista.length === 1 ? "Seleccionar 1 filtrado" : `Seleccionar los ${ENT.format(lista.length)} filtrados`;
    $("sel-filtrados").disabled = !lista.length || nFil === lista.length;
    $("desel-filtrados").textContent = nFil === 1 ? "Deseleccionar 1 filtrado" : `Deseleccionar los ${ENT.format(nFil)} filtrados`;
    $("desel-filtrados").disabled = !nFil;
    $("sel-pagina").disabled = !pagina.length || pagina.every((p) => estado.sel.has(p.gtin));
    $("sel-quitar").disabled = !n;
    $("solo-sel").checked = estado.soloSel;
    const nMeli = [...estado.sel].filter((g) => !porGtin.get(g).descartado).length;
    $("exportar-meli").disabled = !nMeli;
    $("exportar-meli").textContent = nMeli ? `Exportar layout Meli (${ENT.format(nMeli)})` : "Exportar layout Meli";
    $("exportar").disabled = !n;
    $("exportar").textContent = n ? `Exportar pendientes (${ENT.format(n)})` : "Exportar pendientes";
    const nLocal = Object.keys(estado.ajustes).length;
    const nRepo = P.filter((p) => p.param_origen && Object.keys(p.param_origen).length).length;
    $("ajustes-fila").hidden = !nLocal && !nRepo;
    $("aj-n").textContent = ENT.format(nLocal);
    $("aj-txt").textContent = (nLocal === 1 ? "producto con precios editados en este navegador" : "productos con precios editados en este navegador")
      + (nRepo ? ` · ${ENT.format(nRepo)} ajustados en el repositorio` : "");
    $("aj-exportar").disabled = !nLocal && !nRepo;
    $("aj-deshacer").disabled = !nLocal;
    const soloEd = estado.f.ajustes.size === 1 && estado.f.ajustes.has("local");
    $("aj-ver").setAttribute("aria-pressed", String(soloEd));
    $("aj-ver").textContent = soloEd ? "Ver todos" : "Ver solo editados";
    const todos = $("sel-todos");
    if (todos) {
      todos.checked = lista.length > 0 && nFil === lista.length;
      todos.indeterminate = nFil > 0 && nFil < lista.length;
      todos.setAttribute("aria-label", todos.checked ? `Deseleccionar los ${lista.length} filtrados` : `Seleccionar los ${lista.length} filtrados`);
      todos.title = todos.getAttribute("aria-label");
    }
  }

  function alternarSel(gtin, on) {
    on ? estado.sel.add(gtin) : estado.sel.delete(gtin);
    guardarSel();
    if (estado.soloSel && !on) render(); else actualizarBarra();
  }

  function describirFiltros() {
    const f = estado.f, partes = [];
    const lbl = (arr) => arr.map((t) => t.label).join(" o ");
    if (f.nombre.length) partes.push("Nombre: " + lbl(f.nombre));
    if (f.codigo.length) partes.push("Código: " + lbl(f.codigo));
    if (f.categoria.length) partes.push("Categoría: " + lbl(f.categoria));
    const conj = [
      ["linea", "Línea", {}], ["stock", "Inventario", { con: "con existencia", sin: "sin existencia" }],
      ["descripcion", "Descripción", {}], ["fotos", "Fotos", {}], ["precios", "Precios", {}],
      ["publicacion", "Publicación en Meli", { publica: "se publica", descartado: "descartado" }],
      ["tipo", "Tipo de pendiente", { error: "errores", pendiente: "pendientes", mejora: "mejoras" }],
      ["ajustes", "Ajustes de precio", { local: "editados aquí", repo: "ajustados en el repositorio", sin: "sin ajustes" }],
      ["pend", "Pendiente", Object.fromEntries(Object.entries(CATP.pendientes).map(([c, d]) => [c, d.titulo]))],
    ];
    conj.forEach(([k, t, m]) => { if (f[k].size) partes.push(`${t}: ${[...f[k]].map((v) => m[v] || v).join(" o ")}`); });
    return partes.join(" · ") || "Ninguno";
  }

  function exportar() {
    const prods = P.filter((p) => estado.sel.has(p.gtin)).sort(comparador());
    if (!prods.length) return;
    const filtroPend = estado.f.tipo.size || estado.f.pend.size;
    const filasP = [], filasD = [];
    prods.forEach((p) => {
      let vis = pendVisibles(p);
      if (!vis.length) vis = p._pend;
      const n = { error: 0, pendiente: 0, mejora: 0 };
      vis.forEach((x) => { n[x.t] += 1; });
      const pr = p.precios;
      filasP.push([p.gtin, p.titulo, p.nombre_sistema, p.linea, p.categoria_ruta || "Sin categoría", p.stock,
        pr.precio_venta, pr.precio_meli_calculado, pr.precio_mejor_vendedor, pr.precio_meli_final,
        p.ind.descripcion, p.ind.fotos, p.ind.precios, n.error, n.pendiente, n.mejora,
        vis.map((x) => `[${TIPO_ETQ[x.t]}] ${x.titulo}: ${x.d}`).join("\n"),
        [...new Set(vis.map((x) => x.accion).filter(Boolean))].join("; "),
        p.descartado ? `Descartado: ${p.descartado.motivo}` : "Se publica",
        estado.accion, ""]);
      vis.forEach((x) => filasD.push([p.gtin, p.titulo, TIPO_ETQ[x.t], x.titulo, x.d, x.accion, x.c]));
    });
    const ahora = new Date();
    const dos = (v) => String(v).padStart(2, "0");
    const sello = `${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}-${dos(ahora.getDate())}_${dos(ahora.getHours())}${dos(ahora.getMinutes())}`;
    const nombre = `pendientes_meli_${sello}.xlsx`;
    const colsP = [
      ["Código", 16, "codigo"], ["Producto", 40, "largo"], ["Nombre en sistema", 26, "texto"], ["Línea", 12, "texto"],
      ["Categoría", 36, "largo"], ["Inventario", 11, "entero"], ["Precio de venta", 13, "dinero"], ["Precio Meli calculado", 13, "dinero"],
      ["Precio mejor vendedor", 13, "dinero"], ["Precio Meli final", 13, "dinero"], ["Descripción", 12, "texto"], ["Fotos", 10, "texto"],
      ["Precios", 12, "texto"], ["Errores", 9, "entero"], ["Pendientes", 11, "entero"], ["Mejoras", 9, "entero"],
      ["Detalle de pendientes", 90, "largo"], ["Acciones sugeridas", 30, "largo"], ["Publicación en Meli", 16, "texto"],
      ["Acción solicitada", 24, "texto"], ["Comentarios", 40, "largo"],
    ].map(([titulo, ancho, formato]) => ({ titulo, ancho, formato }));
    const colsD = [["Código", 16, "codigo"], ["Producto", 40, "largo"], ["Tipo", 11, "texto"], ["Pendiente", 34, "texto"],
      ["Detalle", 90, "largo"], ["Acción sugerida", 22, "texto"], ["Clave", 20, "texto"]].map(([titulo, ancho, formato]) => ({ titulo, ancho, formato }));
    const inst = [
      ["Exportado", ahora.toLocaleString("es-MX")],
      ["Datos del visor", DATA.generado || ""],
      ["Productos", prods.length],
      ["Filtros aplicados", describirFiltros()],
      ["Pendientes incluidos", filtroPend ? "Solo los que coinciden con los filtros de tipo y pendiente (si un producto no tiene ninguno, todos los suyos)" : "Todos los del producto"],
      ["Acción solicitada precargada", estado.accion || "Ninguna"],
      ["", ""],
      ["Cómo usarlo", "1. En la hoja Productos, elige en «Acción solicitada» qué quieres que se haga con cada producto (lista desplegable). 2. Si hace falta, escribe instrucciones o el dato correcto en «Comentarios». 3. Adjunta este archivo en el chat y pide: «Procesa las solicitudes de este archivo»."],
      ["", ""],
      ["Acción", "Qué se hará"],
      ...ACCIONES.map((a) => [a.nombre, a.descripcion]),
      ["", ""],
      ["Tipo", "Significado"],
      ...TIPOS.map((t) => [TIPO_ETQ[t], CATP.tipos[t] || ""]),
    ];
    XLSXSimple.descargar(nombre, [
      { nombre: "Productos", columnas: colsP, filas: filasP, filtro: true, lista: { columna: 19, opciones: ACCIONES.map((a) => a.nombre) } },
      { nombre: "Detalle", columnas: colsD, filas: filasD, filtro: true },
      { nombre: "Instrucciones", columnas: [{ titulo: "Concepto", ancho: 30, formato: "texto" }, { titulo: "Detalle", ancho: 120, formato: "largo" }], filas: inst },
    ]);
    ayudaMsg = `Se descargó ${nombre} con ${ENT.format(prods.length)} productos. Adjúntalo en el chat y pide: «Procesa las solicitudes de este archivo».`;
    $("pb-ayuda").textContent = ayudaMsg;
  }

  // ---------------- Layout de Mercado Libre (igual al de scripts/build_mercadolibre.py, con valores) ----------------
  // json.dumps de Python (con ", " y ": ") para los atributos de ficha que son objetos o listas
  const pyJson = (v) => (Array.isArray(v) ? `[${v.map(pyJson).join(", ")}]`
    : v && typeof v === "object" ? `{${Object.entries(v).map(([k, x]) => `${JSON.stringify(k)}: ${pyJson(x)}`).join(", ")}}`
      : JSON.stringify(v));

  function exportarLayout() {
    const M = DATA.meli;
    if (!M) return;
    const sel = P.filter((p) => estado.sel.has(p.gtin)).sort(comparador());
    const omitidos = sel.filter((p) => p.descartado);
    const prods = sel.filter((p) => !p.descartado);
    if (!prods.length) return;
    const pub = M.publicacion;
    const filas = prods.map((p) => {
      const pr = p.precios, f = p.ficha || {};
      const final = pr.precio_meli_final;
      const imgs = p.imagenes.slice(0, M.n_imagenes).map((im) => `${M.url_imagenes}/${p.gtin}/images/${im.a}`);
      while (imgs.length < M.n_imagenes) imgs.push("");
      const ficha = M.ficha.map((k) => {
        const v = f[k];
        return v == null || v === "" ? "" : typeof v === "object" ? pyJson(v) : v;
      });
      return [p.gtin, p.gtin, p.sin_titulo ? `PENDIENTE: ${p.nombre_sistema}` : p.titulo, p.categoria_id, p.categoria_ruta, final, p.stock,
        pub.condicion, pub.tipo_publicacion, p.descripcion, pub.forma_envio,
        final >= M.umbral_envio_gratis ? M.texto_envio_gratis : pub.costo_envio,
        pub.retiro_en_persona, pub.tipo_garantia, p.catalogo_id, ...ficha, ...imgs,
        p.linea, p.nombre_sistema, M.estados[p.investigacion.estado] || p.investigacion.estado,
        p._pend.filter((x) => x.t === "error").map((x) => x.titulo).join("; ")];
    });
    const formato = (h, i) => {
      if (i < 2) return { formato: "codigo", ancho: 16 };
      if (h === "Título") return { formato: "texto", ancho: 58 };
      if (h === "Categoría (ruta)") return { formato: "texto", ancho: 60 };
      if (h === "Precio [$]") return { formato: "dinero", ancho: 12 };
      if (h === "Cantidad") return { formato: "entero", ancho: 10 };
      if (h === "Descripción") return { formato: "texto", ancho: 60 };
      if (h.startsWith("Imagen ")) return { formato: "texto", ancho: 30 };
      return { formato: "auto", ancho: 16 };
    };
    const cols = M.encabezados.map((h, i) => ({ titulo: h, ...formato(h, i) }))
      .concat(M.encabezados_aux.map((h) => ({ titulo: h, formato: "texto", ancho: 22, aux: true })))
      .concat([{ titulo: "Errores a revisar", formato: "texto", ancho: 40, aux: true }]);
    const colsP = [
      ["SKU", 16, "codigo"], ["Título", 50, "texto"], ["Categoría (ruta)", 50, "texto"], ["Precio de venta", 13, "dinero"],
      ["Costo de empaque y logística", 12, "dinero"], ["Precio de venta Marketplaces", 14, "dinero"], ["Comisión Meli", 11, "porcentaje"],
      ["Costo de envío si el precio queda en $299 o más", 14, "dinero"], ["Descuento contra mejor vendedor", 12, "dinero"], ["Precio Meli calculado", 13, "dinero"],
      ["Precio Meli promedio otros vendedores", 15, "dinero"], ["Precio mejor vendedor", 13, "dinero"], ["Precio Meli Final", 13, "dinero"],
      ["Diferencia contra mejor vendedor", 13, "porcentaje"], ["Costo fijo aplicado", 12, "dinero"], ["Envío a cargo del vendedor", 13, "dinero"],
      ["Ingreso neto estimado", 13, "dinero"], ["Margen contra Precio de venta Marketplaces", 15, "dinero"],
    ].map(([titulo, ancho, f]) => ({ titulo, ancho, formato: f }));
    const filasP = prods.map((p) => {
      const pr = p.precios;
      return [p.gtin, p.titulo, p.categoria_ruta, pr.precio_venta, pr.costo_empaque, pr.precio_marketplaces, pr.comision, pr.costo_envio,
        pr.descuento_mejor_vendedor, pr.precio_meli_calculado,
        pr.precio_promedio_otros, pr.precio_mejor_vendedor, pr.precio_meli_final, pr.diferencia_mejor_vendedor, pr.costo_fijo,
        pr.envio_vendedor, pr.ingreso_neto, pr.margen];
    });
    const conError = prods.filter((p) => p._n.error);
    const ahora = new Date();
    const dos = (v) => String(v).padStart(2, "0");
    const nombre = `layout_meli_${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}-${dos(ahora.getDate())}_${dos(ahora.getHours())}${dos(ahora.getMinutes())}.xlsx`;
    const inst = [
      ["Exportado", ahora.toLocaleString("es-MX")],
      ["Datos del visor", DATA.generado || ""],
      ["Productos en el layout", prods.length],
      ["Descartados omitidos", omitidos.length ? `${omitidos.length}: ${omitidos.map((p) => p.gtin).join(", ")}` : "0"],
      ["Con errores (columna «Errores a revisar»)", conError.length ? `${conError.length}. Mercado Libre podría rechazar los que no tienen fotos o categoría; revísalos en la sección Pendientes del visor.` : "0"],
      ["Filtros aplicados al seleccionar", describirFiltros()],
      ["", ""],
      ["Fotos", `Las columnas Imagen 1 a Imagen ${M.n_imagenes} apuntan al repositorio de GitHub (${M.url_imagenes}/<GTIN>/images/…). Solo se pueden descargar mientras el repositorio es público: hazlo público antes de importar y vuelve a hacerlo privado al terminar.`],
      ["Precio [$]", "Precio Meli Final: precio del mejor vendedor − descuento si no queda abajo del Precio Meli calculado; si no, el calculado. Si el precio queda en $299 o más, el calculado incluye el envío gratis que cobra Mercado Libre (estimado de $75 a $150 por peso, o el que editaste). Detalle en la hoja Precios."],
      ["Ajustes de precio", Object.keys(estado.ajustes).length ? `${Object.keys(estado.ajustes).length} productos con precios editados en este navegador ya van con esos precios. Para guardarlos en el repositorio usa «Exportar ajustes de precio».` : "Sin ajustes locales."],
      ["Columnas grises", "Línea de origen, Nombre en sistema, Estado de investigación y Errores a revisar son de control interno; no se suben a Mercado Libre."],
      ["Cómo importarlo", "Copia los datos a la plantilla de carga masiva que Mercado Libre da para cada categoría (o úsalo como hoja maestra), respetando la categoría de cada producto. Es el mismo contenido que layouts/mercadolibre/layout_mercadolibre.xlsx del repositorio, con valores en lugar de fórmulas."],
    ];
    XLSXSimple.descargar(nombre, [
      { nombre: "Layout Mercado Libre", columnas: cols, filas, filtro: true },
      { nombre: "Precios", columnas: colsP, filas: filasP, filtro: true },
      { nombre: "Instrucciones", columnas: [{ titulo: "Concepto", ancho: 34, formato: "texto" }, { titulo: "Detalle", ancho: 120, formato: "largo" }], filas: inst },
    ]);
    ayudaMsg = `Se descargó ${nombre} con ${ENT.format(prods.length)} productos`
      + (omitidos.length ? `; se omitieron ${ENT.format(omitidos.length)} descartados` : "")
      + (conError.length ? `; ${ENT.format(conError.length)} tienen errores (columna «Errores a revisar»)` : "")
      + ". Las URLs de fotos solo funcionan mientras el repositorio es público.";
    $("pb-ayuda").textContent = ayudaMsg;
  }

  function exportarAjustes() {
    const prods = P.filter((p) => estado.ajustes[p.gtin] || (p.param_origen && Object.keys(p.param_origen).length)).sort(comparador());
    if (!prods.length) return;
    const cols = [["Código", 16, "codigo"], ["Producto", 46, "texto"]]
      .concat(CAMPOS_PRECIO.map((c) => [c.label, 15, c.pct ? "porcentaje" : "dinero"]))
      .concat([["Precio Meli calculado", 13, "dinero"], ["Precio Meli final", 13, "dinero"], ["Origen", 26, "texto"], ["Nota", 40, "largo"]])
      .map(([titulo, ancho, formato], i) => ({ titulo, ancho, formato, aux: i >= 2 + CAMPOS_PRECIO.length && i < 4 + CAMPOS_PRECIO.length }));
    const filas = prods.map((p) => [p.gtin, p.titulo, ...CAMPOS_PRECIO.map((c) => (origenCampo(p, c.id) ? p.param[c.id] : null)),
      p.precios.precio_meli_calculado, p.precios.precio_meli_final,
      [estado.ajustes[p.gtin] ? "editado en el visor" : "", p.param_origen && Object.keys(p.param_origen).length ? "repositorio" : ""].filter(Boolean).join(" + "),
      p.ajuste_nota || ""]);
    const ahora = new Date();
    const dos = (v) => String(v).padStart(2, "0");
    const nombre = `ajustes_precios_${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}-${dos(ahora.getDate())}_${dos(ahora.getHours())}${dos(ahora.getMinutes())}.xlsx`;
    XLSXSimple.descargar(nombre, [
      { nombre: "Ajustes", columnas: cols, filas, filtro: true },
      { nombre: "Instrucciones", columnas: [{ titulo: "Concepto", ancho: 30, formato: "texto" }, { titulo: "Detalle", ancho: 120, formato: "largo" }], filas: [
        ["Exportado", ahora.toLocaleString("es-MX")],
        ["Productos", String(prods.length)],
        ["Qué es", "Parámetros de precio ajustados a mano. Celda vacía = sin ajuste: se usa el valor del sistema, el estimado (envío) o el de la API (competencia). Las columnas Precio Meli calculado y final son solo de referencia."],
        ["Comisión", "Porcentaje con IVA incluido (14% = 0.14)."],
        ["Costo de envío", "Envío gratis que Mercado Libre cobra al vendedor cuando el precio queda en $299 o más, IVA incluido."],
        ["Cómo versionarlo", "Adjunta este archivo en el chat y pide «Versiona estos ajustes de precio». Se guardan en data/ajustes_precios.json con scripts/ajustes_precios.py y entran al layout y al visor."],
      ] },
    ]);
    ayudaMsg = `Se descargó ${nombre} con ${ENT.format(prods.length)} productos ajustados. Adjúntalo en el chat para versionarlos.`;
    $("pb-ayuda").textContent = ayudaMsg;
  }

  let deshacerArmado = null;
  function deshacerAjustes() {
    const b = $("aj-deshacer");
    if (!deshacerArmado) {
      b.textContent = `¿Seguro? Deshacer ${ENT.format(Object.keys(estado.ajustes).length)}`;
      b.classList.add("peligro");
      deshacerArmado = setTimeout(() => { deshacerArmado = null; b.classList.remove("peligro"); actualizarBarra(); b.textContent = "Deshacer lo editado aquí"; }, 4000);
      return;
    }
    clearTimeout(deshacerArmado);
    deshacerArmado = null;
    b.classList.remove("peligro");
    b.textContent = "Deshacer lo editado aquí";
    const gtins = Object.keys(estado.ajustes);
    estado.ajustes = {};
    guardar("ajustes", estado.ajustes);
    gtins.forEach((g) => recalcular(porGtin.get(g)));
    render();
  }

  function render() {
    const lista = filtrados();
    resumen(lista);
    paginacion(lista.length);
    const ini = (estado.pagina - 1) * estado.porPagina;
    const pagina = lista.slice(ini, ini + estado.porPagina);
    vistaActual = { lista, pagina };
    const enPend = estado.seccion === "pendientes";
    $("vacio").hidden = lista.length > 0;
    $("vacio").textContent = estado.soloSel && !estado.sel.size
      ? "No hay productos seleccionados. Quita «Ver solo seleccionados» o selecciona alguno."
      : enPend ? "Ningún producto con pendientes coincide con los filtros. Quita alguno o usa «Limpiar todo»."
        : "Ningún producto coincide con los filtros. Quita alguno o usa «Limpiar todo».";
    const grid = estado.vista === "cuadricula";
    $("sec-catalogo").setAttribute("aria-pressed", String(!enPend));
    $("sec-pendientes").setAttribute("aria-pressed", String(enPend));
    $("vistas").hidden = enPend;
    $("accion-wrap").hidden = !enPend;
    $("exportar").hidden = !enPend;
    $("exportar").classList.toggle("btn-primario", enPend);
    $("exportar-meli").classList.toggle("btn-primario", !enPend);
    $("pb-ayuda").textContent = ayudaMsg || (enPend
      ? "Selecciona productos, elige la acción que quieres pedir (o déjala vacía y elígela por renglón en Excel), exporta los pendientes y adjunta el archivo en el chat."
      : "Selecciona productos (casillas de la lista o de las tarjetas, o «Seleccionar los N filtrados») y exporta el layout de Mercado Libre con las URLs de las fotos en GitHub. Los descartados se omiten.");
    $("vista-pend").hidden = !enPend || !lista.length;
    $("vista-grid").hidden = enPend || !grid;
    $("vista-tabla").hidden = enPend || grid || !lista.length;
    $("columnas-wrap").hidden = enPend || grid;
    $("vista-cuadricula").setAttribute("aria-pressed", String(grid));
    $("vista-lista").setAttribute("aria-pressed", String(!grid));
    $("orden-dir").textContent = estado.asc ? "↑ Ascendente" : "↓ Descendente";
    if (enPend) {
      $("vista-pend").replaceChildren(...pagina.map(filaPend));
    } else if (grid) {
      const g = $("vista-grid");
      g.replaceChildren(...pagina.map(tarjeta));
    } else {
      cabecera();
      const cols = COLUMNAS.filter((c) => !estado.ocultas.has(c.id));
      const body = $("tabla-body");
      body.replaceChildren(...pagina.map((p) => {
        const tr = document.createElement("tr");
        tr.tabIndex = 0;
        if (estado.sel.has(p.gtin)) tr.classList.add("sel");
        if (estado.ajustes[p.gtin]) tr.classList.add("editado");
        const tdSel = document.createElement("td");
        tdSel.className = "col-sel";
        tdSel.appendChild(casillaSel(p, "tsel", (on) => tr.classList.toggle("sel", on)));
        tdSel.addEventListener("click", (e) => e.stopPropagation());
        tr.appendChild(tdSel);
        cols.forEach((c) => { const td = celda(p, c); td.dataset.col = c.id; tr.appendChild(td); });
        tr.addEventListener("click", () => abrir(p.gtin));
        tr.addEventListener("keydown", (e) => { if (e.key === "Enter") abrir(p.gtin); });
        return tr;
      }));
    }
    actualizarBarra();
  }

  function aplicar() { estado.pagina = 1; render(); }

  // ---------------- Detalle ----------------
  function descripcionHTML(txt) {
    if (!txt) return '<p class="sd">Sin descripción.</p>';
    const out = [];
    let ul = null;
    txt.split("\n").forEach((linea) => {
      const l = linea.trim();
      if (!l) { ul = null; return; }
      const h = l.match(/^([A-ZÁÉÍÓÚÑ][^:]{1,40}):\s*(.*)$/);
      if (l.startsWith("- ")) {
        if (!ul) { ul = []; out.push(ul); }
        ul.push(`<li>${esc(l.slice(2))}</li>`);
        return;
      }
      ul = null;
      if (h && /^(Descripción|Beneficios|Características|Ingredientes|Composición|Fórmula|Modo de uso|Presentación|Advertencias)$/.test(h[1])) {
        if (!(out.length === 0 && h[1] === "Descripción")) out.push(`<h4>${esc(h[1])}</h4>`);
        if (h[2]) out.push(`<p>${esc(h[2])}</p>`);
      } else out.push(`<p>${esc(l)}</p>`);
    });
    return out.map((x) => (Array.isArray(x) ? `<ul>${x.join("")}</ul>` : x)).join("");
  }

  const FICHA_ETQ = {
    marca: "Marca", fabricante: "Fabricante / laboratorio", linea: "Línea", variante: "Variante / modelo", presentacion: "Presentación",
    contenido_neto: "Contenido neto", unidad_contenido: "Unidad de contenido", unidades_por_envase: "Unidades por envase",
    principio_activo: "Principio activo", concentracion: "Concentración", via_administracion: "Vía de administración",
    edad_etapa: "Edad / etapa", talla: "Talla", sabor_aroma: "Sabor / aroma", genero: "Género", tipo_piel_cabello: "Tipo de piel / cabello",
    registro_sanitario: "Registro sanitario", otros: "Otros atributos",
  };

  function similares(p) {
    const mismos = P.filter((x) => x.gtin !== p.gtin && x.categoria_id && x.categoria_id === p.categoria_id);
    let lista = mismos;
    if (lista.length < 6 && p.categoria_ruta.includes(" > ")) {
      const padre = p.categoria_ruta.split(" > ").slice(0, -1).join(" > ");
      const extra = P.filter((x) => x.gtin !== p.gtin && x.categoria_id !== p.categoria_id && x.categoria_ruta.startsWith(padre + " > "));
      lista = lista.concat(extra);
    }
    return { lista: lista.sort((a, b) => a.orden - b.orden).slice(0, 12), total: mismos.length };
  }

  const indGrande = (p) => ["descripcion", "fotos", "precios"].map((k) =>
    `<div class="ind-${p.ind[k]}"><b>${ETQ[k]}: ${p.ind[k]}</b><span>${esc(p.ind[k + "_motivo"])}</span></div>`).join("");
  const bloquePend = (p) => `<h3>Pendientes, errores y mejoras · ${ENT.format(p._pend.length)}</h3>
    ${p._pend.length ? `<ul class="plista">${p._pend.map(itemPend).join("")}</ul>` : `<p class="sd">${p.descartado ? "Producto descartado: no se revisan pendientes." : "Sin pendientes."}</p>`}`;

  function abrir(gtin) {
    const p = porGtin.get(gtin);
    if (!p) return;
    const d = $("detalle"), inner = $("det-inner");
    const pr = p.precios, inv = p.investigacion;
    const sim = similares(p);
    const ficha = Object.entries(p.ficha || {}).filter(([, v]) => v !== "" && v != null);
    inner.innerHTML = `
      <div class="det-head">
        <div>
          <h2 id="det-titulo">${esc(p.titulo)}</h2>
          <div class="det-sub">
            <span class="mono">${esc(p.gtin)}</span><button type="button" class="copiar" id="det-copiar">Copiar código</button>
            <span>${esc(p.linea)}</span>
            <span>Prioridad por ventas: #${ENT.format(p.orden)}</span>
            <span>En sistema: ${esc(p.nombre_sistema)}</span>
          </div>
        </div>
        <div class="det-acciones">
          <button type="button" class="btn" id="det-sel" aria-pressed="${estado.sel.has(p.gtin)}">${estado.sel.has(p.gtin) ? "Quitar de la selección" : "Seleccionar para exportar"}</button>
          <button type="button" class="btn det-cerrar" id="det-cerrar">Cerrar</button>
        </div>
      </div>
      ${p.descartado ? `<div class="aviso-descartado"><b>Descartado de Mercado Libre</b> el ${esc(p.descartado.fecha)}: ${esc(p.descartado.motivo)}. No entra en el layout de importación.</div>` : ""}
      <div class="ind-grande" id="det-ind">${indGrande(p)}</div>
      <div class="det-body">
        <div class="det-fotos" id="det-fotos"></div>
        <div class="det-datos">
          <section class="bloque" id="det-precios"><h3>Precios e inventario <small class="h3-nota">edita cualquier parámetro; se recalcula al salir del campo</small></h3>
            <p class="det-inv">Inventario: <b class="${p.stock > 0 ? "" : "stock-0"}">${ENT.format(p.stock)} piezas</b></p>
          </section>
          <section class="bloque"><h3>Categoría en Mercado Libre</h3><dl class="kv">
            <dt>Categoría</dt><dd>${esc(p.categoria_ruta || "Sin categoría")}</dd>
            <dt>ID de categoría</dt><dd class="mono">${esc(p.categoria_id || "—")}</dd>
            <dt>ID de catálogo</dt><dd class="mono">${esc(p.catalogo_id || "—")}</dd>
            <dt>Receta en México</dt><dd>${esc(p.receta_mx || "—")}${p.categoria_rx_sugerida ? ` · categoría con receta sugerida ${esc(p.categoria_rx_sugerida)}` : ""}</dd>
          </dl></section>
        </div>
      </div>
      <section class="bloque" id="det-pend">${bloquePend(p)}</section>
      <section class="bloque"><h3>Descripción</h3><div class="desc">${descripcionHTML(p.descripcion)}</div></section>
      <section class="bloque"><h3>Ficha técnica</h3>${ficha.length ? `<table class="ficha"><tbody>${ficha.map(([k, v]) =>
        `<tr><th scope="row">${esc(FICHA_ETQ[k] || k)}</th><td>${esc(v)}</td></tr>`).join("")}</tbody></table>` : '<p class="sd">Sin ficha técnica.</p>'}</section>
      <section class="bloque"><h3>Investigación</h3><dl class="kv">
        <dt>Estado</dt><dd>${esc(inv.estado)}${inv.confianza ? ` · confianza ${esc(inv.confianza)}` : ""}${inv.sesion ? ` · sesión ${esc(inv.sesion)}` : ""}</dd>
        <dt>Encontrado por</dt><dd>${esc(inv.encontrado_por || "—")}</dd>
      </dl>
        ${inv.notas ? `<p><b>Notas:</b> ${esc(inv.notas)}</p>` : ""}
        ${inv.notas_imagenes ? `<p><b>Notas de fotos:</b> ${esc(inv.notas_imagenes)}</p>` : ""}
        ${p.url_oficial ? `<p><b>Página oficial:</b> <a href="${esc(p.url_oficial)}" target="_blank" rel="noopener">${esc(p.url_oficial)}</a></p>` : ""}
        ${p.fuentes && p.fuentes.length ? `<ul class="fuentes">${p.fuentes.map((u) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></li>`).join("")}</ul>` : ""}
      </section>
      <section class="bloque"><h3>Productos similares · ${ENT.format(sim.total)} en la misma categoría</h3>
        ${sim.lista.length ? '<div class="similares" id="det-similares"></div>' : '<p class="sd">No hay otros productos en esta categoría.</p>'}
      </section>`;

    if (CALC && p.param) {
      $("det-precios").insertBefore(formPrecios(p, () => {
        $("det-ind").innerHTML = indGrande(p);
        $("det-pend").innerHTML = bloquePend(p);
      }), $("det-precios").querySelector(".det-inv"));
    } else {
      $("det-precios").insertAdjacentHTML("beforeend", `<p>Precio Meli final: <b>${dinero(pr.precio_meli_final)}</b></p>`);
    }

    // fotos con miniaturas
    const cont = $("det-fotos");
    const meta = document.createElement("div");
    meta.className = "foto-meta";
    let thumbs;
    const car = carrusel(p.imagenes, {
      onIndex: (i) => {
        const im = p.imagenes[i];
        if (!im) return;
        meta.innerHTML = `Foto ${i + 1} de ${p.imagenes.length} · origen ${esc(im.o || "—")} · producto de ${ENT.format(im.u)} px${im.gris ? " · posible fondo gris" : ""}${im.fuente ? ` · <a href="${esc(im.fuente)}" target="_blank" rel="noopener">fuente</a>` : ""}`;
        if (thumbs) [...thumbs.children].forEach((b, k) => b.setAttribute("aria-current", String(k === i)));
      },
    });
    cont.appendChild(car);
    if (p.imagenes.length > 1) {
      thumbs = document.createElement("div");
      thumbs.className = "thumbs";
      p.imagenes.forEach((im, k) => {
        const b = document.createElement("button");
        b.type = "button";
        b.setAttribute("aria-label", `Ver foto ${k + 1}`);
        b.setAttribute("aria-current", String(k === 0));
        b.innerHTML = `<img src="${esc(im.src)}" alt="" loading="lazy">`;
        b.addEventListener("click", () => car.ir(k));
        thumbs.appendChild(b);
      });
      cont.appendChild(thumbs);
    }
    cont.appendChild(meta);
    if (p.imagenes.length) car.ir(0); else meta.textContent = inv.notas_imagenes ? "" : "Sin fotos.";

    const simCont = $("det-similares");
    if (simCont) sim.lista.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "sim";
      b.appendChild(carrusel(s.imagenes.slice(0, 1)));
      const t = document.createElement("div");
      t.style.display = "contents";
      t.innerHTML = `<span class="t">${esc(s.titulo)}</span><span class="p">${dinero(s.precios.precio_meli_final)}</span>${indicadores(s)}`;
      b.appendChild(t);
      b.addEventListener("click", () => { abrir(s.gtin); inner.scrollTop = 0; d.scrollTop = 0; });
      simCont.appendChild(b);
    });

    $("det-cerrar").addEventListener("click", () => d.close());
    $("det-sel").addEventListener("click", (e) => {
      const on = !estado.sel.has(p.gtin);
      on ? estado.sel.add(p.gtin) : estado.sel.delete(p.gtin);
      guardarSel();
      e.currentTarget.textContent = on ? "Quitar de la selección" : "Seleccionar para exportar";
      e.currentTarget.setAttribute("aria-pressed", String(on));
      render();
    });
    $("det-copiar").addEventListener("click", (e) => {
      const btn = e.currentTarget;
      const ok = () => { btn.textContent = "Copiado"; setTimeout(() => { btn.textContent = "Copiar código"; }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(p.gtin).then(ok, () => {});
    });
    if (!d.open) d.showModal();
    d.scrollTop = 0;
    try { history.replaceState(null, "", "#p" + p.gtin); } catch (e) { /* sin historial */ }
  }

  // ---------------- Arranque ----------------
  function iniciar() {
    $("generado").textContent = DATA.generado ? `datos del ${DATA.generado}` : "sin datos: corre scripts/build_visor.py";
    const sel = $("orden");
    sel.innerHTML = ORDENES.map((o) => `<option value="${o.id}">${esc(o.label)}</option>`).join("");
    sel.value = estado.ordenId;
    sel.addEventListener("change", () => { estado.ordenId = sel.value; estado.asc = true; aplicar(); });
    $("orden-dir").addEventListener("click", () => { estado.asc = !estado.asc; aplicar(); });
    const pp = $("por-pagina");
    pp.value = String(estado.porPagina);
    pp.addEventListener("change", () => { estado.porPagina = +pp.value; guardar("porPagina", estado.porPagina); aplicar(); });
    const seccion = (s) => { estado.seccion = s; guardar("seccion", s); estado.pagina = 1; ayudaMsg = ""; render(); };
    $("sec-catalogo").addEventListener("click", () => seccion("catalogo"));
    $("sec-pendientes").addEventListener("click", () => seccion("pendientes"));
    const acc = $("accion");
    acc.innerHTML = '<option value="">Sin especificar (elegir en Excel)</option>'
      + ACCIONES.map((a) => `<option value="${esc(a.nombre)}" title="${esc(a.descripcion)}">${esc(a.nombre)}</option>`).join("");
    if (!ACCIONES.some((a) => a.nombre === estado.accion)) estado.accion = "";
    acc.value = estado.accion;
    acc.addEventListener("change", () => { estado.accion = acc.value; guardar("accion", estado.accion); });
    $("sel-filtrados").addEventListener("click", () => { vistaActual.lista.forEach((p) => estado.sel.add(p.gtin)); guardarSel(); render(); });
    $("sel-pagina").addEventListener("click", () => { vistaActual.pagina.forEach((p) => estado.sel.add(p.gtin)); guardarSel(); render(); });
    $("desel-filtrados").addEventListener("click", () => {
      vistaActual.lista.forEach((p) => estado.sel.delete(p.gtin));
      guardarSel();
      if (estado.soloSel) aplicar(); else render();
    });
    $("exportar-meli").addEventListener("click", exportarLayout);
    $("aj-exportar").addEventListener("click", exportarAjustes);
    $("aj-deshacer").addEventListener("click", deshacerAjustes);
    $("aj-ver").addEventListener("click", () => {
      const soloEd = estado.f.ajustes.size === 1 && estado.f.ajustes.has("local");
      estado.f.ajustes = soloEd ? new Set() : new Set(["local"]);
      sincronizarChecks();
      aplicar();
    });
    $("editor-precios").addEventListener("close", () => render());
    $("editor-precios").addEventListener("click", (e) => { if (e.target === $("editor-precios")) $("editor-precios").close(); });
    $("sel-quitar").addEventListener("click", () => { estado.sel.clear(); estado.soloSel = false; guardarSel(); aplicar(); });
    $("solo-sel").addEventListener("change", (e) => { estado.soloSel = e.target.checked; aplicar(); });
    $("exportar").addEventListener("click", exportar);
    const vista = (v) => { estado.vista = v; guardar("vista", v); render(); };
    $("vista-cuadricula").addEventListener("click", () => vista("cuadricula"));
    $("vista-lista").addEventListener("click", () => vista("lista"));
    $("btn-columnas").addEventListener("click", () => {
      const m = $("menu-columnas");
      m.hidden = !m.hidden;
      $("btn-columnas").setAttribute("aria-expanded", String(!m.hidden));
    });
    document.addEventListener("click", (e) => {
      if (!$("columnas-wrap").contains(e.target)) { $("menu-columnas").hidden = true; $("btn-columnas").setAttribute("aria-expanded", "false"); }
    });
    $("btn-filtros").addEventListener("click", () => {
      const f = $("panel-filtros");
      f.classList.toggle("abierto");
      $("btn-filtros").setAttribute("aria-expanded", String(f.classList.contains("abierto")));
    });
    $("detalle").addEventListener("close", () => { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* */ } render(); });
    $("detalle").addEventListener("click", (e) => { if (e.target === $("detalle")) $("detalle").close(); });
    montarFiltros();
    menuColumnas();
    render();
    const desdeHash = () => {
      const m = location.hash.match(/^#p(\d+)$/);
      if (m) abrir(m[1]);
      else if ($("detalle").open) $("detalle").close();
    };
    window.addEventListener("hashchange", desdeHash);
    desdeHash();
  }
  iniciar();
})();
