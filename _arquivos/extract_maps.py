#!/usr/bin/env python3
"""
extract_maps.py
Extrai mapas SVG e PNG de cada país destacado no seu continente,
reproduzindo a lógica de drawWorldChoroplet() do Atlas Escolar IBGE.

Fontes (engenharia reversa de https://atlasescolar.ibge.gov.br/bandeiras-dos-paises.html):
  SVG mundial : https://atlasescolar.ibge.gov.br/templates/atlas_2022/paises_mundo.svg
  Dados países: https://atlasescolar.ibge.gov.br/templates/atlas_2022/js/script.js

Saída:
  images/mapas/{slug}.svg  — SVG vetorial do país destacado
  images/mapas/{slug}.png  — PNG rasterizado (1200×750 px)

Dependências:
  pip install requests lxml pymupdf pillow
"""

import os
import re
import io
import json
import sys
import requests
from lxml import etree

# ── configuração ─────────────────────────────────────────────────────────────

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#OUTPUT_DIR = os.path.join(BASE_DIR, "images", "mapas")
OUTPUT_DIR = os.path.join(BASE_DIR, "images", "mapas_3")

SCRIPT_JS_URL = "https://atlasescolar.ibge.gov.br/templates/atlas_2022/js/script.js"
SVG_URL       = "https://atlasescolar.ibge.gov.br/templates/atlas_2022/paises_mundo.svg"

PNG_W = 1200
PNG_H =  750

# Fator de zoom: quanto maior, mais perto; quanto menor, mais continente ao redor
# 1.0 = zoom original do IBGE | 0.6 = 40% afastado | 0.4 = 60% afastado
ZOOM_FACTOR = 3

# Fallback de matrix por continente (quando o país não tem matrix própria)
MATRIX_FALLBACK = {
    "europa":  "0.0002, 0, 0, -0.0002, -156, 15",
    "asia":    "0.0002, 0, 0, -0.0002, -156, 15",
    "america": "0.00024, 0, 0, -0.00024, 256, 15",
    "africa":  "0.0004, 0, 0, -0.0004, -75, 0",
    "oceania": "0.0002, 0, 0, -0.0002, -300, -50",
}

COLOR_DEFAULT  = "#c8d4d8"   # países sem destaque
COLOR_SELECTED = "#e05c00"   # país selecionado (laranja IBGE)
COLOR_STROKE   = "#ffffff"   # borda entre países

# Largura de borda DESEJADA na imagem final, em pixels (independente do
# zoom_factor ou da escala da matrix — ver cálculo em build_svg).
STROKE_PX_DEFAULT  = 0.8
STROKE_PX_SELECTED = 1.4

CSS = f"""\
path {{ fill: {COLOR_DEFAULT}; stroke: {COLOR_STROKE}; stroke-width: 100; }}
path.reg-selected {{ fill: {COLOR_SELECTED}; stroke: {COLOR_STROKE}; stroke-width: 150; }}
"""

SVG_NS = "http://www.w3.org/2000/svg"


# ── coleta ────────────────────────────────────────────────────────────────────

def fetch_paises() -> list:
    """Extrai o array 'paises' do script.js do IBGE."""
    print("  Baixando script.js...", end=" ", flush=True)
    resp = requests.get(SCRIPT_JS_URL, timeout=30)
    resp.encoding = "utf-8"
    m = re.search(r"const paises\s*=\s*(\[.*?\]);", resp.text, re.DOTALL)
    if not m:
        raise RuntimeError("Array 'paises' não encontrado no script.js")
    data = json.loads(m.group(1))
    print(f"{len(data)} países")
    return data


def fetch_world_svg() -> tuple:
    """Baixa paises_mundo.svg e retorna (etree_root, viewBox_str)."""
    print("  Baixando paises_mundo.svg...", end=" ", flush=True)
    resp = requests.get(SVG_URL, timeout=60)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)
    viewbox = (
        root.get("viewBox")
        or root.get("viewbox")
        or "0 0 100000 60000"
    )
    print(f"{len(resp.content) // 1024} KB | viewBox: {viewbox}")
    return root, viewbox


