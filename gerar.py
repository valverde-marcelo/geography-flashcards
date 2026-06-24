#!/usr/bin/env python3
"""
Gerador de cartões "Info Países" (frente = bandeira / verso = dados)
======================================================================

Lê `data.json` e gera:
  1. `cartoes.html`  -> folha A4 com todos os cartões, prontos para impressão
  2. `cartoes.pdf`   -> mesma folha convertida para PDF (via wkhtmltopdf)

NÃO altera as dimensões originais do cartão (85.6mm x 53.98mm, padrão
cartão de crédito) definidas em `modelo.html`.

Convenções de arquivo assumidas (ajuste em CONFIG se necessário):
  - Bandeiras: "images/{arquivo_bandeira}"   (campo já vem pronto no JSON)
  - Mapas:     "images/mapas/{slug(nome)}.png"
               onde slug() = nome do país em minúsculas, sem acentos,
               espaços/pontuação trocados por "-".
               Ex.: "Brasil" -> "brasil.png"
                    "África do Sul" -> "africa-do-sul.png"
               -> Se os arquivos de mapa do seu acervo seguirem outra
                  convenção, ajuste a função `slug()` abaixo.

Uso:
    python3 gerar_cartoes.py
    python3 gerar_cartoes.py --no-pdf        # gera só o HTML
    python3 gerar_cartoes.py --apenas-onu     # só países membros da ONU
    python3 gerar_cartoes.py --base-images ./images   # ajusta pasta de imagens
"""

import argparse
import json
import re
import subprocess
import unicodedata
from pathlib import Path

# --------------------------------------------------------------------------
# CONFIGURAÇÃO
# --------------------------------------------------------------------------

CARD_W_MM = 85.6   # NÃO ALTERAR - dimensão padrão de cartão de crédito
CARD_H_MM = 53.98  # NÃO ALTERAR

COLS = 2           # cartões por linha na folha A4
ROWS = 4            # cartões por coluna na folha A4 (2x4 = 8 cartões/página)
PAGE_MARGIN_MM = 10
GAP_MM = 8

FOOTER_WATERMARK = "@valverdeoficial"

