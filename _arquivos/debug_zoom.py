#!/usr/bin/env python3
"""
debug_zoom.py - Testa centralização com diferentes zoom factors
"""

import os
import sys
import re
import json
import requests
from lxml import etree

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "images", "mapas")

SCRIPT_JS_URL = "https://atlasescolar.ibge.gov.br/templates/atlas_2022/js/script.js"
SVG_URL       = "https://atlasescolar.ibge.gov.br/templates/atlas_2022/paises_mundo.svg"

PNG_W = 1200
PNG_H = 750

def fetch_paises() -> list:
    print("Baixando script.js...")
    resp = requests.get(SCRIPT_JS_URL, timeout=30)
    resp.encoding = "utf-8"
    m = re.search(r"const paises\s*=\s*(\[.*?\]);", resp.text, re.DOTALL)
    if not m:
        raise RuntimeError("Array 'paises' não encontrado")
    return json.loads(m.group(1))

def fetch_world_svg() -> tuple:
    print("Baixando SVG...")
    resp = requests.get(SVG_URL, timeout=60)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)
    viewbox = root.get("viewBox") or root.get("viewbox")
    return root, viewbox

# Teste com um país
paises = fetch_paises()
svg_root, viewbox = fetch_world_svg()

# Procura Brasil (sigla: BR)
brasil = next((p for p in paises if p["sigla"] == "BR"), None)
if not brasil:
    print("Brasil não encontrado!")
    sys.exit(1)

print(f"\n{'='*70}")
print(f"PAÍS: {brasil['nome']} ({brasil['sigla']})")
print(f"{'='*70}")

matrix_str = brasil.get("matrix", "").strip()
print(f"\nMatrix original: {matrix_str}")

# Parse
parts = [float(v.strip()) for v in matrix_str.split(",")]
a, b, c, d, tx, ty = parts

print(f"\nComponentes:")
print(f"  a  (scale X)     = {a:.10f}")
print(f"  b  (skew Y)      = {b}")
print(f"  c  (skew X)      = {c}")
print(f"  d  (scale Y)     = {d:.10f}")
print(f"  tx (translate X) = {tx:.10f}")
print(f"  ty (translate Y) = {ty:.10f}")

# Calcula ponto central
print(f"\nCálculo do ponto central no mapa original (zoom=1.0):")
print(f"  Centro da tela PNG: ({PNG_W/2}, {PNG_H/2})")

# Inversa da transformação: descobre que ponto do mapa está no centro
# x_screen = a*x_map + c*y_map + tx
# (PNG_W/2, PNG_H/2) = (a*x_map + c*y_map + tx, d*y_map + b*x_map + ty)
# Assumindo c=0, b=0:
# x_map = (PNG_W/2 - tx) / a
# y_map = (PNG_H/2 - ty) / d

x_map = (PNG_W/2 - tx) / a
y_map = (PNG_H/2 - ty) / d

print(f"  Ponto do mapa no centro (assumindo c=0, b=0):")
print(f"    x_map = ({PNG_W/2} - {tx}) / {a:.10f} = {x_map:.6f}")
print(f"    y_map = ({PNG_H/2} - {ty}) / {d:.10f} = {y_map:.6f}")

# Testa diferentes zoom factors
print(f"\n{'='*70}")
print(f"TESTE COM DIFERENTES ZOOM FACTORS")
print(f"{'='*70}\n")

for zoom in [1.0, 0.8, 0.6, 0.5, 0.4]:
    new_a = a * zoom
    new_d = d * zoom
    new_tx = PNG_W / 2 - (PNG_W / 2 - tx) * zoom
    new_ty = PNG_H / 2 - (PNG_H / 2 - ty) * zoom
    
    # Verifica se o mesmo ponto volta ao centro
    check_x = new_a * x_map + new_tx
    check_y = new_d * y_map + new_ty
    
    print(f"zoom_factor = {zoom}")
    print(f"  Nova matrix: {new_a:.10f}, {b}, {c}, {new_d:.10f}, {new_tx:.6f}, {new_ty:.6f}")
    print(f"  Verificação (deve estar no centro ~{PNG_W/2}, {PNG_H/2}):")
    print(f"    x_screen = {new_a:.10f} * {x_map:.6f} + {new_tx:.6f} = {check_x:.2f}")
    print(f"    y_screen = {new_d:.10f} * {y_map:.6f} + {new_ty:.6f} = {check_y:.2f}")
    print()
