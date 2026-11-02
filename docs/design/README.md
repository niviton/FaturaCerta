# Design system "noite solar"

O sistema mostra a energia do sol medida e conferida. Escuro como padrão, com luz (acento) só onde há energia
ou dinheiro. A referência viva fica em **`/design/`** (só administrador geral), com todos os componentes e os 12
gráficos nos dois temas.

## Arquivos

| Arquivo | O que tem |
|---|---|
| `static/css/fc.css` | Tokens (escuro em `:root`, claro em `[data-theme="light"]`) e componentes |
| `static/css/telas.css` | Padrões de tela: fichas, abas, monitoramento, análise da conta, formulários, login, portal |
| `static/js/fc.js` | Tema, menu recolhível, números que contam, toasts, modais, linhas clicáveis |
| `static/js/charts.js` | Gráficos (ECharts + Leaflet), tema gerado dos tokens |
| `apps/core/charts.py` | Monta os dados de cada tipo de gráfico (as views só chamam estas funções) |
| `apps/core/templatetags/fc.py` | `{% icone %}`, `{% sparkline %}`, `{% anel %}`, filtros `brl`, `kwh`, `ptbr`, `cor_texto` |
| `templates/fc/documento.html`, `templates/fc/app.html` | Documento base e layout com menu lateral e topo |
| `templates/components/` | Biblioteca de componentes |
| `static/vendor/` | ECharts 5.5.1, Leaflet 1.9.4 e markercluster, HTMX 2.0.4 (servidos localmente) |

## Tokens

| Token | Escuro | Claro | Uso |
|---|---|---|---|
| `--bg` | `#06080C` | `#F3F5F8` | Fundo da página |
| `--surface` | `#0D1117` | `#FFFFFF` | Painéis |
| `--surface-2` | `#141A23` | `#EEF1F5` | Painéis internos, hover de linha |
| `--glass` | `rgba(20,26,35,.62)` | `rgba(255,255,255,.72)` | Painéis flutuantes e modais (com desfoque) |
| `--text` | `#F2F5F8` | `#0B1220` | Texto |
| `--muted` | `#8B95A5` | `#5B6676` | Texto secundário (6,6:1 e 5,9:1) |
| `--accent` | `#C8FF2E` | `#5A7D00` | Energia, ação principal, valor positivo |
| `--brand` | `#3D6BFF` | `#2F56E0` | Marca, links, seleção |
| `--solar` | `#FFB224` | `#B86E00` | Geração, sol |
| `--danger` | `#FF5A3C` | `#C93A1E` | Divergência, usina parada |
| `--ok` | `#2EE6A0` | `#0E8A5F` | Confere, gerando normal |

- **Tipografia:** Geist (tudo) e Geist Mono (valores técnicos pequenos). Escala 12, 14, 16, 20, 24, 32, 44, 64.
  Números sempre tabulares.
- **Raios:** 10px controles, 16px painéis, 24px cartão-herói, pílula 999px.
- **Hierarquia por luz:** o número mais importante de cada tela vai no cartão-herói (claro sobre escuro); o resto
  em painéis discretos. O halo do herói muda pela situação (`ok`, `solar`, `danger`, `brand`).
- **Ícones:** Lucide v0.460.0 (ISC), traço 1,75, via `{% icone "nome" %}`.
- **Situação nunca só por cor:** círculo (normal), quadrado (atenção), losango (crítico).
- **Movimento:** uma entrada por página; tudo desliga com `prefers-reduced-motion`.
- **Marca branca:** no portal do cliente, a cor da integradora vira o `--accent`; o texto sobre ela é preto ou
  branco pela luminância (`|cor_texto`).

## Componentes (`templates/components/`)

