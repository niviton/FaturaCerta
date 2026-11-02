/* FaturaCerta · comportamento da interface (sem dependências).
   Tema claro/escuro, menu lateral, números que contam, toasts, modais e linhas clicáveis. */
(function () {
  "use strict";
  var raiz = document.documentElement;
  var reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function salvar(chave, valor) { try { localStorage.setItem(chave, valor); } catch (e) { /* modo privado */ } }
  function ler(chave) { try { return localStorage.getItem(chave); } catch (e) { return null; } }

  /* ---------- tema ---------- */
  function aplicarTema(tema) {
    raiz.dataset.theme = tema === "claro" ? "light" : "dark";
    document.dispatchEvent(new CustomEvent("fc:tema", { detail: raiz.dataset.theme }));
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-acao='tema']");
    if (!b) return;
    var novo = raiz.dataset.theme === "light" ? "escuro" : "claro";
    salvar("fc-tema", novo);
    aplicarTema(novo);
    b.setAttribute("aria-label", novo === "claro" ? "Usar tema escuro" : "Usar tema claro");
  });
  window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", function (m) {
    if (!ler("fc-tema")) aplicarTema(m.matches ? "claro" : "escuro");
  });

  /* ---------- menu lateral ---------- */
  document.addEventListener("click", function (e) {
    var shell = document.querySelector(".shell");
    if (!shell) return;
    if (e.target.closest("[data-acao='menu']")) {
      var aberto = shell.classList.toggle("menu-aberto");
      e.target.closest("[data-acao='menu']").setAttribute("aria-expanded", aberto);
    } else if (e.target.closest("[data-acao='recolher']")) {
      var rec = raiz.classList.toggle("recolhido");
      salvar("fc-menu", rec ? "recolhido" : "aberto");
      e.target.closest("[data-acao='recolher']").setAttribute("aria-expanded", !rec);
    } else if (shell.classList.contains("menu-aberto") && !e.target.closest(".sidebar")) {
      shell.classList.remove("menu-aberto");
    }
  });

  /* ---------- números que contam (um único momento de entrada) ---------- */
  function contar(el) {
    if (el.dataset.contado) return;
    el.dataset.contado = "1";
    var alvo = parseFloat(el.dataset.contar);
    var casas = parseInt(el.dataset.casas || "0", 10);
    var fmt = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
    if (reduzido || isNaN(alvo)) { el.textContent = fmt.format(alvo); return; }
    var inicio = null, dur = 900;
    function passo(t) {
      if (!inicio) inicio = t;
      var p = Math.min((t - inicio) / dur, 1);
      el.textContent = fmt.format(alvo * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(passo);
    }
    requestAnimationFrame(passo);
  }

  /* ---------- toasts ---------- */
  var ICONES = { ok: "circle-check", erro: "triangle-alert", info: "info" };
  window.fcToast = function (texto, tipo) {
    tipo = tipo || "info";
    var caixa = document.querySelector(".toasts");
    if (!caixa) { caixa = document.createElement("div"); caixa.className = "toasts"; document.body.appendChild(caixa); }
    var t = document.createElement("div");
    t.className = "toast toast-" + tipo;
    t.setAttribute("role", tipo === "erro" ? "alert" : "status");
    t.innerHTML = '<svg class="i"><use href="#i-' + ICONES[tipo] + '"/></svg><span></span>' +
      '<button class="btn btn-fantasma btn-p btn-icone toast-fechar" type="button" aria-label="Fechar aviso">' +
      '<svg class="i i-sm"><use href="#i-x"/></svg></button>';
    t.querySelector("span").textContent = texto;
    caixa.appendChild(t);
    setTimeout(function () { t.remove(); }, 6000);
  };
  document.addEventListener("click", function (e) {
    var f = e.target.closest(".toast-fechar");
    if (f) f.closest(".toast").remove();
  });

  /* ---------- modais (<dialog>) ---------- */
  document.addEventListener("click", function (e) {
    var abre = e.target.closest("[data-abre-modal]");
    if (abre) { var d = document.getElementById(abre.dataset.abreModal); if (d) d.showModal(); return; }
    var fecha = e.target.closest("[data-fecha-modal]");
    if (fecha) fecha.closest("dialog").close();
  });

  /* ---------- linhas de tabela clicáveis ---------- */
  document.addEventListener("click", function (e) {
    var tr = e.target.closest("tr[data-href]");
    if (tr && !e.target.closest("a, button, input, select, label")) window.location = tr.dataset.href;
  });

  function iniciar(raizBusca) {
    (raizBusca || document).querySelectorAll("[data-contar]").forEach(contar);
  }
  document.addEventListener("DOMContentLoaded", function () {
    iniciar();
    document.querySelectorAll(".toast[data-auto]").forEach(function (t) { setTimeout(function () { t.remove(); }, 6000); });
  });
  document.addEventListener("htmx:afterSwap", function (e) { iniciar(e.target); });
})();