THIS_DIR = Path(__file__).resolve().parent
DATA_JSON_DEFAULT = THIS_DIR / "data.json"
OUTPUT_HTML_DEFAULT = THIS_DIR / "cartoes.html"
OUTPUT_PDF_DEFAULT = THIS_DIR / "cartoes.pdf"


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def slug(text: str) -> str:
    """Normaliza um nome de país para usar como nome de arquivo de mapa."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def fmt_number(n):
    """Formata número no padrão brasileiro (ponto como separador de milhar)."""
    if n is None:
        return None
    try:
        return f"{int(n):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def html_escape(text) -> str:
    if text is None:
        return ""
    text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_localizacao_text(localizacao):
    """Recebe o campo 'localizacao' (dict ou string vazia) e retorna texto."""
    if not localizacao or not isinstance(localizacao, dict):
        return None
    regiao = localizacao.get("regiao", "")
    sub = localizacao.get("sub-regiao", "")
    regiao = regiao.upper() if regiao else ""
    sub = sub.upper() if sub else ""
    if regiao and sub:
        return f"{regiao} ({sub})"
    return regiao or sub or None


# --------------------------------------------------------------------------
# Construção do HTML de cada cartão
# --------------------------------------------------------------------------

def build_frente_html(country: dict, images_base: str) -> str:
    bandeira = country.get("arquivo_bandeira") or ""
    src = f"{images_base}/{bandeira}" if bandeira else ""
    nome = html_escape(country.get("nome"))
    return f"""
        <div class="credit-card">
            <img src="{html_escape(src)}" alt="Bandeira de {nome}" class="bandeira"
                 onerror="this.style.visibility='hidden'">
        </div>"""


def country_name_font_size(nome: str) -> str:
    """Reduz a fonte do nome do país conforme o tamanho do texto, para
    nomes longos não quebrarem em 3+ linhas e vazarem do cartão."""
    length = len(nome or "")
    if length <= 14:
        return "0.7cm"
    if length <= 22:
        return "0.55cm"
    if length <= 30:
        return "0.45cm"
    return "0.36cm"


def build_verso_html(country: dict, images_base: str) -> str:
    nome = html_escape(country.get("nome") or "")
    capital = html_escape(country.get("capital") or "")
    nome_slug = slug(country.get("nome") or "")
    map_src = f"{images_base}/mapas/{nome_slug}.png" if nome_slug else ""

    items = []

    

    idioma = country.get("idioma")
    if idioma:
        items.append(f'<div class="detail-item"><span class="label">Idioma:</span> {html_escape(str(idioma).upper())}</div>')

    moeda = country.get("moeda")
    if moeda:
        items.append(f'<div class="detail-item"><span class="label">Moeda:</span> {html_escape(str(moeda).upper())}</div>')

    nome_oficial = country.get("nome_oficial")
    if nome_oficial and nome_oficial != country.get("nome"):
        items.append(f'<div class="detail-item"><span class="label">Nome Oficial:</span> {html_escape(str(nome_oficial).upper())}</div>')

    loc_text = build_localizacao_text(country.get("localizacao"))
    if loc_text:
        items.append(f'<div class="detail-item"><span class="label">Continente:</span> {html_escape(loc_text)}</div>')

    #forma_governo = country.get("forma_de_governo")
    #if forma_governo:
    #    items.append(f'<div class="detail-item"><span class="label">Forma de Governo:</span> {html_escape(str(forma_governo).upper())}</div>')

    area = country.get("area")
    if area not in (None, ""):
        area_fmt = fmt_number(area)
        rank_area = country.get("colocacao_area")
        rank_html = f'<span class="rank">{rank_area}º</span>' if rank_area else ""
        items.append(f'<div class="detail-item"><span class="label">Território:</span> {area_fmt} km²{rank_html}</div>')

    populacao = country.get("populacao")
    if populacao not in (None, ""):
        pop_fmt = fmt_number(populacao)
        rank_pop = country.get("colocacao_populacao")
        rank_html = f'<span class="rank">{rank_pop}º</span>' if rank_pop else ""
        items.append(f'<div class="detail-item"><span class="label">População:</span> {pop_fmt}{rank_html}</div>')

    #ano = country.get("ano_independencia_fundacao")
    #if ano:
    #    items.append(f'<div class="detail-item"><span class="label">Ano independência/fundação:</span> {html_escape(ano)}</div>')

    details_html = "\n                ".join(items)

    return f"""
        <div class="credit-card verso">
            <img src="{html_escape(map_src)}" alt="Mapa de {nome}" class="world-map-bg"
                 onerror="this.style.visibility='hidden'">
            <div class="card-content">
                <div class="header-text">
                    <div class="country-name" style="font-size: {country_name_font_size(country.get('nome'))};">{nome}</div>
                    <div class="capital-name">{capital}</div>
                </div>
                <div class="details-text">
                {details_html}
                </div>
                <div class="footer-text">{html_escape(FOOTER_WATERMARK)}</div>
            </div>
        </div>"""


# --------------------------------------------------------------------------
# Montagem das páginas A4
# --------------------------------------------------------------------------

def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def build_pages(countries, images_base):
    per_page = COLS * ROWS
    pages_html = []
    for batch in chunk(countries, per_page):
        frente_cards = "\n".join(
            f'<div class="card-slot">{build_frente_html(c, images_base)}</div>' for c in batch
        )
        verso_cards = "\n".join(
            f'<div class="card-slot">{build_verso_html(c, images_base)}</div>' for c in batch
        )
        pages_html.append(f'<div class="page"><div class="page-grid">{frente_cards}\n</div></div>')
        pages_html.append(f'<div class="page"><div class="page-grid">{verso_cards}\n</div></div>')
    return "\n".join(pages_html)


PAGE_CSS = f"""
@page {{
    size: A4;
    margin: 0;
}}

* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    font-family: 'Courier New', Courier, monospace;
}}

html, body {{
    background: #f0f0f0;
}}

/* wkhtmltopdf usa um WebKit antigo sem suporte confiável a CSS Grid,
   por isso o layout é feito com floats simples (compatível e estável). */
.page {{
    width: 210mm;
    height: 297mm;
    padding: {PAGE_MARGIN_MM}mm;
    background: white;
    page-break-after: always;
    break-after: page;
    overflow: hidden;
}}

.page-grid {{
    width: {COLS * CARD_W_MM + (COLS - 1) * GAP_MM}mm;
    margin: 0 auto;
    overflow: hidden; /* contém os floats (cria um BFC) */
}}

.card-slot {{
    float: left;
    width: {CARD_W_MM}mm;
    height: {CARD_H_MM}mm;
    margin: 0 {GAP_MM}mm {GAP_MM}mm 0;
}}

.card-slot:nth-child({COLS}n) {{
    margin-right: 0;
}}

.page:last-child {{
    page-break-after: auto;
    break-after: auto;
}}

