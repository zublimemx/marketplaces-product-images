/* Escritor mínimo de libros .xlsx (Office Open XML), sin dependencias, para exportar desde el visor.
   Uso: XLSXSimple.descargar("archivo.xlsx", [{ nombre, columnas: [{ titulo, ancho, formato }], filas: [[...]],
        lista: { columna, opciones }, filtro: true }])
   formato: "texto" (por omisión), "codigo" (texto que no se convierte a número), "dinero", "entero", "largo" (texto con ajuste). */
(function () {
  "use strict";
  const enc = new TextEncoder();

  // ---------- ZIP sin compresión ----------
  const TABLA = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(b) {
    let c = 0xffffffff;
    for (let i = 0; i < b.length; i++) c = TABLA[(c ^ b[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  function zip(archivos) {
    const partes = [], central = [];
    let offset = 0;
    const d = new Date();
    const hora = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1);
    const fecha = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
    archivos.forEach(({ nombre, texto }) => {
      const datos = enc.encode(texto), n = enc.encode(nombre), crc = crc32(datos);
      const lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true);
      lh.setUint16(10, hora, true); lh.setUint16(12, fecha, true); lh.setUint32(14, crc, true);
      lh.setUint32(18, datos.length, true); lh.setUint32(22, datos.length, true); lh.setUint16(26, n.length, true); lh.setUint16(28, 0, true);
      partes.push(new Uint8Array(lh.buffer), n, datos);
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true);
      ch.setUint16(12, hora, true); ch.setUint16(14, fecha, true); ch.setUint32(16, crc, true);
      ch.setUint32(20, datos.length, true); ch.setUint32(24, datos.length, true); ch.setUint16(28, n.length, true);
      ch.setUint32(42, offset, true);
      central.push(new Uint8Array(ch.buffer), n);
      offset += 30 + n.length + datos.length;
    });
    const tam = central.reduce((s, b) => s + b.length, 0);
    const fin = new DataView(new ArrayBuffer(22));
    fin.setUint32(0, 0x06054b50, true); fin.setUint16(8, archivos.length, true); fin.setUint16(10, archivos.length, true);
    fin.setUint32(12, tam, true); fin.setUint32(16, offset, true);
    return new Blob([...partes, ...central, new Uint8Array(fin.buffer)],
      { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  }

  // ---------- XML de la hoja de cálculo ----------
  const xml = (s) => String(s)
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g, "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const letra = (i) => { let s = ""; i += 1; while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); } return s; };
  const nombreHoja = (s) => String(s).replace(/[\[\]:*?\/\\]/g, " ").slice(0, 31);
  // índices de estilo (cellXfs)
  const ESTILO = { encabezado: 1, largo: 2, dinero: 3, entero: 4, texto: 5, codigo: 6 };

  function celda(ref, v, formato) {
    if (v == null || v === "") return "";
    if (typeof v === "number" && Number.isFinite(v) && formato !== "codigo" && formato !== "texto" && formato !== "largo") {
      return `<c r="${ref}" s="${ESTILO[formato] || ESTILO.entero}"><v>${v}</v></c>`;
    }
    const t = String(v).slice(0, 32000);
    return `<c r="${ref}" t="inlineStr" s="${ESTILO[formato] || ESTILO.texto}"><is><t xml:space="preserve">${xml(t)}</t></is></c>`;
  }

  function hojaXML(h) {
    const cols = h.columnas;
    const ultima = letra(cols.length - 1);
    const n = h.filas.length + 1;
    let out = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
      + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
      + `<dimension ref="A1:${ultima}${n}"/>`
      + '<sheetViews><sheetView workbookViewId="0">'
      + (h.congelar !== false ? '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' : "")
      + '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/><cols>'
      + cols.map((c, i) => `<col min="${i + 1}" max="${i + 1}" width="${c.ancho || 14}" customWidth="1"/>`).join("")
      + '</cols><sheetData>';
    out += '<row r="1">' + cols.map((c, i) => `<c r="${letra(i)}1" t="inlineStr" s="${ESTILO.encabezado}"><is><t xml:space="preserve">${xml(c.titulo)}</t></is></c>`).join("") + "</row>";
    h.filas.forEach((f, k) => {
      const r = k + 2;
      out += `<row r="${r}">` + cols.map((c, i) => celda(`${letra(i)}${r}`, f[i], c.formato)).join("") + "</row>";
    });
    out += "</sheetData>";
    if (h.filtro && h.filas.length) out += `<autoFilter ref="A1:${ultima}${n}"/>`;
    if (h.lista && h.filas.length) {
      const col = letra(h.lista.columna);
      out += `<dataValidations count="1"><dataValidation type="list" allowBlank="1" showErrorMessage="1" errorTitle="Acción no válida" error="Elige una acción de la lista" sqref="${col}2:${col}${n}"><formula1>${xml('"' + h.lista.opciones.join(",") + '"')}</formula1></dataValidation></dataValidations>`;
    }
    return out + "</worksheet>";
  }

  const ESTILOS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    + '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    + '<numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/></numFmts>'
    + '<fonts count="2"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font><font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts>'
    + '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    + '<fill><patternFill patternType="solid"><fgColor rgb="FFDCE6F2"/><bgColor indexed="64"/></patternFill></fill></fills>'
    + '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    + '<cellXfs count="7">'
    + '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    + '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'
    + '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
    + '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>'
    + '<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>'
    + '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top"/></xf>'
    + '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>'
    + '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';

  function libro(hojas) {
    const nombres = hojas.map((h) => nombreHoja(h.nombre));
    const archivos = [
      { nombre: "[Content_Types].xml", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        + '<Default Extension="xml" ContentType="application/xml"/>'
        + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + hojas.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("")
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "</Types>" },
      { nombre: "_rels/.rels", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        + "</Relationships>" },
      { nombre: "xl/workbook.xml", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        + '<bookViews><workbookView/></bookViews><sheets>'
        + nombres.map((nm, i) => `<sheet name="${xml(nm)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("")
        + "</sheets>"
        + (() => {
          const defs = hojas.map((h, i) => (h.filtro && h.filas.length
            ? `<definedName name="_xlnm._FilterDatabase" localSheetId="${i}" hidden="1">'${xml(nombres[i].replace(/'/g, "''"))}'!$A$1:$${letra(h.columnas.length - 1)}$${h.filas.length + 1}</definedName>`
            : "")).join("");
          return defs ? `<definedNames>${defs}</definedNames>` : "";
        })()
        + "</workbook>" },
      { nombre: "xl/_rels/workbook.xml.rels", texto: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + hojas.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("")
        + `<Relationship Id="rId${hojas.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>`
        + "</Relationships>" },
      { nombre: "xl/styles.xml", texto: ESTILOS },
      ...hojas.map((h, i) => ({ nombre: `xl/worksheets/sheet${i + 1}.xml`, texto: hojaXML(h) })),
    ];
    return zip(archivos);
  }

  function descargar(nombreArchivo, hojas) {
    const blob = libro(hojas);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nombreArchivo;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
    return blob;
  }

  window.XLSXSimple = { libro, descargar };
})();
