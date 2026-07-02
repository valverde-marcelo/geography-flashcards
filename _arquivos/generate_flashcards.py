#!/usr/bin/env python3
"""
generate_flashcards.py
Gera um PDF A4 em CMYK com flashcards frente/verso de países para impressão.

Execução:
    python generate_flashcards.py

Dependências:
    pip install reportlab Pillow

Saída:
    flashcards.pdf na mesma pasta do script
"""

import json
import os
import sys
from io import BytesIO

from PIL import Image
from reportlab.lib.colors import CMYKColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES — ajuste aqui para alterar o layout
# ─────────────────────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4          # 595.28 × 841.89 pt (A4)

CARD_W = 85.6 * mm           # Largura do cartão (padrão ISO crédito)
CARD_H = 53.98 * mm          # Altura do cartão (padrão ISO crédito)

COL_GAP = 3 * mm             # Espaço entre coluna frente e verso (para guilhotina)
ROW_GAP = 2 * mm             # Espaço entre linhas de cartões
PADDING = 2 * mm             # Padding interno do verso

ROWS_PER_PAGE = 5

# Margens — calculadas para centralizar a grade na página A4
GRID_W = 2 * CARD_W + COL_GAP
GRID_H = ROWS_PER_PAGE * CARD_H + (ROWS_PER_PAGE - 1) * ROW_GAP
MARGIN_L = (PAGE_W - GRID_W) / 2
MARGIN_B = (PAGE_H - GRID_H) / 2

# Fontes (Helvetica embutida no ReportLab — sem instalação extra)
FONT   = "Helvetica"
FONT_B = "Helvetica-Bold"

# Tamanhos de fonte (pt)
SZ_REGION  = 5
SZ_NAME    = 9
SZ_CAPITAL = 5.5
SZ_DATA    = 5

# Line heights (pt) — espaço entre baselines
LD_REGION  = 7.0
LD_NAME    = 12.0
LD_CAPITAL = 7.5
LD_DATA    = 7.0

# Marcas de corte
CUT_COLOR = CMYKColor(0, 0, 0, 1)   # Preto de registro
CUT_W     = 0.25                     # Espessura da hairline (pt)

# ─────────────────────────────────────────────────────────────────────────────
# CORES POR CONTINENTE (CMYK — tons claros para facilitar separação física)
# ─────────────────────────────────────────────────────────────────────────────

CONTINENT_ORDER = ["África", "Américas", "Ásia", "Europa", "Oceania", "Territórios"]

CONTINENT_COLORS = {
    "África":      CMYKColor(0.00, 0.12, 0.30, 0.05),  # bege cálido
    "Américas":    CMYKColor(0.10, 0.00, 0.22, 0.05),  # verde claro
    "Ásia":        CMYKColor(0.22, 0.05, 0.00, 0.05),  # azul claro
    "Europa":      CMYKColor(0.15, 0.00, 0.08, 0.05),  # verde-azulado claro
    "Oceania":     CMYKColor(0.18, 0.05, 0.08, 0.02),  # ciano claro
    "Territórios": CMYKColor(0.00, 0.00, 0.00, 0.08),  # cinza claro
}


def get_continent_color(continent: str) -> CMYKColor:
    return CONTINENT_COLORS.get(continent, CONTINENT_COLORS["Territórios"])


def normalize_region(region_raw) -> str:
    """Normaliza o valor de localizacao.regiao para um dos continentes da ordem."""
    if not region_raw or not isinstance(region_raw, str):
        return "Territórios"
    r = region_raw.strip()
    if "América" in r or "America" in r:
        return "Américas"
    for continent in CONTINENT_ORDER:
        if r.startswith(continent) or continent in r:
            return continent
    return "Territórios"


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

def truncate(c, text: str, font: str, size: float, max_w: float) -> str:
    """Trunca o texto com '…' para que caiba em max_w pontos."""
    if c.stringWidth(text, font, size) <= max_w:
        return text
    while text:
        text = text[:-1]
        if c.stringWidth(text + "…", font, size) <= max_w:
            return text + "…"
    return "…"


