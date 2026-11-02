/* Desenha os gráficos a partir dos dados montados no servidor (apps/core/graficos.py).
   Uso: <canvas data-fonte="id-do-json"></canvas> + {{ dados|json_script:"id-do-json" }} */
(function () {
  "use strict";
  if (!window.Chart) return;

  var css = getComputedStyle(document.documentElement);
  function v(nome) { return css.getPropertyValue(nome).trim(); }

  // Paleta validada para fundo escuro (dataviz: CVD e contraste ok). Cor segue o PAPEL, nunca a posição.
  var PAPEIS = {
    geracao: v("--g-geracao"), esperado: v("--g-esperado"), injecao: v("--g-injecao"),
    autoconsumo: v("--g-autoconsumo"), rede: v("--g-rede"), carga: v("--g-carga"),
    compensada: v("--g-compensada"), fatura: v("--g-fatura"),
    bom: v("--confere"), atencao: v("--atencao"), critico: v("--divergencia"), neutro: v("--secundario")
  };
  var CATEGORIAS = ["--c1", "--c2", "--c3", "--c4", "--c5", "--c6"].map(v);
  var SUPERFICIE = v("--superficie");

  Chart.defaults.color = v("--secundario");
  Chart.defaults.font.family = '"IBM Plex Sans", "Segoe UI", Arial, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.borderColor = v("--linha");
  Chart.defaults.animation = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 400 };

  var fmt = function (casas) {
    return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  };

  function corDe(s, i) {
    if (s.cores) return s.cores.map(function (p) { return PAPEIS[p] || p; });
    return PAPEIS[s.papel] || CATEGORIAS[i % CATEGORIAS.length];
  }

  function montar(canvas) {
    if (canvas._grafico) return;
    var fonte = document.getElementById(canvas.dataset.fonte);
    if (!fonte) return;
    var d = JSON.parse(fonte.textContent);
    var f = fmt(d.casas || 0);
    var rosca = d.tipo === "rosca";

    var datasets = d.series.map(function (s, i) {
      var cor = corDe(s, i);
      var base = { label: s.nome, data: s.valores };
      if (rosca) {
        return Object.assign(base, { backgroundColor: cor, borderColor: SUPERFICIE, borderWidth: 2, hoverOffset: 4 });
      }
      if (s.tipo === "line" || d.tipo === "area") {
        var area = d.tipo === "area";
        return Object.assign(base, {
          type: "line", borderColor: cor, backgroundColor: area ? cor + "33" : cor, fill: area ? "origin" : false,
          borderWidth: 2, borderDash: s.tracejado ? [5, 4] : [], pointRadius: 0, pointHoverRadius: 4,
          tension: area ? 0.3 : 0, stepped: s.tracejado && !area ? "middle" : false, order: 0, spanGaps: true
        });
      }
      return Object.assign(base, {
        type: "bar", backgroundColor: cor, stack: s.pilha || undefined, order: 1,
        borderRadius: d.empilhado ? 0 : 4, borderSkipped: d.horizontal ? "start" : "bottom",
        borderColor: SUPERFICIE, borderWidth: d.empilhado ? { top: 2 } : 0,
        maxBarThickness: 36, categoryPercentage: 0.72, barPercentage: 0.9
      });
    });

    var multi = d.series.length > 1 || rosca;
    var opcoes = {
      responsive: true, maintainAspectRatio: false,
      indexAxis: d.horizontal ? "y" : "x",
      interaction: { mode: rosca ? "nearest" : "index", intersect: rosca },
      plugins: {
        legend: { display: multi, position: rosca ? "right" : "top", align: "start",
                  labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: "rectRounded", padding: 14 } },
        tooltip: {
          backgroundColor: v("--fundo-2"), borderColor: v("--linha-forte"), borderWidth: 1,
          titleColor: v("--texto"), bodyColor: v("--texto"), padding: 10, boxPadding: 4,
          callbacks: {
            label: function (ctx) {
              var val = rosca ? ctx.parsed : (d.horizontal ? ctx.parsed.x : ctx.parsed.y);
              if (val === null || val === undefined) return ctx.dataset.label + ": sem dado";
              return (ctx.dataset.label || ctx.label) + ": " + f.format(val) + " " + d.unidade;
            }
          }
        }
      }
    };
    if (!rosca) {
      var eixoValor = {
        beginAtZero: true, stacked: !!d.empilhado, border: { display: false },
        grid: { color: v("--linha") }, ticks: { callback: function (x) { return f.format(x); }, maxTicksLimit: 6 },
        title: { display: true, text: d.unidade, color: v("--secundario") }
      };
      var eixoCat = { stacked: !!d.empilhado, grid: { display: false }, border: { color: v("--linha-forte") },
                      ticks: { autoSkip: true, maxRotation: 0, autoSkipPadding: 12 } };
      opcoes.scales = d.horizontal ? { x: eixoValor, y: eixoCat } : { x: eixoCat, y: eixoValor };
    } else {
      opcoes.cutout = "62%";
    }

    canvas._grafico = new Chart(canvas, {
      type: rosca ? "doughnut" : "bar",
      data: { labels: d.rotulos, datasets: datasets },
      options: opcoes
    });
  }

  function montarTodos(raiz) {
    (raiz || document).querySelectorAll("canvas[data-fonte]").forEach(montar);
  }
  document.addEventListener("DOMContentLoaded", function () { montarTodos(); });
  document.body && document.body.addEventListener("htmx:afterSwap", function (e) { montarTodos(e.target); });
})();