| Componente | Parâmetros principais |
|---|---|
| `hero_card` | `rotulo`, `icone`, `valor`, `casas`, `prefixo`, `unidade`, `sub`, `estado`, `acento`, `acao_url`, `serie` |
| `kpi_card` | `rotulo`, `icone`, `valor`, `casas`, `unidade`, `estado`, `rodape`, `delta`, `delta_bom`, `serie`, `serie_tom` |
| `status_pill` | `tom` (`ok`, `solar`, `danger`, `brand`, `accent`, `demo`), `texto`, `sem_ponto` |
| `filter_tabs` | `itens` [{rotulo, valor, contador, tom}], `nome`, `atual` |
| `data_table` | `colunas`, `linhas` (para tabelas ricas, use as classes `.tabela` direto) |
| `chart_panel` | `id`, `titulo`, `sub`, `dados`, `altura`, `vazio_texto`, `sem_tabela` |
| `empty_state` | `icone`, `titulo`, `texto`, `acao_url`, `acao_texto` |
| `toast` | mensagens do Django; no JS, `fcToast(texto, "ok" \| "erro" \| "info")` |
| `modal` | `id`, `titulo`, `texto`, `confirmar_texto`, `acao`; abrir com `data-abre-modal="id"` |
| `sidebar`, `topbar`, `tema_toggle` | layout (o topo das telas internas fica em `fc/app.html`) |
| `bottom_nav` | `itens` (até 4), só no portal do cliente |
| `skeleton` | `linhas`, `altura` |
| `selo_demo` | selo "dados de demonstração" / "demonstração com clima real" |

## Gráficos

Tipos que o `charts.js` desenha: `sankey`, `geracao` (com 7D/30D/12M), `barras_agrupadas`, `cascata`, `aneis`,
`calendario`, `rosca`, `ranking`, `bullet`, `gauge`, `mapa` (Leaflet) e o formato genérico `barras`/`area`
(de `apps/core/graficos.py`). Sparklines são SVG do servidor (`{% sparkline %}`), mais leves.

Regras: cor segue o papel do dado (geração = solar, injeção = brand, compensado = ok, não compensado = danger),
paleta categórica de 8 cores distintas também em luminosidade, gradiente vertical nas áreas e barras, grade quase
invisível, tooltip em vidro com linha tracejada, valores em pt-BR, "Ver os números" em todo gráfico e estado vazio
com uma frase do que fazer.

### Criar um gráfico novo

1. Monte os dados numa função de `apps/core/charts.py` (ou use uma existente), devolvendo `tipo`, os dados e a
   `tabela` para o "Ver os números".
2. Na view, coloque o resultado no contexto: `ctx["g_algo"] = charts.ranking(...)`.
3. No template: `{% include "components/chart_panel.html" with id="g-algo" dados=g_algo titulo="..." sub="..." altura="300px" %}`.
4. Tipo novo de desenho: escreva a função em `static/js/charts.js` (recebe tokens, dados e o elemento) e registre
   em `DESENHOS`. Use `base()`, `eixoCat()`, `eixoValor()`, `grad()` e `fmt()` para manter o padrão.

O ECharts (e o Leaflet) só são baixados em páginas com gráfico. Os gráficos se redesenham ao trocar o tema, ao
redimensionar (`ResizeObserver`) e nas trocas do HTMX.

## Antes e depois

- `docs/design/antes/`: o visual anterior, 26 telas em desktop (1440px) e celular (390px).
- `docs/design/depois/`: as mesmas telas no design novo, nos temas escuro e claro.
- `docs/design/etapa1/` e `etapa2/`: a página `/design/` e os 12 gráficos isolados.

Para refazer as capturas (com o servidor rodando e o `seed_demo` carregado):

```bash
.venv/Scripts/python scripts/capturar_telas.py docs/design/depois
.venv/Scripts/python scripts/capturar_telas.py docs/design/depois --tema claro
```

## O que ainda não tem tela

Laudo de contestação, recomendações com aceite e o seletor de paletas de marca branca dependem de funções que
ainda não existem (motor de regras, recomendações). A identidade, os componentes e os gráficos (cascata, bullet de
demanda, medidor) já estão prontos para elas.
