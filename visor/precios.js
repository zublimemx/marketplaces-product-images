/* Cálculo de precios de Mercado Libre en el navegador: mismas reglas que scripts/precios.py y la hoja Precios del layout.
   Se usa para recalcular en vivo cuando se editan los parámetros de un producto en el visor.
   Parámetros: precio_venta, costo_empaque, comision, costo_envio, precio_promedio_otros, precio_mejor_vendedor,
   descuento_mejor_vendedor. Constantes (costos fijos, umbral de envío gratis) en window.CATALOGO.calculo. */
(function () {
  "use strict";

  // ROUNDUP(x, 0) de Excel sin errores de punto flotante (igual que _roundup de Python)
  const roundup = (x) => Math.ceil(Number(x.toFixed(6)));
  const r2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;
  const pesos = (v) => "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function costoFijo(precio, calc) {
    for (const t of calc.costos_fijos) {
      if (precio >= t.desde && (t.hasta == null || precio < t.hasta)) return t.costo_fijo;
    }
    return 0;
  }

  function calcular(par, calc) {
    const U = calc.umbral;
    const pm = par.precio_venta + par.costo_empaque;
    const c = par.comision, envio = par.costo_envio;
    const mv = par.precio_mejor_vendedor, desc = par.descuento_mejor_vendedor;
    const conEnvio = Math.max(roundup((pm + envio) / (1 - c)), U);
    let calculado = null;
    for (const t of calc.costos_fijos.slice(0, -1)) {
      const p = roundup((pm + t.costo_fijo) / (1 - c));
      if (p < t.hasta) { calculado = p; break; }
    }
    if (calculado == null || (mv != null && mv - desc >= U)) calculado = conEnvio;
    let final = calculado;
    if (mv != null && mv - desc >= calculado) final = r2(mv - desc);
    const fijo = costoFijo(final, calc);
    const envioVendedor = final >= U ? envio : 0;
    const neto = final * (1 - c) - fijo - envioVendedor;
    return {
      precio_venta: par.precio_venta, costo_empaque: par.costo_empaque, precio_marketplaces: r2(pm), comision: c,
      costo_envio: envio, precio_meli_calculado: calculado, precio_promedio_otros: par.precio_promedio_otros,
      precio_mejor_vendedor: mv, descuento_mejor_vendedor: desc, precio_meli_final: final,
      diferencia_mejor_vendedor: mv ? final / mv - 1 : null, costo_fijo: fijo, envio_vendedor: envioVendedor,
      ingreso_neto: r2(neto), margen: r2(neto - pm),
    };
  }

  // Indicador de precios (config/indicadores.json → precios.requeridos)
  function indicador(pr, reglas) {
    const falta = Object.entries(reglas.requeridos || {}).filter(([k]) => pr[k] == null).map(([, t]) => t);
    return falta.length ? ["incompletos", "Falta: " + falta.join("; ")] : ["completos", "Se conocen los tres precios"];
  }

  // Pendientes que dependen del precio (mismos textos que pendientes() de scripts/build_visor.py)
  const CODIGOS = new Set(["sin_precio_venta", "sin_mejor_vendedor", "no_competitivo", "precio_inflado"]);
  function pendientes(pr, umbrales) {
    const out = [];
    if (!pr.precio_venta || pr.precio_venta <= 0) out.push({ c: "sin_precio_venta", d: "El catálogo del sistema no trae precio" });
    const mv = pr.precio_mejor_vendedor;
    if (mv == null) out.push({ c: "sin_mejor_vendedor", d: `Mientras no se tenga, se publica al Precio Meli calculado (${pesos(pr.precio_meli_calculado)})` });
    if (mv != null && pr.precio_meli_calculado > mv - pr.descuento_mejor_vendedor) {
      out.push({ c: "no_competitivo", d: `Calculado ${pesos(pr.precio_meli_calculado)} contra mejor vendedor ${pesos(mv)}: se publica al calculado, ${Math.round((pr.precio_meli_calculado / mv - 1) * 100)}% arriba` });
    }
    if (pr.precio_venta && pr.precio_meli_final / pr.precio_venta >= (umbrales.veces_precio_tienda || 2)) {
      out.push({ c: "precio_inflado", d: `Precio Meli final ${pesos(pr.precio_meli_final)} = ${(pr.precio_meli_final / pr.precio_venta).toFixed(1)} veces el precio de tienda (${pesos(pr.precio_venta)}) por el costo fijo de Mercado Libre; considerar kit o paquete` });
    }
    return out;
  }

  window.PreciosMeli = { calcular, indicador, pendientes, CODIGOS };
})();
