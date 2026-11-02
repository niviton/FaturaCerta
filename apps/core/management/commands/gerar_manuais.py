"""Gera os manuais em PDF a partir do Markdown.

Uso: python manage.py gerar_manuais [administrador|integradora ...]

Converte o Markdown em HTML com estilo de impressão e gera o PDF com o WeasyPrint (imagem Docker) ou,
na falta dele, com o Edge/Chrome em modo headless (Windows). Depois carimba o rodapé com o título e o
número da página em todas as páginas menos a capa.
"""

import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import markdown
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from markdown.extensions.toc import slugify_unicode

from apps.core.manuais import MANUAIS

NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge", "google-chrome", "chromium", "chromium-browser",
]

CSS = """
@page { size: A4; margin: 18mm 17mm 20mm 17mm; }
@page capa { margin: 0; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", "IBM Plex Sans", "DejaVu Sans", Arial, sans-serif; font-size: 10pt; line-height: 1.55;
       color: #141B2D; margin: 0; }
.capa { page: capa; height: 297mm; width: 210mm; background: #0A0F1C; color: #EEF1F7; padding: 26mm 22mm; position: relative;
        page-break-after: always; break-after: page; overflow: hidden; }
.capa .faixa { position: absolute; left: 0; top: 0; width: 100%; height: 8mm; background: #1F4FFF; }
.capa .marca { display: flex; align-items: center; gap: 4mm; font-size: 15pt; font-weight: 700; margin-top: 10mm; }
.capa .raio { width: 12mm; height: 12mm; border-radius: 3mm; background: #1F4FFF; display: flex; align-items: center;
              justify-content: center; }
.capa h1 { font-size: 34pt; line-height: 1.05; margin: 60mm 0 6mm; max-width: 150mm; border: 0; color: #EEF1F7; }
.capa .publico { display: inline-block; background: #C8FF2E; color: #0A0F1C; font-weight: 700; padding: 1.5mm 4mm;
                 border-radius: 1.5mm; font-size: 11pt; }
.capa .descricao { color: #B8C2D6; font-size: 11.5pt; max-width: 150mm; margin-top: 10mm; line-height: 1.5; }
.capa .rodape { position: absolute; left: 22mm; right: 22mm; bottom: 22mm; border-top: 1px solid #2E3A55;
                padding-top: 4mm; color: #9AA6BD; font-size: 9pt; display: flex; justify-content: space-between; }
.capa .tres { position: absolute; left: 22mm; right: 22mm; bottom: 45mm; display: flex; gap: 6mm; }
.capa .tres div { flex: 1; border-top: 2px solid #2E3A55; padding-top: 3mm; font-size: 9pt; color: #9AA6BD; }
.capa .tres div:nth-child(1) { border-color: #C8FF2E; }
.capa .tres div:nth-child(2) { border-color: #1F4FFF; }
.capa .tres div:nth-child(3) { border-color: #D95926; }
.capa .tres strong { display: block; color: #EEF1F7; font-size: 10pt; margin-bottom: 1mm; }

main h1 { font-size: 22pt; color: #0A0F1C; margin: 0 0 6mm; padding-bottom: 3mm; border-bottom: 3px solid #C8FF2E;
          page-break-before: always; break-before: page; }
main h2 { font-size: 15pt; color: #0A0F1C; margin: 0 0 4mm; padding-top: 2mm; page-break-before: always;
          break-before: page; page-break-after: avoid; break-after: avoid; }
main h2::before { content: ""; display: block; width: 14mm; height: 1.4mm; background: #1F4FFF; margin-bottom: 3mm; }
main h3 { font-size: 11.5pt; color: #1F4FFF; margin: 6mm 0 2mm; page-break-after: avoid; break-after: avoid; }
main > h2:first-child, main > h1:first-child, h1 + h2, #sumário {
  page-break-before: auto; break-before: auto; }
p { margin: 0 0 3mm; orphans: 3; widows: 3; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1mm; }
a { color: #1F4FFF; text-decoration: none; }
strong { color: #0A0F1C; }
hr { display: none; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 5mm; font-size: 8.8pt; page-break-inside: auto; }
tr { page-break-inside: avoid; break-inside: avoid; }
thead { display: table-header-group; }
th { background: #0F1626; color: #EEF1F7; text-align: left; font-weight: 600; padding: 2mm 2.5mm;
     overflow-wrap: normal; white-space: nowrap; }
td { border-bottom: 1px solid #D9DEE8; padding: 1.8mm 2.5mm; vertical-align: top; overflow-wrap: anywhere; }
main { max-width: 176mm; overflow-wrap: anywhere; }
tbody tr:nth-child(even) td { background: #F4F6FA; }
code { font-family: Consolas, "Cascadia Mono", "DejaVu Sans Mono", monospace; font-size: 8.6pt; background: #EEF1F7;
       padding: 0.3mm 1mm; border-radius: 1mm; color: #0A0F1C; }
pre { background: #0F1626; color: #EEF1F7; padding: 3.5mm 4mm; border-radius: 2mm; font-size: 8.3pt;
      white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; break-inside: avoid; margin: 2mm 0 4mm; }
pre code { background: transparent; color: inherit; padding: 0; font-size: inherit; }
blockquote { margin: 3mm 0 4mm; padding: 3mm 4mm; border-left: 3px solid #D95926; background: #FFF4EE; color: #3A2A20; }
blockquote p { margin: 0; }
.sumario-titulo + ol, .sumario-titulo + ul { columns: 1; }
"""

