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
    { id: "precio_venta", label: "Precio venta", sort: (p) => p.precios.precio_venta, num: true, money: true },
    { id: "precio_marketplaces", label: "Precio marketplaces", sort: (p) => p.precios.precio_marketplaces, num: true, money: true },
    { id: "precio_meli_calculado", label: "Precio Meli calculado", sort: (p) => p.precios.precio_meli_calculado, num: true, money: true },
    { id: "precio_promedio_otros", label: "Promedio otros vendedores", sort: (p) => p.precios.precio_promedio_otros, num: true, money: true },
    { id: "precio_mejor_vendedor", label: "Precio mejor vendedor", sort: (p) => p.precios.precio_mejor_vendedor, num: true, money: true },
    { id: "precio_meli_final", label: "Precio Meli final", sort: (p) => p.precios.precio_meli_final, num: true, money: true },
    { id: "ind_descripcion", label: "Descripción", sort: (p) => RANGO[p.ind.descripcion] },
    { id: "ind_fotos", label: "Calidad de fotos", sort: (p) => RANGO[p.ind.fotos] },
    { id: "ind_precios", label: "Precios", sort: (p) => RANGO[p.ind.precios] },
  ];
  const ORDENES = [
    { id: "orden", label: "Prioridad por ventas", sort: (p) => p.orden },
    ...COLUMNAS.filter((c) => c.sort),
  ];
  const estado = {
    vista: leer("vista", "cuadricula"),
    ordenId: "orden",
    asc: true,
    pagina: 1,
    porPagina: leer("porPagina", 48),
    ocultas: new Set(leer("ocultas", ["linea", "precio_marketplaces"])),
    f: { nombre: [], codigo: [], categoria: [], linea: new Set(), stock: new Set(), descripcion: new Set(), fotos: new Set(), precios: new Set() },
  };

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
    return true;
  }
  function filtrados() {
    const o = ORDENES.find((x) => x.id === estado.ordenId) || ORDENES[0];
    const dir = estado.asc ? 1 : -1;
    return P.filter((p) => coincide(p)).sort((a, b) => {
      const va = o.sort(a), vb = o.sort(b);
      if (va == null && vb == null) return a.orden - b.orden;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (va < vb) return -dir;
      if (va > vb) return dir;
      return a.orden - b.orden;
    });
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
    $("limpiar").addEventListener("click", () => {
      Object.keys(estado.f).forEach((k) => { estado.f[k] = Array.isArray(estado.f[k]) ? [] : new Set(); });
      Object.values(MS).forEach((m) => m.chips());
      document.querySelectorAll("#panel-filtros input[type=checkbox]").forEach((c) => { c.checked = false; });
      aplicar();
    });
    $("reglas-texto").innerHTML = textoReglas();
  }

  function grupoToggles(idCont, clave, opciones) {
    const fs = $(idCont);
    opciones.forEach(([v, txt]) => {
      const lab = document.createElement("label");
      lab.className = "toggle";
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
    const stockTotal = lista.reduce((s, p) => s + p.stock, 0);
    const sinStock = lista.filter((p) => p.stock <= 0).length;
    $("resumen-grupos").innerHTML = grupos.map(([k, t, vals]) => {
      const c = contar(lista.map((p) => p.ind[k]));
      return `<div class="res-grupo"><span>${t}</span>${vals.map((v) =>
        `<button type="button" class="res-chip ind-${v}" data-k="${k}" data-v="${v}" aria-pressed="${estado.f[k].has(v)}">${v} <b>${ENT.format(c.get(v) || 0)}</b></button>`).join("")}</div>`;
    }).join("") + `<div class="res-grupo"><span>Inventario</span><span class="res-chip">${ENT.format(stockTotal)} piezas</span><button type="button" class="res-chip ind-mala" data-k="stock" data-v="sin" aria-pressed="${estado.f.stock.has("sin")}">sin existencia <b>${ENT.format(sinStock)}</b></button></div>`;
    $("resumen-grupos").querySelectorAll("button[data-k]").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.k, v = b.dataset.v;
      estado.f[k].has(v) ? estado.f[k].delete(v) : estado.f[k].add(v);
      const cb = document.querySelector(`#panel-filtros input[id$="-${v}"][id^="f-${k === "stock" ? "stock" : "ind-" + k}"]`);
      if (cb) cb.checked = estado.f[k].has(v);
      aplicar();
    }));
    // conteos de cada opción considerando los demás filtros
    const claves = { linea: (p) => p.linea, stock: (p) => (p.stock > 0 ? "con" : "sin"), descripcion: (p) => p.ind.descripcion, fotos: (p) => p.ind.fotos, precios: (p) => p.ind.precios };
    Object.entries(claves).forEach(([k, fn]) => {
      const c = contar(P.filter((p) => coincide(p, k)).map(fn));
      document.querySelectorAll(`[data-cuenta^="${k}:"]`).forEach((el) => { el.textContent = ENT.format(c.get(el.dataset.cuenta.split(":")[1]) || 0); });
    });
  }

  // ---------------- Vistas ----------------
  function tarjeta(p) {
    const el = document.createElement("article");
    el.className = "card";
    el.tabIndex = 0;
    el.setAttribute("aria-label", p.titulo);
    el.appendChild(carrusel(p.imagenes));
    const info = document.createElement("div");
    info.style.display = "contents";
    info.innerHTML = `
      <div class="meta"><span class="mono">${esc(p.gtin)}</span><span class="${p.stock > 0 ? "" : "stock-0"}">${ENT.format(p.stock)} pzas</span></div>
      <h3>${esc(p.titulo)}</h3>
      <div class="cat" title="${esc(p.categoria_ruta)}">${esc(p.categoria)}</div>
      <div class="precio"><strong>${dinero(p.precios.precio_meli_final)}</strong><small>venta ${dinero(p.precios.precio_venta)}</small></div>
      ${indicadores(p)}`;
    el.appendChild(info);
    el.addEventListener("click", () => abrir(p.gtin));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter") abrir(p.gtin); });
    return el;
  }

  function celda(p, c) {
    const td = document.createElement("td");
    if (c.num) td.className = "num";
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
      default: td.innerHTML = dinero(p.precios[c.id]);
    }
    return td;
  }

  function cabecera() {
    const tr = $("tabla-head");
    tr.innerHTML = "";
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
      guardar("ocultas", [...estado.ocultas]);
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

  function render() {
    const lista = filtrados();
    resumen(lista);
    paginacion(lista.length);
    const ini = (estado.pagina - 1) * estado.porPagina;
    const pagina = lista.slice(ini, ini + estado.porPagina);
    $("vacio").hidden = lista.length > 0;
    const grid = estado.vista === "cuadricula";
    $("vista-grid").hidden = !grid;
    $("vista-tabla").hidden = grid || !lista.length;
    $("columnas-wrap").hidden = grid;
    $("vista-cuadricula").setAttribute("aria-pressed", String(grid));
    $("vista-lista").setAttribute("aria-pressed", String(!grid));
    $("orden-dir").textContent = estado.asc ? "↑ Ascendente" : "↓ Descendente";
    if (grid) {
      const g = $("vista-grid");
      g.replaceChildren(...pagina.map(tarjeta));
    } else {
      cabecera();
      const cols = COLUMNAS.filter((c) => !estado.ocultas.has(c.id));
      const body = $("tabla-body");
      body.replaceChildren(...pagina.map((p) => {
        const tr = document.createElement("tr");
        tr.tabIndex = 0;
        cols.forEach((c) => tr.appendChild(celda(p, c)));
        tr.addEventListener("click", () => abrir(p.gtin));
        tr.addEventListener("keydown", (e) => { if (e.key === "Enter") abrir(p.gtin); });
        return tr;
      }));
    }
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
        <button type="button" class="btn det-cerrar" id="det-cerrar">Cerrar</button>
      </div>
      <div class="ind-grande">${["descripcion", "fotos", "precios"].map((k) =>
        `<div class="ind-${p.ind[k]}"><b>${ETQ[k]}: ${p.ind[k]}</b><span>${esc(p.ind[k + "_motivo"])}</span></div>`).join("")}</div>
      <div class="det-body">
        <div class="det-fotos" id="det-fotos"></div>
        <div class="det-datos">
          <section class="bloque"><h3>Precios e inventario</h3><dl class="kv">
            <dt>Precio de venta (IVA incluido)</dt><dd>${dinero(pr.precio_venta)}</dd>
            <dt>Precio de venta marketplaces (+ empaque y logística)</dt><dd>${dinero(pr.precio_marketplaces)}</dd>
            <dt>Comisión Meli (Clásica)</dt><dd>${PCT.format(pr.comision)}</dd>
            <dt>Precio Meli calculado</dt><dd>${dinero(pr.precio_meli_calculado)}</dd>
            <dt>Promedio otros vendedores</dt><dd>${dinero(pr.precio_promedio_otros)}</dd>
            <dt>Precio mejor vendedor${p.metodo_mejor_vendedor ? ` (${esc(p.metodo_mejor_vendedor)})` : ""}</dt><dd>${dinero(pr.precio_mejor_vendedor)}</dd>
            <dt class="fuerte">Precio Meli final</dt><dd class="fuerte">${dinero(pr.precio_meli_final)}</dd>
            <dt>Diferencia contra mejor vendedor</dt><dd>${pr.diferencia_mejor_vendedor == null ? '<span class="sd">sin dato</span>' : PCT.format(pr.diferencia_mejor_vendedor)}</dd>
            <dt>Costo fijo Meli / envío a cargo del vendedor</dt><dd>${dinero(pr.costo_fijo)} / ${dinero(pr.envio_vendedor)}</dd>
            <dt>Ingreso neto estimado</dt><dd>${dinero(pr.ingreso_neto)}</dd>
            <dt>Inventario</dt><dd class="${p.stock > 0 ? "" : "stock-0"}">${ENT.format(p.stock)} piezas</dd>
          </dl></section>
          <section class="bloque"><h3>Categoría en Mercado Libre</h3><dl class="kv">
            <dt>Categoría</dt><dd>${esc(p.categoria_ruta || "Sin categoría")}</dd>
            <dt>ID de categoría</dt><dd class="mono">${esc(p.categoria_id || "—")}</dd>
            <dt>ID de catálogo</dt><dd class="mono">${esc(p.catalogo_id || "—")}</dd>
            <dt>Receta en México</dt><dd>${esc(p.receta_mx || "—")}${p.categoria_rx_sugerida ? ` · categoría con receta sugerida ${esc(p.categoria_rx_sugerida)}` : ""}</dd>
          </dl></section>
        </div>
      </div>
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
    $("detalle").addEventListener("close", () => { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* */ } });
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