def chunks(lst: list, n: int):
    """Divide uma lista em sublistas de tamanho n."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def load_flag(images_dir: str, filename: str) -> tuple:
    """
    Carrega a imagem PNG da bandeira.
    Retorna (ImageReader, is_portrait).
    is_portrait = True se a bandeira for mais alta do que larga.
    """
    if not filename:
        return None, False
    path = os.path.join(images_dir, filename)
    if not os.path.exists(path):
        return None, False
    img = Image.open(path).convert("RGB")
    is_portrait = img.height > img.width
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf), is_portrait


def load_and_sort_countries(data_path: str) -> dict:
    """
    Lê data.json, agrupa por continente e ordena por nome dentro de cada grupo.
    Retorna: { continente: [lista de países] }
    """
    with open(data_path, encoding="utf-8") as f:
        countries = json.load(f)

    grouped = {c: [] for c in CONTINENT_ORDER}

    for country in countries:
        loc = country.get("localizacao", "")
        region_raw = loc.get("regiao", "") if isinstance(loc, dict) else ""
        continent = normalize_region(region_raw)
        grouped[continent].append(country)

    for continent in grouped:
        grouped[continent].sort(key=lambda x: x.get("nome", "").lower())

    return grouped


# ─────────────────────────────────────────────────────────────────────────────
# MARCAS DE CORTE
# ─────────────────────────────────────────────────────────────────────────────

def compute_cut_positions(n: int) -> tuple:
    """
    Calcula as posições das marcas de corte para uma página com n linhas de cartões.
    Retorna (row_ys, col_xs):
      row_ys — conjunto de coordenadas y (bordas inferior e superior de cada cartão)
      col_xs — lista de coordenadas x (bordas verticais da grade)
    """
    col_xs = [
        MARGIN_L,                               # borda esquerda da frente
        MARGIN_L + CARD_W,                      # borda direita da frente
        MARGIN_L + CARD_W + COL_GAP,            # borda esquerda do verso
        MARGIN_L + CARD_W + COL_GAP + CARD_W,  # borda direita do verso
    ]

    row_ys = set()
    for i in range(n):
        row_from_bottom = n - 1 - i
        y_bot = MARGIN_B + row_from_bottom * (CARD_H + ROW_GAP)
        row_ys.add(y_bot)
        row_ys.add(y_bot + CARD_H)

    return sorted(row_ys), col_xs


def draw_cut_marks(c, row_ys: list, col_xs: list):
    """
    Desenha hairlines de corte apenas nas margens da página (não sobre o conteúdo).
    As linhas ficam visíveis ao redor da grade para orientar o operador da guilhotina.
    """
    gap_in = 1 * mm  # folga de 1 mm entre a borda do cartão e o início da hairline

    c.saveState()
    c.setStrokeColor(CUT_COLOR)
    c.setLineWidth(CUT_W)

    for y in row_ys:
        # Margem esquerda
        c.line(0, y, MARGIN_L - gap_in, y)
        # Margem direita
        c.line(MARGIN_L + GRID_W + gap_in, y, PAGE_W, y)

    for x in col_xs:
        # Margem inferior
        c.line(x, 0, x, MARGIN_B - gap_in)
        # Margem superior
        c.line(x, MARGIN_B + GRID_H + gap_in, x, PAGE_H)

    c.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# CARTÃO FRENTE — BANDEIRA
# ─────────────────────────────────────────────────────────────────────────────

def draw_flag_card(c, x: float, y: float, w: float, h: float,
                   img_reader, is_portrait: bool):
    """
    Desenha a frente do cartão preenchendo 100% do slot (x, y, w, h).
    Para bandeiras em formato retrato (height > width), a imagem é rotacionada
    90° dentro do slot para melhor aproveitamento visual.
    y é a coordenada inferior do cartão (ReportLab: origem inferior-esquerda).
    """
    if img_reader is None:
        c.saveState()
        c.setFillColor(CMYKColor(0, 0, 0, 0.08))
        c.rect(x, y, w, h, fill=1, stroke=0)
        c.restoreState()
        return

    if is_portrait:
        # Rotacionar 90° em torno do centro do slot
        c.saveState()
        c.translate(x + w / 2, y + h / 2)
        c.rotate(90)
        # Com a rotação, w e h ficam trocados para o drawImage
        c.drawImage(img_reader, -h / 2, -w / 2, width=h, height=w,
                    preserveAspectRatio=False, mask="auto")
        c.restoreState()
    else:
        c.drawImage(img_reader, x, y, width=w, height=h,
                    preserveAspectRatio=False, mask="auto")


# ─────────────────────────────────────────────────────────────────────────────
# CARTÃO VERSO — INFORMAÇÕES DO PAÍS
# ─────────────────────────────────────────────────────────────────────────────

def draw_info_card(c, x: float, y: float, w: float, h: float,
                   country: dict, bg_color: CMYKColor):
    """
    Desenha o verso do cartão com as informações do país.
    Sempre em formato paisagem, independente da orientação da bandeira.
    y é a coordenada inferior do cartão.
    """
    # ── Fundo colorido por continente ──
    c.saveState()
    c.setFillColor(bg_color)
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.restoreState()

    inner_w = w - 2 * PADDING    # largura útil para texto
    cx  = x + w / 2              # centro horizontal
    lx  = x + PADDING            # margem esquerda do texto
    rx  = x + w - PADDING        # margem direita (para separador)
    cur_y = y + h - PADDING      # cursor Y: decresce de cima para baixo

    # ── Região ──
    loc = country.get("localizacao", "")
    region_raw = loc.get("regiao", "") if isinstance(loc, dict) else ""
    region_label = region_raw if region_raw else "Território"

    cur_y -= LD_REGION
    c.saveState()
    c.setFont(FONT, SZ_REGION)
    c.setFillColor(CMYKColor(0, 0, 0, 0.55))
    c.drawCentredString(cx, cur_y,
                        truncate(c, region_label.upper(), FONT, SZ_REGION, inner_w))
    c.restoreState()

    # ── Nome do País ──
    cur_y -= LD_NAME
    c.saveState()
    c.setFont(FONT_B, SZ_NAME)
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    c.drawCentredString(cx, cur_y,
                        truncate(c, country.get("nome", ""), FONT_B, SZ_NAME, inner_w))
    c.restoreState()

    # ── Capital ──
    cur_y -= LD_CAPITAL
    c.saveState()
    c.setFont(FONT, SZ_CAPITAL)
    c.setFillColor(CMYKColor(0, 0, 0, 0.55))
    c.drawCentredString(cx, cur_y,
                        truncate(c, country.get("capital", ""), FONT, SZ_CAPITAL, inner_w))
    c.restoreState()

    # ── Linha separadora ──
    cur_y -= 3
    c.saveState()
    c.setStrokeColor(CMYKColor(0, 0, 0, 0.25))
    c.setLineWidth(0.4)
    c.line(lx, cur_y, rx, cur_y)
    c.restoreState()
    cur_y -= 2  # folga após o separador

    # ── Campos de dados (justificados à esquerda) ──
    # Linhas com valor vazio são omitidas automaticamente.
    data_fields = [
        ("Nome oficial",                   country.get("nome_oficial", "")),
        ("Idioma",                         country.get("idioma", "")),
        ("Moeda",                          country.get("moeda", "")),
        ("Forma de governo",               country.get("forma_de_governo", "")),
        ("Ano de fundação/independência",  country.get("ano_independencia_fundacao", "")),
    ]

    c.setFont(FONT, SZ_DATA)
    c.setFillColor(CMYKColor(0, 0, 0, 1))

    for label, value in data_fields:
        if not str(value).strip():
            continue                        # omite linha se valor vazio
        cur_y -= LD_DATA
        if cur_y < y + PADDING:
            break                           # não ultrapassa a borda inferior
        full_line = f"{label}: {value}"
        c.drawString(lx, cur_y,
                     truncate(c, full_line, FONT, SZ_DATA, inner_w))


# ─────────────────────────────────────────────────────────────────────────────
# SEPARADOR DE CONTINENTE
# ─────────────────────────────────────────────────────────────────────────────

def draw_continent_separator(c, continent: str, color: CMYKColor):
    """Insere uma página de separação com o nome do continente sobre fundo colorido."""
    c.saveState()
    c.setFillColor(color)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(CMYKColor(0, 0, 0, 0.75))
    c.setFont(FONT_B, 36)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2, continent.upper())
    c.restoreState()
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# RENDERIZAÇÃO DE PÁGINA
# ─────────────────────────────────────────────────────────────────────────────

def render_page(c, countries: list, images_dir: str):
    """
    Renderiza uma página com até ROWS_PER_PAGE países.
    Coluna esquerda: frente (bandeira). Coluna direita: verso (informações).
    """
    n = len(countries)
    row_ys, col_xs = compute_cut_positions(n)
    draw_cut_marks(c, row_ys, col_xs)

    x_flag = MARGIN_L
    x_info = MARGIN_L + CARD_W + COL_GAP

    for i, country in enumerate(countries):
        # Linha 0 = topo visual → maior y (ReportLab: y cresce para cima)
        row_from_bottom = n - 1 - i
        y = MARGIN_B + row_from_bottom * (CARD_H + ROW_GAP)

        img_reader, is_portrait = load_flag(images_dir, country.get("arquivo_bandeira", ""))

        loc = country.get("localizacao", "")
        region_raw = loc.get("regiao", "") if isinstance(loc, dict) else ""
        continent = normalize_region(region_raw)
        bg_color = get_continent_color(continent)

        draw_flag_card(c, x_flag, y, CARD_W, CARD_H, img_reader, is_portrait)
        draw_info_card(c, x_info, y, CARD_W, CARD_H, country, bg_color)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    base_dir    = os.path.dirname(os.path.abspath(__file__))
    data_path   = os.path.join(base_dir, "data.json")
    images_dir  = os.path.join(base_dir, "images")
    output_path = os.path.join(base_dir, "flashcards.pdf")

    # Validações iniciais
    if not os.path.exists(data_path):
        print(f"Erro: data.json não encontrado em {data_path}")
        sys.exit(1)
    if not os.path.isdir(images_dir):
        print(f"Erro: pasta images/ não encontrada em {images_dir}")
        sys.exit(1)

    print("Carregando dados...")
    grouped = load_and_sort_countries(data_path)

    total = sum(len(v) for v in grouped.values())
    print(f"Total de países/territórios: {total}")
    for continent in CONTINENT_ORDER:
        count = len(grouped[continent])
        if count:
            print(f"  {continent}: {count}")

    print(f"\nGerando PDF: {output_path}")
    c = rl_canvas.Canvas(output_path, pagesize=A4)
    c.setPageCompression(1)
    c.setTitle("Flashcards de Países — Jogo de Adivinhação")
    c.setAuthor("generate_flashcards.py")
    c.setSubject("Flashcards para impressão — CMYK A4")

    for continent in CONTINENT_ORDER:
        countries = grouped.get(continent, [])
        if not countries:
            continue

        color = get_continent_color(continent)
        draw_continent_separator(c, continent, color)

        page_count = 0
        for batch in chunks(countries, ROWS_PER_PAGE):
            render_page(c, batch, images_dir)
            page_count += 1

        print(f"  {continent}: {len(countries)} países → {page_count} página(s)")

    c.save()
    print(f"\nPDF gerado com sucesso: {output_path}")


if __name__ == "__main__":
    main()