RAIO = ('<svg width="22" height="22" viewBox="0 0 24 24"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" '
        'fill="#C8FF2E"/></svg>')


def montar_html(manual) -> str:
    texto = manual.caminho_fonte.read_text(encoding="utf-8")
    # o primeiro título (H1) vira a capa
    texto = re.sub(r"\A# .+\n", "", texto.lstrip(), count=1)
    corpo = markdown.markdown(
        texto, extensions=["tables", "fenced_code", "toc", "sane_lists"],
        extension_configs={"toc": {"slugify": slugify_unicode}})
    # links para arquivos do repositório não funcionam no PDF: deixa só o texto
    corpo = re.sub(r'<a href="(?!#|https?:)[^"]*">(.*?)</a>', r"\1", corpo)
    hoje = timezone.localdate()
    capa = f"""
<section class="capa">
  <div class="faixa"></div>
  <div class="marca"><span class="raio">{RAIO}</span>FaturaCerta</div>
  <h1>{manual.titulo}</h1>
  <span class="publico">{manual.publico}</span>
  <p class="descricao">{manual.descricao}</p>
  <div class="tres">
    <div><strong>Inversor</strong>Quanto a usina gerou</div>
    <div><strong>Medidor próprio</strong>O que entrou e saiu da rede</div>
    <div><strong>Concessionária</strong>O que foi medido e cobrado</div>
  </div>
  <div class="rodape"><span>Monitoramento e auditoria de faturas para integradoras solares</span>
    <span>Edição de {hoje:%m/%Y}</span></div>
</section>"""
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{manual.titulo}</title>'
            f"<style>{CSS}</style></head><body>{capa}<main>{corpo}</main></body></html>")


def _pdf_weasyprint(html: str) -> bytes | None:
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return None
    return HTML(string=html).write_pdf()


def _pdf_navegador(html: str) -> bytes | None:
    exe = next((p for p in NAVEGADORES if Path(p).exists() or shutil.which(p)), None)
    if exe is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        origem, destino = Path(tmp) / "manual.html", Path(tmp) / "manual.pdf"
        origem.write_text(html, encoding="utf-8")
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
                        f"--user-data-dir={Path(tmp) / 'perfil'}", f"--print-to-pdf={destino}", origem.as_uri()],
                       check=True, capture_output=True, timeout=180)
        return destino.read_bytes() if destino.exists() else None


def carimbar_rodape(pdf: bytes, titulo: str) -> bytes:
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas

    leitor = PdfReader(io.BytesIO(pdf))
    escritor = PdfWriter()
    total = len(leitor.pages)
    for i, pagina in enumerate(leitor.pages):
        if i > 0:
            larg, alt = float(pagina.mediabox.width), float(pagina.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(larg, alt))
            c.setFont("Helvetica", 7.5)
            c.setFillColor(HexColor("#6B7790"))
            c.drawString(48, 26, f"FaturaCerta · {titulo}")
            c.drawRightString(larg - 48, 26, f"página {i + 1} de {total}")
            c.setStrokeColor(HexColor("#D9DEE8"))
            c.setLineWidth(0.5)
            c.line(48, 36, larg - 48, 36)
            c.save()
            buf.seek(0)
            pagina.merge_page(PdfReader(buf).pages[0])
        escritor.add_page(pagina)
    escritor.add_metadata({"/Title": f"FaturaCerta · {titulo}", "/Author": "FaturaCerta"})
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


class Command(BaseCommand):
    help = "Gera os manuais em PDF (docs/manuais/) a partir do Markdown."

    def add_arguments(self, parser):
        parser.add_argument("codigos", nargs="*", help=f"Manuais a gerar ({', '.join(MANUAIS)}). Padrão: todos.")
        parser.add_argument("--html", action="store_true", help="Também salva o HTML intermediário (para revisão).")

    def handle(self, *args, codigos, html, **opts):
        for codigo in codigos or list(MANUAIS):
            if codigo not in MANUAIS:
                raise CommandError(f"Manual desconhecido: {codigo}")
            manual = MANUAIS[codigo]
            doc = montar_html(manual)
            if html:
                manual.arquivo.with_suffix(".html").write_text(doc, encoding="utf-8")
            pdf = _pdf_weasyprint(doc) or _pdf_navegador(doc)
            if pdf is None:
                raise CommandError("Instale o WeasyPrint ou o Edge/Chrome para gerar o PDF.")
            manual.arquivo.parent.mkdir(parents=True, exist_ok=True)
            manual.arquivo.write_bytes(carimbar_rodape(pdf, manual.titulo))
            self.stdout.write(self.style.SUCCESS(f"{manual.arquivo.name}: {len(pdf) // 1024} KB"))
