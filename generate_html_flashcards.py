#!/usr/bin/env python3
"""
generate_html_flashcards.py
Gera flashcards.html com flashcards de países para impressão A4.

Uso:
    python generate_html_flashcards.py

Para imprimir no Chrome/Edge:
    Ctrl+P → Mais configurações:
      • Tamanho: A4
      • Margens: Nenhuma
      • Imprimir planos de fundo: Ativado
      • Escala: 100%

Dependências:
    pip install Pillow
"""

import json
import os
import sys
from html import escape
from PIL import Image


# ─── Dimensões (mm) ───────────────────────────────────────────────────────────

CARD_W        = 85.6    # Largura do cartão (ISO crédito)
CARD_H        = 53.98   # Altura do cartão  (ISO crédito)
COL_GAP       = 3.0     # Espaço entre coluna frente e verso
ROW_GAP       = 2.0     # Espaço entre linhas
PADDING       = 2.0     # Padding interno do verso
ROWS_PER_PAGE = 5

PAGE_W = 210.0
PAGE_H = 297.0

GRID_W = 2 * CARD_W + COL_GAP                                         # 174.2 mm
GRID_H = ROWS_PER_PAGE * CARD_H + (ROWS_PER_PAGE - 1) * ROW_GAP     # 277.9 mm
MARGIN_L = (PAGE_W - GRID_W) / 2                                       # 17.9  mm
MARGIN_T = (PAGE_H - GRID_H) / 2                                       # 9.55  mm

# ─── Cores (CMYK → Hex RGB) ───────────────────────────────────────────────────

CONTINENT_ORDER = ["África", "Américas", "Ásia", "Europa", "Oceania", "Territórios"]


def cmyk_to_hex(c, m, y, k):
    r = round(255 * (1 - c) * (1 - k))
    g = round(255 * (1 - m) * (1 - k))
    b = round(255 * (1 - y) * (1 - k))
    return f"#{r:02x}{g:02x}{b:02x}"


# Tons claros para o fundo do verso dos cartões
CARD_BG = {
    "África":      cmyk_to_hex(0.00, 0.12, 0.30, 0.05),  # bege cálido
    "Américas":    cmyk_to_hex(0.10, 0.00, 0.22, 0.05),  # verde claro
    "Ásia":        cmyk_to_hex(0.22, 0.05, 0.00, 0.05),  # azul claro
    "Europa":      cmyk_to_hex(0.15, 0.00, 0.08, 0.05),  # verde-azulado
    "Oceania":     cmyk_to_hex(0.18, 0.05, 0.08, 0.02),  # ciano claro
    "Territórios": cmyk_to_hex(0.00, 0.00, 0.00, 0.08),  # cinza
}

# Tons médios para a barra do cabeçalho do verso
HEADER_BG = {
    "África":      cmyk_to_hex(0.00, 0.18, 0.42, 0.08),
    "Américas":    cmyk_to_hex(0.16, 0.00, 0.33, 0.08),
    "Ásia":        cmyk_to_hex(0.34, 0.08, 0.00, 0.08),
    "Europa":      cmyk_to_hex(0.24, 0.00, 0.13, 0.08),
    "Oceania":     cmyk_to_hex(0.28, 0.08, 0.13, 0.04),
    "Territórios": cmyk_to_hex(0.00, 0.00, 0.00, 0.18),
}

# Tons mais fortes para as páginas separadoras de continente
SEP_BG = {
    "África":      cmyk_to_hex(0.00, 0.22, 0.55, 0.10),
    "Américas":    cmyk_to_hex(0.22, 0.00, 0.44, 0.10),
    "Ásia":        cmyk_to_hex(0.44, 0.10, 0.00, 0.10),
    "Europa":      cmyk_to_hex(0.30, 0.00, 0.17, 0.10),
    "Oceania":     cmyk_to_hex(0.36, 0.10, 0.17, 0.05),
    "Territórios": cmyk_to_hex(0.00, 0.00, 0.00, 0.22),
}


def get_card_bg(continent):
    return CARD_BG.get(continent, CARD_BG["Territórios"])

def get_header_bg(continent):
    return HEADER_BG.get(continent, HEADER_BG["Territórios"])

def get_sep_bg(continent):
    return SEP_BG.get(continent, SEP_BG["Territórios"])


