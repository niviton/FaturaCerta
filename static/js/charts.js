/* FaturaCerta · gráficos (Apache ECharts + Leaflet), sem dependências além delas.
   Uso no HTML:  <div data-chart="tipo" data-fonte="id"></div>  +  {{ dados|json_script:"id" }}
   Os dados vêm de apps/core/charts.py. O ECharts (e o Leaflet, no mapa) só é baixado se a página tiver gráfico.
   Tema montado a partir dos tokens CSS; troca junto com o tema da página. */
(function () {
  "use strict";
  var STATIC = (document.currentScript && document.currentScript.src.split("/js/")[0]) || "/static";
  var reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var instancias = new Map(); // elemento -> {grafico, mapa, observador}
  var carregando = {};

  function carregarScript(src) {
    if (!carregando[src]) {
      carregando[src] = new Promise(function (ok, erro) {
        var s = document.createElement("script");
        s.src = src; s.onload = ok; s.onerror = erro; document.head.appendChild(s);
      });
    }
    return carregando[src];
  }
  function carregarCss(href) {
    if (document.querySelector('link[href="' + href + '"]')) return;
    var l = document.createElement("link"); l.rel = "stylesheet"; l.href = href; document.head.appendChild(l);
  }

  /* ---------------------------------------------------------------- tokens e formatação */
  function tokens() {
    var cs = getComputedStyle(document.documentElement);
    var v = function (n) { return cs.getPropertyValue(n).trim(); };
    return {
      text: v("--text"), muted: v("--muted"), faint: v("--faint"), border: v("--border"), surface: v("--surface"),
      surface2: v("--surface-2"), glass: v("--glass"), accent: v("--accent"), brand: v("--brand"), solar: v("--solar"),
      danger: v("--danger"), ok: v("--ok"), escuro: document.documentElement.dataset.theme !== "light",
      cat: [1, 2, 3, 4, 5, 6, 7, 8].map(function (i) { return v("--c" + i); }),
      fonte: v("--font") || "Geist, sans-serif"
    };
  }
  function tom(t, nome) {
    return { solar: t.solar, ok: t.ok, brand: t.brand, danger: t.danger, accent: t.accent, neutro: t.cat[5] }[nome] || t.brand;
  }
  function rgba(hex, a) {
    if (!hex || hex[0] !== "#") return hex;
    var h = hex.length === 4 ? hex.replace(/#(.)(.)(.)/, "#$1$1$2$2$3$3") : hex;
    return "rgba(" + parseInt(h.substr(1, 2), 16) + "," + parseInt(h.substr(3, 2), 16) + "," + parseInt(h.substr(5, 2), 16) + "," + a + ")";
  }
  function grad(cor, topo, base, horizontal) {
    return new echarts.graphic.LinearGradient(0, 0, horizontal ? 1 : 0, horizontal ? 0 : 1,
      [{ offset: 0, color: rgba(cor, horizontal ? base : topo) }, { offset: 1, color: rgba(cor, horizontal ? topo : base) }]);
  }
  function num(v, casas) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }).format(v);
  }
  function fmt(d, v, casas) {
    var c = casas === undefined ? d.casas : casas;
    if (d.unidade === "R$") return "R$ " + num(v, c === undefined ? 2 : c);
    return num(v, c || 0) + (d.unidade ? " " + d.unidade : "");
  }

  /* ---------------------------------------------------------------- base comum */
  function base(t, d) {
    return {
      backgroundColor: "transparent",
      textStyle: { fontFamily: t.fonte, color: t.muted },
      animation: !reduzido, animationDuration: 700, animationEasing: "cubicOut",
      aria: { enabled: true },
      tooltip: {
        trigger: "axis", confine: true,
        backgroundColor: t.glass, borderColor: rgba(t.text, 0.12), borderWidth: 1, padding: [10, 12],
        textStyle: { color: t.text, fontFamily: t.fonte, fontSize: 12 },
        extraCssText: "backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-radius:12px;" +
          "box-shadow:0 18px 40px -16px rgba(0,0,0,.6);",
        axisPointer: { type: "line", lineStyle: { color: rgba(t.text, 0.35), type: "dashed", width: 1 } }
      },
      grid: { left: 8, right: 12, top: 28, bottom: 4, containLabel: true }
    };
  }
  function eixoCat(t, rotulos, extra) {
    return Object.assign({ type: "category", data: rotulos, boundaryGap: true,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: t.muted, fontSize: 11, hideOverlap: true, margin: 12 } }, extra || {});
  }
  function eixoValor(t, d, extra) {
    return Object.assign({ type: "value", axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: rgba(t.text, t.escuro ? 0.05 : 0.07) } },
      axisLabel: { color: t.muted, fontSize: 11, formatter: function (v) { return num(v, 0); } } }, extra || {});
  }
  function linhasTooltip(d, params) {
    var p = Array.isArray(params) ? params : [params];
    var html = '<div style="font-weight:600;margin-bottom:6px">' + p[0].axisValueLabel + "</div>";
    p.forEach(function (x) {
      if (x.seriesName.charAt(0) === "_" || x.value === null || x.value === undefined || x.value === "-") return;
      html += '<div style="display:flex;gap:10px;align-items:center;justify-content:space-between;min-width:170px">' +
        '<span style="display:flex;gap:6px;align-items:center"><span style="width:8px;height:8px;border-radius:3px;background:' +
        (typeof x.color === "string" ? x.color : (x.color.colorStops ? x.color.colorStops[0].color : "#888")) +
        '"></span>' + x.seriesName + '</span><b style="font-variant-numeric:tabular-nums">' + fmt(d, x.value) + "</b></div>";
    });
    return html;
  }

  /* ---------------------------------------------------------------- 1. sankey */
  function sankey(t, d, el) {
    var cores = {};
    var estreito = el && el.clientWidth < 560; // no celular o fluxo desce de cima para baixo
    d.nos.forEach(function (n) { cores[n.nome] = tom(t, n.tom); });
    return Object.assign(base(t, d), {
      tooltip: Object.assign(base(t, d).tooltip, { trigger: "item", formatter: function (p) {
        return p.dataType === "edge" ? p.data.source + " → " + p.data.target + "<br><b>" + fmt(d, p.value) + "</b>"
          : p.name + "<br><b>" + fmt(d, p.value) + "</b>"; } }),
      series: [{
        type: "sankey", draggable: false, nodeAlign: "left", layoutIterations: 64,
        orient: estreito ? "vertical" : "horizontal",
        left: estreito ? 8 : 4, right: estreito ? 8 : 150, top: estreito ? 6 : 10, bottom: estreito ? 46 : 10,
        nodeWidth: estreito ? 10 : 12, nodeGap: estreito ? 28 : 22,
        emphasis: { focus: "adjacency" },
        data: d.nos.map(function (n) { return { name: n.nome, itemStyle: { color: cores[n.nome], borderWidth: 0, borderRadius: 4 } }; }),
        links: d.links.map(function (l) {
          var destino = cores[l.para];
          return { source: l.de, target: l.para, value: l.valor,
            lineStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: rgba(cores[l.de], 0.32) }, { offset: 1, color: rgba(destino, l.para === "Não compensado" ? 0.7 : 0.38) }]),
              opacity: 1, curveness: 0.5 } };
        }),
        label: { color: t.text, fontSize: 12, fontFamily: t.fonte, position: estreito ? "bottom" : "right",
          formatter: function (p) { return "{n|" + p.name + "}\n{v|" + fmt(d, p.value) + "}"; },
          rich: { n: { color: t.muted, fontSize: 11, lineHeight: 16 }, v: { color: t.text, fontSize: 14, fontWeight: 600, lineHeight: 18 } } }
      }]
    });
  }

  /* ---------------------------------------------------------------- 2. geração × esperado */
  function geracao(t, d, el) {
    var periodo = el.dataset.periodo || d.padrao;
    var p = d.periodos[periodo];
    var faixa = p.max.map(function (mx, i) { return mx - p.min[i]; });
    var abaixo = p.gerado.map(function (g, i) { return g < p.min[i] ? g : null; });
    return Object.assign(base(t, d), {
      tooltip: Object.assign(base(t, d).tooltip, { formatter: function (ps) {
        var i = ps[0].dataIndex;
        return '<div style="font-weight:600;margin-bottom:6px">' + p.rotulos[i] + "</div>" +
          "Gerado <b style='float:right;margin-left:16px'>" + fmt(d, p.gerado[i]) + "</b><br>" +
          "Esperado <b style='float:right;margin-left:16px'>" + fmt(d, p.esperado[i]) + "</b><br>" +
          "<span style='color:" + t.muted + "'>Faixa " + num(p.min[i], 0) + " a " + num(p.max[i], 0) + "</span>" +
          (abaixo[i] !== null ? "<br><span style='color:" + t.danger + "'>Abaixo do esperado</span>" : ""); } }),
      xAxis: eixoCat(t, p.rotulos, { boundaryGap: false }),
      yAxis: eixoValor(t, d),
      series: [
        { name: "_min", type: "line", data: p.min, stack: "faixa", symbol: "none", lineStyle: { opacity: 0 }, silent: true },
        { name: "_faixa", type: "line", data: faixa, stack: "faixa", symbol: "none", lineStyle: { opacity: 0 }, silent: true,
          areaStyle: { color: rgba(t.text, t.escuro ? 0.07 : 0.06) } },
        { name: "Esperado", type: "line", data: p.esperado, symbol: "none", smooth: true,
          lineStyle: { color: rgba(t.text, 0.45), width: 1, type: "dashed" } },
        { name: "Gerado", type: "line", data: p.gerado, smooth: 0.35, symbol: "circle", symbolSize: 5, showSymbol: false,
          lineStyle: { color: t.solar, width: 2.5 }, itemStyle: { color: t.solar },
          areaStyle: { color: grad(t.solar, 0.32, 0) } },
        { name: "_abaixo", type: "scatter", data: abaixo, symbolSize: 9,
          itemStyle: { color: t.danger, borderColor: t.surface, borderWidth: 2 }, z: 5 }
      ]
    });
  }

  /* ---------------------------------------------------------------- 3. barras agrupadas */
  function barrasAgrupadas(t, d) {
    var destacar = {};
    (d.anotacoes || []).forEach(function (a) { destacar[a.indice] = a.texto; });
    var series = d.series.map(function (s, k) {
      var c = tom(t, s.tom);
      var serie = { name: s.nome, type: "bar", data: s.valores, barMaxWidth: 16, barGap: "25%",
        itemStyle: { color: grad(c, 1, 0.35), borderRadius: [6, 6, 2, 2] }, emphasis: { focus: "series" } };
      if (k === d.series.length - 1 && d.anotacoes.length) {
        serie.markPoint = { symbol: "pin", symbolSize: 1, data: d.anotacoes.map(function (a) {
          return { coord: [a.indice, Math.max.apply(null, d.series.map(function (x) { return x.valores[a.indice]; }))],
            value: a.texto, label: { show: true, position: "top", distance: 8, formatter: a.texto, color: t.danger,
              fontWeight: 600, fontSize: 11, backgroundColor: rgba(t.danger, 0.14), padding: [3, 6], borderRadius: 6 } }; }) };
        serie.markArea = { silent: true, itemStyle: { color: rgba(t.danger, 0.06) },
          data: d.anotacoes.map(function (a) { return [{ xAxis: a.indice }, { xAxis: a.indice }]; }) };
      }
      return serie;
    });
    return Object.assign(base(t, d), {
      legend: { top: 0, right: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: t.muted } },
      grid: { left: 8, right: 36, top: 52, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t, d).tooltip, { axisPointer: { type: "shadow", shadowStyle: { color: rgba(t.text, 0.04) } },
        formatter: function (ps) { var i = ps[0].dataIndex;
          return linhasTooltip(d, ps) + (destacar[i] ? "<div style='color:" + t.danger + ";margin-top:6px'>Perdido: " + destacar[i] + "</div>" : ""); } }),
      xAxis: eixoCat(t, d.rotulos), yAxis: eixoValor(t, d), series: series
    });
  }

  /* ---------------------------------------------------------------- 4. cascata */
  function cascata(t, d, el) {
    var estreito = el && el.clientWidth < 520;
    var acumulado = 0, invisivel = [], visivel = [], cores = [], rotulos = [];
    d.itens.forEach(function (it, i) {
      rotulos.push(it.curto || it.rotulo);
      if (it.tipo === "total") {
        invisivel.push(0); visivel.push(it.valor); acumulado = it.valor;
        cores.push(i === 0 ? t.brand : t.accent);
      } else if (it.tipo === "menos") {
        acumulado -= it.valor; invisivel.push(acumulado); visivel.push(it.valor); cores.push(t.ok);
      } else {
        invisivel.push(acumulado); visivel.push(it.valor); acumulado += it.valor; cores.push(it.rotulo.indexOf("Fio B") >= 0 ? t.danger : t.solar);
      }
    });
    return Object.assign(base(t, d), {
      tooltip: Object.assign(base(t, d).tooltip, { axisPointer: { type: "shadow", shadowStyle: { color: rgba(t.text, 0.04) } },
        formatter: function (ps) { var i = ps[0].dataIndex, it = d.itens[i];
          var sinal = it.tipo === "menos" ? "− " : it.tipo === "mais" ? "+ " : "";
          return "<b>" + it.rotulo + "</b><br>" + sinal + fmt(d, it.valor); } }),
      grid: { left: 8, right: 12, top: 30, bottom: 4, containLabel: true },
      xAxis: eixoCat(t, rotulos, { axisLabel: { color: t.muted, fontSize: estreito ? 9 : 11, interval: 0, rotate: estreito ? 35 : 0,
        width: estreito ? 64 : 70, overflow: estreito ? "truncate" : "break", lineHeight: 14 } }),
      yAxis: eixoValor(t, d, { axisLabel: { color: t.muted, fontSize: 11, formatter: function (v) { return "R$ " + num(v, 0); } } }),
      series: [
        { name: "_base", type: "bar", stack: "c", data: invisivel, itemStyle: { color: "transparent" }, silent: true, barMaxWidth: 46 },
        { name: "Valor", type: "bar", stack: "c", barMaxWidth: 46,
          data: visivel.map(function (v, i) { return { value: v, itemStyle: { color: grad(cores[i], 1, 0.55), borderRadius: 6 } }; }),
          label: { show: true, position: "top", color: t.text, fontSize: estreito ? 9 : 11, fontWeight: 600,
            formatter: function (p) { var it = d.itens[p.dataIndex];
              return (it.tipo === "menos" ? "−" : it.tipo === "mais" ? "+" : "") + "R$ " + num(it.valor, 0); } } }
      ]
    });
  }

  /* ---------------------------------------------------------------- 5. anéis de desempenho */
  function aneis(t, d, el) {
    var n = d.itens.length;
    var largura = (el && el.clientWidth) || 600, altura = (el && el.clientHeight) || 200;
    var colunas = largura / n >= 120 ? n : Math.min(n, 2); // sem espaço, os anéis vão para 2 colunas
    var linhas = Math.ceil(n / colunas);
    var raio = Math.max(Math.min(largura / colunas / 2 - 14, altura / linhas / 2 - 22, 64), 26);
    var fonte = raio < 40 ? 13 : raio < 52 ? 16 : 18;
    return Object.assign(base(t, d), {
      tooltip: { show: false },
      series: d.itens.map(function (it, i) {
        var c = it.pct >= 85 ? t.ok : it.pct >= 60 ? t.solar : t.danger;
        var col = i % colunas, lin = Math.floor(i / colunas);
        return {
          type: "gauge", startAngle: 90, endAngle: -270, min: 0, max: 100, radius: raio,
          center: [((col + 0.5) / colunas * 100) + "%", ((lin + 0.42) / linhas * 100) + "%"], pointer: { show: false },
          progress: { show: true, roundCap: true, width: 9,
            itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [{ offset: 0, color: rgba(c, 0.55) }, { offset: 1, color: c }]) } },
          axisLine: { roundCap: true, lineStyle: { width: 9, color: [[1, rgba(t.text, t.escuro ? 0.07 : 0.08)]] } },
          splitLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false },
          title: { show: true, offsetCenter: [0, raio + 14], color: t.muted, fontSize: 12, fontFamily: t.fonte },
          detail: { offsetCenter: [0, 0], fontSize: fonte, fontWeight: 650, color: t.text, fontFamily: t.fonte,
            formatter: function (v) { return num(v, 0) + "%"; } },
          data: [{ value: it.pct, name: it.rotulo }]
        };
      })
    });
  }

  /* ---------------------------------------------------------------- 6. calendário de calor */
  function calendario(t, d, el) {
    var max = d.max || 1;
    var largura = el.clientWidth || 800;
    var semanas = largura < 640 ? 26 : 53; // no celular, os últimos 6 meses
    var inicio = d.inicio, dias = d.dias;
    if (semanas < 53) {
      var corte = new Date(d.fim); corte.setDate(corte.getDate() - semanas * 7 + 1);
      inicio = corte.toISOString().slice(0, 10);
      dias = d.dias.filter(function (x) { return x[0] >= inicio; });
    }
    var celula = Math.max(Math.min(Math.floor((largura - 50) / (semanas + 1)), 16), 8);
    return Object.assign(base(t, d), {
      tooltip: Object.assign(base(t, d).tooltip, { trigger: "item", formatter: function (p) {
        var dt = p.value[0].split("-"); return dt[2] + "/" + dt[1] + "/" + dt[0] + "<br><b>" +
          (p.value[1] === 0 ? "<span style='color:" + t.danger + "'>sem geração</span>" : fmt(d, p.value[1])) + "</b>"; } }),
      visualMap: { type: "piecewise", show: true, orient: "horizontal", left: "right", top: 0, itemWidth: 12, itemHeight: 12,
        itemGap: 6, textStyle: { color: t.muted, fontSize: 11 }, itemSymbol: "roundRect",
        pieces: [
          { value: 0, color: t.danger, label: "sem geração" },
          { gt: 0, lte: max * 0.55, color: rgba(t.solar, 0.22), label: "baixa" },
          { gt: max * 0.55, lte: max * 0.75, color: rgba(t.solar, 0.5), label: " " },
          { gt: max * 0.75, lte: max * 0.9, color: rgba(t.solar, 0.75), label: " " },
          { gt: max * 0.9, color: t.solar, label: "alta" }] },
      calendar: { range: [inicio, d.fim], top: 44, left: semanas === 53 ? 34 : 8, right: 8, cellSize: [celula, celula],
        splitLine: { show: false }, itemStyle: { color: "transparent", borderColor: t.surface, borderWidth: 2.5 },
        dayLabel: { show: semanas === 53, firstDay: 0, nameMap: ["D", "S", "T", "Q", "Q", "S", "S"], color: t.muted, fontSize: 10 },
        monthLabel: { nameMap: ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"], color: t.muted, fontSize: 11 },
        yearLabel: { show: false } },
      series: [{ type: "heatmap", coordinateSystem: "calendar", data: dias,
        itemStyle: { borderRadius: 3, borderColor: t.surface, borderWidth: 2 } }]
    });
  }

  /* ---------------------------------------------------------------- 7. rosca */
  function rosca(t, d) {
    var total = d.itens.reduce(function (s, i) { return s + i.valor; }, 0);
    return Object.assign(base(t, d), {
      color: t.cat,
      tooltip: Object.assign(base(t, d).tooltip, { trigger: "item",
        formatter: function (p) { return p.name + "<br><b>" + fmt(d, p.value) + "</b> · " + num(p.percent, 1) + "%"; } }),
      title: { text: num(total, d.casas), subtext: d.centro, left: "center", top: "43%", itemGap: 2,
        textStyle: { color: t.text, fontSize: 22, fontWeight: 650, fontFamily: t.fonte },
        subtextStyle: { color: t.muted, fontSize: 12, fontFamily: t.fonte } },
      series: [{ type: "pie", radius: ["44%", "62%"], center: ["50%", "52%"], padAngle: 1.5, minAngle: 4,
        itemStyle: { borderRadius: 6, borderColor: t.surface, borderWidth: 2 },
        avoidLabelOverlap: true,
        label: { show: true, color: t.text, fontSize: 12, fontFamily: t.fonte, overflow: "none", minMargin: 4,
          formatter: function (p) { return "{n|" + p.name + "}\n{p|" + num(p.percent, 0) + "%}"; },
          rich: { n: { color: t.muted, fontSize: 11, lineHeight: 15 }, p: { color: t.text, fontSize: 13, fontWeight: 600, lineHeight: 17 } } },
        labelLine: { length: 10, length2: 8, lineStyle: { color: rgba(t.text, 0.25) } },
        emphasis: { scaleSize: 4 },
        data: d.itens.map(function (i) { return { name: i.nome, value: i.valor }; }) }]
    });
  }

  /* ---------------------------------------------------------------- 8. ranking */
  function ranking(t, d) {
    var itens = d.itens.slice().reverse(); // ECharts desenha de baixo para cima
    return Object.assign(base(t, d), {
      grid: { left: 8, right: 70, top: 4, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t, d).tooltip, { axisPointer: { type: "shadow", shadowStyle: { color: rgba(t.text, 0.04) } },
        formatter: function (ps) { return ps[0].name + "<br><b>" + fmt(d, ps[0].value) + "</b>"; } }),
      xAxis: eixoValor(t, d, { show: false }),
      yAxis: eixoCat(t, itens.map(function (i) { return i.nome; }), { axisLabel: { color: t.text, fontSize: 12, margin: 12 } }),
      series: [{ type: "bar", barMaxWidth: 18, barCategoryGap: "38%",
        data: itens.map(function (it, i) {
          var c = it.cor || (it.tom ? tom(t, it.tom) : t.cat[(itens.length - 1 - i) % t.cat.length]);
          return { value: it.valor, itemStyle: { color: grad(c, 1, 0.45, true), borderRadius: [4, 8, 8, 4] } }; }),
        label: { show: true, position: "right", distance: 8, color: t.text, fontWeight: 600, fontSize: 12,
          formatter: function (p) { return fmt(d, p.value); } },
        showBackground: true, backgroundStyle: { color: rgba(t.text, t.escuro ? 0.03 : 0.04), borderRadius: 8 } }]
    });
  }

  /* ---------------------------------------------------------------- 9. bullet de demanda */
  function bullet(t, d) {
    var c = d.contratada, tol = c * (1 + d.tolerancia);
    var dentro = d.medida.map(function (m) { return Math.min(m, c); });
    var fora = d.medida.map(function (m) { return m > c ? +(m - c).toFixed(1) : null; });
    return Object.assign(base(t, d), {
      legend: { top: 0, right: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: t.muted },
        data: ["Até a contratada", "Ultrapassagem"] },
      grid: { left: 8, right: 12, top: 44, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t, d).tooltip, { axisPointer: { type: "shadow", shadowStyle: { color: rgba(t.text, 0.04) } },
        formatter: function (ps) { var i = ps[0].dataIndex, m = d.medida[i];
          return "<b>" + d.rotulos[i] + "</b><br>Medida <b style='float:right;margin-left:16px'>" + fmt(d, m, 1) + "</b><br>" +
            "Contratada <b style='float:right;margin-left:16px'>" + fmt(d, c, 0) + "</b>" +
            (m > tol ? "<br><span style='color:" + t.danger + "'>Ultrapassagem de " + fmt(d, m - c, 1) + " (acima da tolerância)</span>"
              : m > c ? "<br><span style='color:" + t.solar + "'>Acima da contratada, dentro da tolerância</span>" : ""); } }),
      xAxis: eixoCat(t, d.rotulos), yAxis: eixoValor(t, d, { max: function (v) { return Math.ceil(v.max * 1.12 / 10) * 10; } }),
      series: [
        { name: "Até a contratada", type: "bar", stack: "m", data: dentro, barMaxWidth: 22,
          itemStyle: { color: grad(t.brand, 0.95, 0.35), borderRadius: [0, 0, 3, 3] },
          markLine: { symbol: "none", silent: true, data: [
            { yAxis: c, lineStyle: { color: t.text, type: "solid", width: 1.5 },
              label: { formatter: "contratada " + num(c, 0) + " kW", color: t.text, position: "insideEndBottom", fontSize: 11,
                backgroundColor: t.surface, padding: [2, 6], borderRadius: 6 } },
            { yAxis: tol, lineStyle: { color: t.solar, type: "dashed", width: 1 },
              label: { formatter: "tolerância +" + num(d.tolerancia * 100, 0) + "%", color: t.solar, position: "insideStartTop", fontSize: 11,
                backgroundColor: t.surface, padding: [2, 6], borderRadius: 6 } }] } },
        { name: "Ultrapassagem", type: "bar", stack: "m", data: fora, barMaxWidth: 22,
          itemStyle: { color: grad(t.danger, 1, 0.6), borderRadius: [5, 5, 0, 0] } }
      ]
    });
  }

  /* ---------------------------------------------------------------- 12. medidor de economia */
  function gauge(t, d) {
    var pct = d.meta ? Math.min(d.valor / d.meta * 100, 100) : 0;
    return Object.assign(base(t, d), {
      tooltip: { show: false },
      series: [{ type: "gauge", startAngle: 205, endAngle: -25, min: 0, max: 100, radius: "92%", center: ["50%", "62%"],
        pointer: { show: false },
        progress: { show: true, roundCap: true, width: 16,
          itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: rgba(t.accent, 0.5) }, { offset: 1, color: t.accent }]),
            shadowBlur: 18, shadowColor: rgba(t.accent, 0.35) } },
        axisLine: { roundCap: true, lineStyle: { width: 16, color: [[1, rgba(t.text, t.escuro ? 0.07 : 0.08)]] } },
        splitLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false },
        title: { offsetCenter: [0, "34%"], color: t.muted, fontSize: 12, fontFamily: t.fonte },
        detail: { offsetCenter: [0, "-4%"], fontFamily: t.fonte, valueAnimation: !reduzido,
          formatter: function () { return "{v|R$ " + num(d.valor, 0) + "}\n{m|de R$ " + num(d.meta, 0) + " · " + num(pct, 0) + "%}"; },
          rich: { v: { fontSize: 30, fontWeight: 650, color: t.text, lineHeight: 38 }, m: { fontSize: 12, color: t.muted, lineHeight: 18 } } },
        data: [{ value: pct, name: d.rotulo }] }]
    });
  }

  /* ---------------------------------------------------------------- formato genérico (apps/core/graficos.py)
     rotulos + series [{nome, valores, papel, tipo: bar|line, pilha, tracejado, cores}] + horizontal/empilhado.
     A cor segue o PAPEL do dado (geração, injeção...), nunca a posição. */
  function corPapel(t, papel, i) {
    var mapa = { geracao: t.solar, esperado: rgba(t.text, 0.55), injecao: t.brand, autoconsumo: t.ok, compensada: t.ok,
                 rede: t.cat[3], carga: t.cat[5], fatura: t.cat[4], bom: t.ok, atencao: t.solar, critico: t.danger,
                 neutro: t.muted };
    return mapa[papel] || t.cat[i % t.cat.length];
  }
  function barras(t, d) {
    if (d.horizontal) {
      return ranking(t, { unidade: d.unidade, casas: d.casas, itens: d.rotulos.map(function (r, i) {
        var s = d.series[0], c = s.cores ? s.cores[i] : s.papel;
        return { nome: r, valor: s.valores[i], cor: corPapel(t, c, i) }; }) });
    }
    var multi = d.series.length > 1;
    var series = d.series.map(function (s, i) {
      var c = corPapel(t, s.papel, i);
      if (s.tipo === "line") {
        return { name: s.nome, type: "line", data: s.valores, smooth: s.tracejado ? false : 0.3, symbol: "none", z: 5,
          step: s.tracejado ? "middle" : false,
          lineStyle: { color: c, width: s.tracejado ? 1.5 : 2.5, type: s.tracejado ? "dashed" : "solid" }, itemStyle: { color: c } };
      }
      return { name: s.nome, type: "bar", data: s.valores, stack: s.pilha || undefined, barMaxWidth: d.empilhado ? 22 : 16,
        barGap: "25%", itemStyle: { color: grad(c, 1, d.empilhado ? 0.7 : 0.35), borderRadius: d.empilhado ? 0 : [6, 6, 2, 2] },
        emphasis: { focus: "series" } };
    });
    if (d.empilhado) { // arredonda só o topo da pilha
      var ultimas = series.filter(function (s) { return s.type === "bar"; });
      if (ultimas.length) ultimas[ultimas.length - 1].itemStyle.borderRadius = [6, 6, 0, 0];
    }
    return Object.assign(base(t, d), {
      legend: { show: multi, top: 0, right: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: t.muted } },
      grid: { left: 8, right: 12, top: multi ? 44 : 24, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t, d).tooltip, { axisPointer: { type: "shadow", shadowStyle: { color: rgba(t.text, 0.04) } },
        formatter: function (ps) { return linhasTooltip(d, ps); } }),
      xAxis: eixoCat(t, d.rotulos), yAxis: eixoValor(t, d, d.unidade === "R$" ?
        { axisLabel: { color: t.muted, fontSize: 11, formatter: function (v) { return "R$ " + num(v, 0); } } } : undefined),
      series: series
    });
  }
  function area(t, d) {
    var s = d.series[0], c = corPapel(t, s.papel, 0);
    return Object.assign(base(t, d), {
      grid: { left: 8, right: 12, top: 16, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t, d).tooltip, { formatter: function (ps) { return linhasTooltip(d, ps); } }),
      xAxis: eixoCat(t, d.rotulos, { boundaryGap: false }), yAxis: eixoValor(t, d),
      series: [{ name: s.nome, type: "line", data: s.valores, smooth: 0.4, symbol: "none",
        lineStyle: { color: c, width: 2.5 }, areaStyle: { color: grad(c, 0.35, 0) } }]
    });
  }
  function roscaGenerica(t, d) {
    if (!d.itens) {
      d = Object.assign({}, d, { centro: d.centro || d.unidade, itens: d.rotulos.map(function (r, i) {
        return { nome: r, valor: d.series[0].valores[i] }; }) });
    }
    return rosca(t, d);
  }

  var DESENHOS = { sankey: sankey, geracao: geracao, barras_agrupadas: barrasAgrupadas, cascata: cascata, aneis: aneis,
                   calendario: calendario, rosca: roscaGenerica, ranking: ranking, bullet: bullet, gauge: gauge,
                   barras: barras, area: area };

  /* ---------------------------------------------------------------- 11. mapa (Leaflet) */
  function mapa(el, d) {
    var t = tokens();
    var m = L.map(el, { zoomControl: true, attributionControl: true, scrollWheelZoom: false });
    // Tiles do OpenStreetMap (sem chave; uso leve, com atribuição). Em produção, defina data-tiles com um provedor
    // contratado (MapTiler, Stadia...). No tema escuro, o mapa claro é escurecido por filtro CSS (.mapa-escuro).
    var url = el.dataset.tiles || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    L.tileLayer(url, { maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(m);
    el.classList.toggle("mapa-escuro", t.escuro);
    var grupo = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 40,
      iconCreateFunction: function (c) {
        var filhos = c.getAllChildMarkers(), pior = "ok";
        filhos.forEach(function (f) { var s = f.options.fcStatus; if (s === "danger") pior = "danger"; else if (s === "solar" && pior !== "danger") pior = "solar"; });
        return L.divIcon({ html: '<span class="mapa-grupo mapa-' + pior + '">' + c.getChildCount() + "</span>", className: "", iconSize: [34, 34] });
      } });
    var limites = [];
    d.pontos.forEach(function (p) {
      var cor = tom(t, p.status) || t.muted;
      var mk = L.marker([p.lat, p.lon], { fcStatus: p.status, keyboard: true, title: p.nome,
        icon: L.divIcon({ className: "", html: '<span class="mapa-ponto mapa-' + p.status + '"></span>', iconSize: [18, 18] }) });
      mk.bindPopup('<div class="mapa-popup"><strong>' + p.nome + '</strong><span style="color:' + cor + '">● ' + p.rotulo + "</span>" +
        (p.kwp ? "<span>" + num(p.kwp, 1) + " kWp</span>" : "") + (p.url ? '<a href="' + p.url + '">Abrir usina</a>' : "") + "</div>");
      grupo.addLayer(mk);
      limites.push([p.lat, p.lon]);
    });
    m.addLayer(grupo);
    if (limites.length) m.fitBounds(limites, { padding: [30, 30], maxZoom: 12 });
    return m;
  }

  /* ---------------------------------------------------------------- ciclo de vida */
  function dados(el) {
    var s = document.getElementById(el.dataset.fonte);
    return s ? JSON.parse(s.textContent) : null;
  }
  function destruir(el) {
    var i = instancias.get(el);
    if (!i) return;
    if (i.observador) i.observador.disconnect();
    if (i.grafico) i.grafico.dispose();
    if (i.mapa) i.mapa.remove();
    instancias.delete(el);
  }
  function montar(el) {
    var d = dados(el);
    if (!d) return;
    destruir(el);
    var esqueleto = el.querySelector(".skeleton");
    if (d.tipo === "mapa") {
      if (esqueleto) esqueleto.remove();
      instancias.set(el, { mapa: mapa(el, d) });
      return;
    }
    var desenhar = DESENHOS[d.tipo];
    if (!desenhar) return;
    if (esqueleto) esqueleto.remove();
    var g = echarts.init(el, null, { renderer: "canvas" });
    g.setOption(desenhar(tokens(), d, el));
    var largura = el.clientWidth;
    var obs = new ResizeObserver(function () {
      g.resize();
      // gráficos que mudam de forma conforme a largura (calendário, fluxo, anéis) são redesenhados
      if (Math.abs(el.clientWidth - largura) > 40 && ["calendario", "sankey", "aneis", "cascata"].indexOf(d.tipo) >= 0) {
        largura = el.clientWidth;
        g.setOption(desenhar(tokens(), d, el), true);
      }
    });
    obs.observe(el);
    instancias.set(el, { grafico: g, observador: obs });
  }
  function montarTodos(raiz) {
    var els = Array.prototype.slice.call((raiz || document).querySelectorAll("[data-chart]"));
    if (!els.length) return;
    var precisaMapa = els.some(function (e) { return e.dataset.chart === "mapa"; });
    var precisaEcharts = els.some(function (e) { return e.dataset.chart !== "mapa"; });
    var cargas = [];
    if (precisaEcharts) cargas.push(carregarScript(STATIC + "/vendor/echarts.min.js"));
    if (precisaMapa) {
      carregarCss(STATIC + "/vendor/leaflet/leaflet.css");
      cargas.push(carregarScript(STATIC + "/vendor/leaflet/leaflet.js").then(function () {
        return carregarScript(STATIC + "/vendor/leaflet/leaflet.markercluster.js"); }));
    }
    Promise.all(cargas).then(function () { els.forEach(montar); });
  }

  // seletor de período (7D, 30D, 12M) dentro do painel do gráfico
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".periodo button[data-periodo]");
    if (!b) return;
    var painel = b.closest(".grafico-painel"), el = painel && painel.querySelector("[data-chart]");
    if (!el) return;
    painel.querySelectorAll(".periodo button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
    el.dataset.periodo = b.dataset.periodo;
    var i = instancias.get(el), d = dados(el);
    if (i && i.grafico) i.grafico.setOption(DESENHOS[d.tipo](tokens(), d, el), true);
  });

  document.addEventListener("DOMContentLoaded", function () { montarTodos(); });
  // Redesenha numa CÓPIA da lista: montar() remove e recoloca o gráfico no Map, e um forEach direto
  // visitaria de novo cada item recolocado, para sempre (a página congelava ao trocar o tema).
  document.addEventListener("fc:tema", function () { Array.from(instancias.keys()).forEach(montar); });
  document.addEventListener("htmx:beforeSwap", function (e) {
    instancias.forEach(function (_, el) { if (e.detail.target.contains(el)) destruir(el); });
  });
  document.addEventListener("htmx:afterSwap", function (e) { montarTodos(e.target); });
  window.fcGraficos = { montar: montarTodos };
})();
