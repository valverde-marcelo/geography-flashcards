import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE, "data.json")
IBGE_PATH = os.path.join(BASE, "ibge-paises.json")

with open(DATA_PATH, encoding="utf-8") as f:
    data = json.load(f)

with open(IBGE_PATH, encoding="utf-8") as f:
    ibge_list = json.load(f)

# Build lookup: lowercase ISO-2 code -> ibge entry
ibge_by_iso2 = {}
for entry in ibge_list:
    iso2 = entry.get("id", {}).get("ISO-3166-1-ALPHA-2")
    if iso2:
        ibge_by_iso2[iso2.lower()] = entry


def get_localizacao(ibge_entry):
    loc = ibge_entry.get("localizacao", {})
    if not loc:
        return ""
    result = {}
    regiao = loc.get("regiao")
    if regiao and regiao.get("nome"):
        result["regiao"] = regiao["nome"]
    sub = loc.get("sub-regiao")
    if sub and sub.get("nome"):
        result["sub-regiao"] = sub["nome"]
    inter = loc.get("regiao-intermediaria")
    if inter and inter.get("nome"):
        result["regiao-intermediaria"] = inter["nome"]
    return result if result else ""


def get_idiomas(ibge_entry):
    linguas = ibge_entry.get("linguas", [])
    nomes = [l["nome"] for l in linguas if l.get("nome")]
    return ", ".join(nomes)


def get_moedas(ibge_entry):
    moedas = ibge_entry.get("unidades-monetarias", [])
    nomes = [m["nome"] for m in moedas if m.get("nome")]
    return ", ".join(nomes)


def get_capital(ibge_entry):
    governo = ibge_entry.get("governo", {})
    if not governo:
        return None
    capital = governo.get("capital", {})
    if not capital:
        return None
    return capital.get("nome")


updated = 0
no_match = 0

for country in data:
    iso = country.get("codigo_iso", "").lower()
    ibge = ibge_by_iso2.get(iso)

    if ibge is None:
        no_match += 1
        continue

    # nome (abreviado only)
    nome_abrev = ibge.get("nome", {}).get("abreviado")
    if nome_abrev:
        country["nome"] = nome_abrev

    # capital
    capital = get_capital(ibge)
    if capital:
        country["capital"] = capital

    # idioma
    idiomas = get_idiomas(ibge)
    if idiomas:
        country["idioma"] = idiomas

    # moeda
    moedas = get_moedas(ibge)
    if moedas:
        country["moeda"] = moedas

    # area (number string only)
    area_total = ibge.get("area", {}).get("total")
    if area_total:
        country["area"] = area_total

    # localizacao
    loc = get_localizacao(ibge)
    if loc:
        country["localizacao"] = loc

    # historico
    historico = ibge.get("historico")
    if historico:
        country["historico"] = historico

    updated += 1

with open(DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"Done. Updated: {updated} | No IBGE match: {no_match}")