# ─── Dados ────────────────────────────────────────────────────────────────────

def normalize_region(raw) -> str:
    if not raw or not isinstance(raw, str):
        return "Territórios"
    r = raw.strip()
    if "América" in r or "America" in r:
        return "Américas"
    for c in CONTINENT_ORDER:
        if r.startswith(c) or c in r:
            return c
    return "Territórios"


def load_and_sort(data_path: str) -> dict:
    with open(data_path, encoding="utf-8") as f:
        countries = json.load(f)
    grouped = {c: [] for c in CONTINENT_ORDER}
    for country in countries:
        loc = country.get("localizacao", "")
        raw = loc.get("regiao", "") if isinstance(loc, dict) else ""
        grouped[normalize_region(raw)].append(country)
    for c in grouped:
        grouped[c].sort(key=lambda x: x.get("nome", "").lower())
    return grouped


def is_portrait(images_dir: str, filename: str) -> bool:
    if not filename:
        return False
    path = os.path.join(images_dir, filename)
    if not os.path.exists(path):
        return False
    try:
        img = Image.open(path)
        return img.height > img.width
    except Exception:
        return False


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def esc(s) -> str:
    return escape(str(s)) if s else ""


# ─── CSS ──────────────────────────────────────────────────────────────────────

def build_css() -> str:
    return f"""
    /* ── Reset ── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    @page {{ size: A4 portrait; margin: 0; }}

    body {{
        font-family: Helvetica, Arial, sans-serif;
    }}

    /* ── Visualização em tela ── */
    @media screen {{
        body {{
            background: #888;
            padding: 10mm;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8mm;
        }}
        .page {{
            box-shadow: 0 4px 20px rgba(0,0,0,0.35);
        }}
    }}

    /* ── Página A4 ── */
    .page {{
        width: {PAGE_W}mm;
        height: {PAGE_H}mm;
        position: relative;
        overflow: hidden;
        background: white;
        page-break-after: always;
        break-after: page;
    }}

    /* ── Separador de continente ── */
    .sep-page {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 5mm;
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
    }}
    .sep-name {{
        font-size: 44pt;
        font-weight: 900;
        letter-spacing: 6pt;
        text-transform: uppercase;
        color: rgba(0,0,0,0.60);
    }}
    .sep-sub {{
        font-size: 9pt;
        font-weight: 400;
        letter-spacing: 3pt;
        text-transform: uppercase;
        color: rgba(0,0,0,0.35);
    }}

    /* ── Grade de cartões ── */
    .card-grid {{
        position: absolute;
        top: {MARGIN_T:.4f}mm;
        left: {MARGIN_L:.4f}mm;
        display: flex;
        flex-direction: column;
        gap: {ROW_GAP}mm;
    }}
    .card-row {{
        display: flex;
        gap: {COL_GAP}mm;
    }}

    /* ── Cartão base ── */
    .card {{
        width: {CARD_W}mm;
        height: {CARD_H}mm;
        overflow: hidden;
        flex-shrink: 0;
        position: relative;
        z-index: 1;            /* cobre as marcas de corte */
    }}

    /* ── Frente: Bandeira ── */
    .card-flag img {{
        display: block;
        width: 100%;
        height: 100%;
        /* sem preservar proporção: preenche 100% do slot, igual ao PDF */
    }}
    /* Bandeiras retrato: rotaciona 90° para preencher o slot paisagem */
    .card-flag.portrait img {{
        position: absolute;
        width: {CARD_H}mm;
        height: {CARD_W}mm;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(90deg);
    }}
    .card-flag.no-image {{
        background: #e0e0e0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #999;
        font-size: 6pt;
    }}

    /* ── Verso: estrutura ── */
    .card-info {{
        display: flex;
        flex-direction: column;
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
    }}

    /* Cabeçalho colorido (região / nome / capital) */
    .info-header {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.6mm {PADDING}mm 1.4mm;
        flex-shrink: 0;
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
    }}
    .info-region {{
        font-size: 4pt;
        font-weight: 700;
        letter-spacing: 1pt;
        text-transform: uppercase;
        color: rgba(0,0,0,0.55);
        line-height: 1.5;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: {CARD_W - 2 * PADDING}mm;
    }}
    .info-name {{
        font-size: 10pt;
        font-weight: 900;
        color: rgba(0,0,0,0.82);
        line-height: 1.2;
        text-align: center;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: {CARD_W - 2 * PADDING}mm;
        margin-top: 0.3mm;
    }}
    .info-capital {{
        font-size: 5.5pt;
        font-weight: 400;
        color: rgba(0,0,0,0.55);
        line-height: 1.5;
        margin-top: 0.5mm;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: {CARD_W - 2 * PADDING}mm;
    }}

    /* Divisor */
    .info-divider {{
        height: 0.5pt;
        background: rgba(0,0,0,0.18);
        margin: 0 {PADDING}mm;
        flex-shrink: 0;
    }}

    /* Área de dados */
    .info-data {{
        flex: 1;
        display: flex;
        flex-direction: column;
        padding: 1.4mm {PADDING}mm {PADDING}mm;
        gap: 0.7mm;
        overflow: hidden;
    }}
    .data-row {{
        display: flex;
        align-items: baseline;
        gap: 1mm;
        overflow: hidden;
    }}
    .data-label {{
        font-size: 4.5pt;
        font-weight: 700;
        color: rgba(0,0,0,0.55);
        white-space: nowrap;
        flex-shrink: 0;
        line-height: 1.5;
    }}
    .data-value {{
        font-size: 4.5pt;
        font-weight: 400;
        color: rgba(0,0,0,0.85);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
        min-width: 0;           /* necessário para ellipsis em flex */
        line-height: 1.5;
    }}

    /* ── Marcas de corte ── */
    /* z-index: 0 → ficam atrás dos cartões (z-index: 1).
       O background dos cartões cobre as linhas dentro da grade;
       apenas as partes nas margens brancas ficam visíveis. */
    .cut-h, .cut-v {{
        position: absolute;
        z-index: 0;
        pointer-events: none;
    }}
    .cut-h {{
        left: 0; right: 0;
        height: 0.25pt;
        background: rgba(0,0,0,0.40);
    }}
    .cut-v {{
        top: 0; bottom: 0;
        width: 0.25pt;
        background: rgba(0,0,0,0.40);
    }}
"""