/* --- Estilos do cartão (dimensões originais preservadas) --- */

.credit-card {{
    width: {CARD_W_MM}mm;
    height: {CARD_H_MM}mm;
    background-image: url('images/_flags.jpg');
    background-size: cover;
    background-position: center;
    border-radius: 5mm;
    padding: 10px;
    position: relative;
    overflow: hidden;
    outline: 1px dashed #999;      /* guia de corte, não altera o tamanho */
    outline-offset: 2px;
}}

.card-content {{
    width: 100%;
    height: 100%;
    background-color: white;
    border-radius: 3mm;
    padding: 5px 10px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}

.world-map-bg {{
    position: absolute;
    top: 10px;
    right: 10px;
    width: 60%;
    border-radius: 10px;
    opacity: 0.5;
    z-index: 1;
    -webkit-mask-image: linear-gradient(to right, transparent 0%, black 20%),
        linear-gradient(to top, transparent 0%, black 20%);
    mask-image: linear-gradient(to right, transparent 0%, black 20%),
        linear-gradient(to top, transparent 0%, black 20%);
    -webkit-mask-composite: source-in;
    mask-composite: intersect;
}}

.header-text {{
    text-align: center;
    z-index: 2;
    margin-bottom: 5px;
}}

.country-name {{
    font-size: 0.7cm;
    font-weight: bold;
    color: #d9534f;
    text-transform: uppercase;
}}

.capital-name {{
    font-size: 0.3cm;
    color: #333;
}}

.details-text {{
    text-align: left;
    z-index: 2;
    font-size: 0.2cm;
    line-height: 1.4;
}}

.detail-item {{
    margin-bottom: 3px;
}}

.label {{
    font-weight: bold;
}}

.rank {{
    font-size: 0.2cm;
    font-weight: bold;
    color: white;
    margin-left: 5px;
    background: red;
    padding: 1px;
    border-radius: 3px;
}}

.bandeira {{
    width: 100%;
    height: 100%;
    object-fit: cover;
}}

.footer-text {{
    text-align: center;
    font-size: 0.7rem;
    color: #777;
    margin-top: auto;
    z-index: 2;
}}

@media print {{
    body {{ background: white; }}
    .credit-card {{ box-shadow: none; }}
}}
"""


def build_full_html(countries, images_base):
    pages = build_pages(countries, images_base)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Cartões Info Países</title>
<style>
{PAGE_CSS}
</style>
</head>
<body>
{pages}
</body>
</html>"""


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Gera cartões (frente/verso) de países em A4, prontos para PDF.")
    parser.add_argument("--data", default=str(DATA_JSON_DEFAULT), help="Caminho para data.json")
    parser.add_argument("--out-html", default=str(OUTPUT_HTML_DEFAULT), help="Caminho do HTML de saída")
    parser.add_argument("--out-pdf", default=str(OUTPUT_PDF_DEFAULT), help="Caminho do PDF de saída")
    parser.add_argument("--base-images", default="images", help="Pasta base das imagens (relativa ou absoluta)")
    parser.add_argument("--no-pdf", action="store_true", help="Gera apenas o HTML, não converte para PDF")
    parser.add_argument("--apenas-onu", action="store_true", help="Inclui apenas países membros da ONU")
    parser.add_argument("--limit", type=int, default=None, help="Limita a quantidade de países (para testes)")
    args = parser.parse_args()

    with open(args.data, encoding="utf-8") as f:
        countries = json.load(f)

    if args.apenas_onu:
        countries = [c for c in countries if c.get("onu")]

    countries = sorted(countries, key=lambda c: c.get("nome") or "")

    if args.limit:
        countries = countries[: args.limit]

    html = build_full_html(countries, args.base_images)

    out_html = Path(args.out_html)
    out_html.write_text(html, encoding="utf-8")
    print(f"[OK] HTML gerado: {out_html}  ({len(countries)} países, "
          f"{2 * -(-len(countries) // (COLS * ROWS))} páginas)")

    if not args.no_pdf:
        out_pdf = Path(args.out_pdf)
        cmd = [
            "wkhtmltopdf",
            "--enable-local-file-access",
            "--page-size", "A4",
            "--margin-top", "0",
            "--margin-bottom", "0",
            "--margin-left", "0",
            "--margin-right", "0",
            str(out_html),
            str(out_pdf),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("[ERRO] Falha ao gerar PDF com wkhtmltopdf:")
            print(result.stderr)
        else:
            print(f"[OK] PDF gerado: {out_pdf}")


if __name__ == "__main__":
    main()