# ── geometria do país (para centralização real) ───────────────────────────────

_PATH_CMD_RE   = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)")
_PATH_NUM_RE   = re.compile(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?")


def _path_points(d: str) -> list:
    """
    Faz o parse mínimo de um atributo 'd' de <path> e retorna a lista de
    pontos (x, y) ABSOLUTOS por onde o traçado passa (incluindo pontos de
    controle de curvas). Suficiente para calcular bounding box — não
    precisa ser um parser SVG completo nem renderizar a curva certinho.
    """
    x, y = 0.0, 0.0
    start_x, start_y = 0.0, 0.0
    points = []

    for cmd, nums_str in _PATH_CMD_RE.findall(d):
        nums = [float(n) for n in _PATH_NUM_RE.findall(nums_str)]
        upper = cmd.upper()
        rel = cmd.islower()

        if upper == "Z":
            x, y = start_x, start_y
            continue

        elif upper in ("M", "L", "T"):
            for i in range(0, len(nums) - 1, 2):
                nx, ny = nums[i], nums[i + 1]
                if rel:
                    nx += x
                    ny += y
                x, y = nx, ny
                points.append((x, y))
                if upper == "M" and i == 0:
                    start_x, start_y = x, y

        elif upper == "H":
            for n in nums:
                x = x + n if rel else n
                points.append((x, y))

        elif upper == "V":
            for n in nums:
                y = y + n if rel else n
                points.append((x, y))

        elif upper == "C":
            for i in range(0, len(nums) - 5, 6):
                x1, y1, x2, y2, ex, ey = nums[i:i + 6]
                if rel:
                    x1 += x; y1 += y; x2 += x; y2 += y; ex += x; ey += y
                points.extend([(x1, y1), (x2, y2), (ex, ey)])
                x, y = ex, ey

        elif upper in ("S", "Q"):
            for i in range(0, len(nums) - 3, 4):
                x1, y1, ex, ey = nums[i:i + 4]
                if rel:
                    x1 += x; y1 += y; ex += x; ey += y
                points.extend([(x1, y1), (ex, ey)])
                x, y = ex, ey

        elif upper == "A":
            for i in range(0, len(nums) - 6, 7):
                ex, ey = nums[i + 5], nums[i + 6]
                if rel:
                    ex += x; ey += y
                points.append((ex, ey))
                x, y = ex, ey

    return points


def get_country_bbox_center(source_root, sigla: str):
    """
    Calcula o centro real (centro da bounding box) do(s) path(s) do país
    'sigla' dentro do SVG-fonte. Retorna (cx, cy) em coordenadas originais
    do mapa-múndi, ou None se nenhum path correspondente for encontrado.
    """
    sigla_up = sigla.upper()
    xs, ys = [], []

    for el in source_root.iter("{%s}path" % SVG_NS):
        d = el.get("d")
        if not d:
            continue
        tokens = [t.upper() for t in el.get("class", "").split()]
        if sigla_up not in tokens:
            continue
        for px, py in _path_points(d):
            xs.append(px)
            ys.append(py)

    if not xs:
        return None

    return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0


# ── geração SVG ───────────────────────────────────────────────────────────────

def build_svg(source_root, sigla: str, matrix: str, viewbox: str,
              zoom_factor: float = ZOOM_FACTOR) -> bytes:
    """
    Constrói SVG com matrix transform, centralizando o país selecionado
    no meio da imagem (PNG_W x PNG_H).

    A escala (zoom) vem da matriz original ('a'/'d', já com zoom_factor
    aplicado). A translação (tx, ty), porém, NÃO vem da matriz original —
    ela é recalculada a partir do centro geométrico REAL do país (bounding
    box do seu próprio path no SVG-fonte). Isso garante que o país fique
    centralizado mesmo que a matriz do IBGE não tenha sido pensada para
    centralizar exatamente em (PNG_W/2, PNG_H/2).

    O viewBox de saída é fixado em "0 0 PNG_W PNG_H" porque é esse o
    espaço de coordenadas para o qual a centralização é calculada.

    zoom_factor:
      - 1.0: zoom original (tight no país)
      - 0.6: 40% zoom out (vê mais continente)
      - 0.4: 60% zoom out (vê muito mais continente)
    """
    # Parse matrix: "a, b, c, d, tx, ty" — usamos apenas a escala (a, d).
    parts = [float(v.strip()) for v in matrix.split(",")]
    a, b, c, d, _tx_original, _ty_original = parts

    scale_x = a * zoom_factor
    scale_y = d * zoom_factor

    # Centro REAL do país, calculado a partir da geometria do próprio path.
    center = get_country_bbox_center(source_root, sigla)
    if center is None:
        # Fallback: se não achar nenhum path com essa sigla, mantém o
        # comportamento antigo (evita crash, mas avisa no log).
        print(f"  [AVISO] Nenhum path encontrado para sigla '{sigla}' "
              f"— centralização pode falhar.", file=sys.stderr)
        center_x, center_y = (PNG_W / 2 - _tx_original) / a, (PNG_H / 2 - _ty_original) / d
    else:
        center_x, center_y = center

    new_tx = PNG_W / 2 - scale_x * center_x
    new_ty = PNG_H / 2 - scale_y * center_y

    matrix_adjusted = f"{scale_x}, {b}, {c}, {scale_y}, {new_tx}, {new_ty}"

    # Largura de borda alvo, em PIXELS da imagem final — convertida para
    # unidades "locais" (pré-transform) dividindo pelo fator de escala,
    # já que stroke-width é especificado no espaço de coordenadas do
    # próprio path (antes do <g transform="matrix(...)"> ser aplicado).
    avg_scale = (abs(scale_x) + abs(scale_y)) / 2.0
    stroke_w_default  = STROKE_PX_DEFAULT  / avg_scale
    stroke_w_selected = STROKE_PX_SELECTED / avg_scale

    svg = etree.Element("{%s}svg" % SVG_NS, nsmap={None: SVG_NS})
    svg.set("viewBox", f"0 0 {PNG_W} {PNG_H}")
    svg.set("width", str(PNG_W))
    svg.set("height", str(PNG_H))

    # Mantém o <style> para navegadores/visualizadores que suportam CSS
    # em SVG — mas NÃO depende dele: cada <path> também recebe fill/
    # stroke/stroke-width como atributos inline, que funcionam mesmo em
    # renderizadores com suporte limitado a CSS (ex.: MuPDF/PyMuPDF),
    # que ignoram <style> e caem no padrão do SVG (fill preto, sem
    # stroke) — essa era a causa do mapa sair preto no PNG.
    style_el = etree.SubElement(svg, "{%s}style" % SVG_NS)
    style_el.text = CSS

    # Aplica matrix transform ao grupo contendo os paths
    g = etree.SubElement(svg, "{%s}g" % SVG_NS)
    g.set("transform", "matrix(%s)" % matrix_adjusted)
    g.set("class", "map-paths-wrapper")

    sigla_up = sigla.upper()
    for el in source_root.iter("{%s}path" % SVG_NS):
        d = el.get("d")
        if not d:
            continue
        src_class = el.get("class", "")
        tokens    = [t.upper() for t in src_class.split()]
        selected  = sigla_up in tokens

        new_path = etree.SubElement(g, "{%s}path" % SVG_NS)
        new_path.set("d", d)
        new_path.set("class", (src_class + " reg-selected").strip() if selected else src_class)

        # Estilo inline — fonte da verdade para qualquer renderizador.
        new_path.set("fill", COLOR_SELECTED if selected else COLOR_DEFAULT)
        new_path.set("stroke", COLOR_STROKE)
        new_path.set("stroke-width", str(stroke_w_selected if selected else stroke_w_default))

    return etree.tostring(svg, xml_declaration=True, encoding="UTF-8", pretty_print=True)



# ── PNG ───────────────────────────────────────────────────────────────────────

def svg_to_png(svg_bytes: bytes, png_path: str):
    #bypass
    #return True
    
    """Converte SVG bytes para PNG via PyMuPDF (fitz) — sem dependências nativas."""
    import fitz  # PyMuPDF
    from PIL import Image

    doc  = fitz.open(stream=svg_bytes, filetype="svg")
    page = doc[0]

    # Escala para o tamanho alvo mantendo proporção
    scale = min(PNG_W / page.rect.width, PNG_H / page.rect.height)
    mat   = fitz.Matrix(scale, scale)
    pix   = page.get_pixmap(matrix=mat, alpha=False)
    doc.close()

    # Centraliza em canvas branco de tamanho exato
    img    = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    canvas = Image.new("RGB", (PNG_W, PNG_H), (255, 255, 255))
    offset = ((PNG_W - img.width) // 2, (PNG_H - img.height) // 2)
    canvas.paste(img, offset)
    canvas.save(png_path, "PNG")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Coletando dados do IBGE Atlas Escolar...")
    paises            = fetch_paises()
    svg_root, viewbox = fetch_world_svg()

    try:
        import fitz  # noqa — verificação de disponibilidade
        have_png = True
    except ImportError:
        have_png = False
        print(
            "\n  AVISO: PyMuPDF não instalado — apenas SVGs serão gerados.\n"
            "  Para gerar PNGs também: pip install pymupdf\n"
        )

    total      = len(paises)
    svg_ok     = 0
    png_ok     = 0
    svg_errors = []
    png_errors = []

    print(f"\nGerando mapas em: {OUTPUT_DIR}\n")

    for i, pais in enumerate(paises, 1):
        sigla      = pais["sigla"]
        slug       = pais["slug"]
        continente = pais.get("continente", "europa")
        matrix     = pais.get("matrix", "").strip()

        if len(matrix) < 3:
            matrix = MATRIX_FALLBACK.get(continente, MATRIX_FALLBACK["europa"])

        svg_path = os.path.join(OUTPUT_DIR, f"{slug}.svg")
        png_path = os.path.join(OUTPUT_DIR, f"{slug}.png")

        # ── SVG ──────────────────────────────────────────────────────────────
        try:
            svg_bytes = build_svg(svg_root, sigla, matrix, viewbox,
                                 zoom_factor=ZOOM_FACTOR)
            with open(svg_path, "wb") as fh:
                fh.write(svg_bytes)
            svg_ok += 1
        except Exception as exc:
            svg_errors.append((slug, str(exc)))
            print(f"  [{i:3d}/{total}] {sigla:<3}  {slug:<48} SVG ERRO: {exc}",
                  file=sys.stderr)
            continue

        # ── PNG ──────────────────────────────────────────────────────────────
        if have_png:
            try:
                svg_to_png(svg_bytes, png_path)
                png_ok += 1
                status = "OK svg+png"
            except Exception as exc:
                png_errors.append((slug, str(exc)))
                status = f"SVG OK | PNG ERRO: {exc}"
        else:
            status = "OK svg"

        print(f"  [{i:3d}/{total}] {sigla:<3}  {slug:<48} {status}")

    print(f"\n{'─' * 60}")
    print(f"SVGs: {svg_ok}/{total}   PNGs: {png_ok}/{total}")

    if svg_errors:
        print(f"\nErros SVG ({len(svg_errors)}):", file=sys.stderr)
        for s, m in svg_errors:
            print(f"  X {s}: {m}", file=sys.stderr)

    if png_errors:
        print(f"\nErros PNG ({len(png_errors)}):", file=sys.stderr)
        for s, m in png_errors:
            print(f"  X {s}: {m}", file=sys.stderr)

    print(f"\nSVGs: {OUTPUT_DIR}\\*.svg")
    if have_png:
        print(f"PNGs: {OUTPUT_DIR}\\*.png  ({PNG_W}x{PNG_H} px)")


if __name__ == "__main__":
    main()