# ─── Marcas de corte ─────────────────────────────────────────────────────────

def build_cut_marks(n_rows: int) -> str:
    lines = []

    # Linhas horizontais: uma acima e uma abaixo de cada linha de cartões
    ys = set()
    for i in range(n_rows):
        y_top = MARGIN_T + i * (CARD_H + ROW_GAP)
        ys.add(y_top)
        ys.add(y_top + CARD_H)

    for y in sorted(ys):
        lines.append(f'<div class="cut-h" style="top:{y:.4f}mm;"></div>')

    # Linhas verticais: bordas esquerda e direita de cada coluna
    xs = [
        MARGIN_L,
        MARGIN_L + CARD_W,
        MARGIN_L + CARD_W + COL_GAP,
        MARGIN_L + CARD_W + COL_GAP + CARD_W,
    ]
    for x in xs:
        lines.append(f'<div class="cut-v" style="left:{x:.4f}mm;"></div>')

    return "\n    ".join(lines)


# ─── Cartão frente (bandeira) ─────────────────────────────────────────────────

def card_flag_html(images_dir: str, country: dict) -> str:
    filename = country.get("arquivo_bandeira", "")
    nome     = esc(country.get("nome", ""))

    if not filename or not os.path.exists(os.path.join(images_dir, filename)):
        return f'<div class="card card-flag no-image">{nome}</div>'

    portrait_cls = " portrait" if is_portrait(images_dir, filename) else ""
    src = f"images/{esc(filename)}"

    return (
        f'<div class="card card-flag{portrait_cls}">'
        f'<img src="{src}" alt="{nome}">'
        f'</div>'
    )


# ─── Cartão verso (informações) ───────────────────────────────────────────────

def card_info_html(country: dict, continent: str) -> str:
    loc       = country.get("localizacao", "")
    region_raw = loc.get("regiao", "") if isinstance(loc, dict) else ""

    region_label = esc(region_raw.upper() if region_raw else "TERRITÓRIO")
    nome    = esc(country.get("nome", ""))
    capital = esc(country.get("capital", "") or "—")

    bg_card   = get_card_bg(continent)
    bg_header = get_header_bg(continent)

    # Campos de dados — linha omitida se valor vazio
    data_fields = [
        ("Nome oficial",  country.get("nome_oficial", "")),
        ("Idioma",        country.get("idioma", "")),
        ("Moeda",         country.get("moeda", "")),
        ("Governo",       country.get("forma_de_governo", "")),
        ("Fundação/Ind.", country.get("ano_independencia_fundacao", "")),
    ]

    data_rows = ""
    for label, value in data_fields:
        if not str(value).strip():
            continue
        data_rows += (
            f'\n          <div class="data-row">'
            f'<span class="data-label">{esc(label)}:</span>'
            f'<span class="data-value">{esc(str(value))}</span>'
            f'</div>'
        )

    return f"""<div class="card card-info" style="background:{bg_card};">
      <div class="info-header" style="background:{bg_header};">
        <span class="info-region">{region_label}</span>
        <span class="info-name">{nome}</span>
        <span class="info-capital">{capital}</span>
      </div>
      <div class="info-divider"></div>
      <div class="info-data">{data_rows}
      </div>
    </div>"""


# ─── Páginas ─────────────────────────────────────────────────────────────────

def separator_page(continent: str, count: int) -> str:
    bg  = get_sep_bg(continent)
    sub = f"{count} país{'es' if count != 1 else ''} &middot; Jogo de Adivinhação"
    return (
        f'\n<div class="page sep-page" style="background:{bg};">'
        f'\n  <span class="sep-name">{esc(continent)}</span>'
        f'\n  <span class="sep-sub">{sub}</span>'
        f'\n</div>'
    )


def card_page(batch: list, images_dir: str) -> str:
    cut_marks = build_cut_marks(len(batch))

    rows = ""
    for country in batch:
        loc       = country.get("localizacao", "")
        raw       = loc.get("regiao", "") if isinstance(loc, dict) else ""
        continent = normalize_region(raw)

        flag = card_flag_html(images_dir, country)
        info = card_info_html(country, continent)

        rows += f'\n      <div class="card-row">\n        {flag}\n        {info}\n      </div>'

    return (
        f'\n<div class="page">'
        f'\n  {cut_marks}'
        f'\n  <div class="card-grid">{rows}'
        f'\n  </div>'
        f'\n</div>'
    )


# ─── HTML completo ────────────────────────────────────────────────────────────

def build_html(grouped: dict, images_dir: str) -> str:
    pages = []

    for continent in CONTINENT_ORDER:
        countries = grouped.get(continent, [])
        if not countries:
            continue
        pages.append(separator_page(continent, len(countries)))
        for batch in chunks(countries, ROWS_PER_PAGE):
            pages.append(card_page(batch, images_dir))

    css = build_css()

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Flashcards de Países — Jogo de Adivinhação</title>
  <style>{css}  </style>
</head>
<body>
{"".join(pages)}
</body>
</html>
"""


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    base_dir    = os.path.dirname(os.path.abspath(__file__))
    data_path   = os.path.join(base_dir, "data.json")
    images_dir  = os.path.join(base_dir, "images")
    output_path = os.path.join(base_dir, "flashcards.html")

    if not os.path.exists(data_path):
        print(f"Erro: data.json não encontrado em {data_path}")
        sys.exit(1)
    if not os.path.isdir(images_dir):
        print(f"Erro: pasta images/ não encontrada em {images_dir}")
        sys.exit(1)

    print("Carregando dados...")
    grouped = load_and_sort(data_path)

    total = sum(len(v) for v in grouped.values())
    print(f"Total de países/territórios: {total}")
    for c in CONTINENT_ORDER:
        n = len(grouped[c])
        if n:
            print(f"  {c}: {n}")

    print(f"\nGerando HTML: {output_path}")
    html = build_html(grouped, images_dir)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) // 1024
    print(f"HTML gerado com sucesso: {output_path} ({size_kb} KB)")
    print()
    print("Para imprimir:")
    print("  1. Abra flashcards.html no Chrome ou Edge")
    print("  2. Ctrl+P  →  Mais configurações:")
    print("       Tamanho:                  A4")
    print("       Margens:                  Nenhuma")
    print("       Imprimir planos de fundo: Ativado ✓")
    print("       Escala:                   100%")


if __name__ == "__main__":
    main()
