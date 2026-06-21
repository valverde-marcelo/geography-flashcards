"""
Busca forma de governo e ano de independência/fundação do Wikidata SPARQL
para todos os países em data.json e preenche os campos vazios.

Propriedades Wikidata utilizadas:
  P297  - código ISO 3166-1 alpha-2  (identifica o país)
  P122  - forma básica de governo    (label em pt, fallback en)
  P571  - data de início/fundação    (extrai o ano)
  P31   - instância de               (fallback quando P122 não existe)
"""

import json
import time
import re
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict

DATA_PATH = r"c:\Users\valve\Documents\repositorios\flashcards\data.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
BATCH_SIZE = 50
DELAY_SECONDS = 1.5   # respeitar rate limit do Wikidata

# Tipos P31 genéricos demais para serem usados como forma de governo
_P31_SKIP = {
    "país", "país insular", "país sem costa marítima", "country",
    "estado soberano", "sovereign state",
    "estado unitário", "unitary state",
    "estado arquipelágico", "archipelagic state",
    "estado sucessor", "successor state",
    "micro-estado", "microstate",
    "arquipélago", "archipelago",
    "ilha", "island",
    "grupo insular", "island group",
    "divisão política", "political division",
    "entidade territorial administrativa", "administrative territorial entity",
    "entidade territorial estatística",
    "posição geográfica", "geographic region",
    "continente", "continent",
    "destino turístico", "tourist destination",
    "cidade grande", "big city",
    "cidade fronteiriça",
    "círculo eleitoral",
}

# Palavras-chave que indicam um tipo de governo relevante
_P31_GOV_KEYWORDS = [
    "república", "republic",
    "monarquia", "monarchy",
    "principado", "principality",
    "sultanato", "sultanate",
    "emirado", "emirate",
    "federação", "federation",
    "estado associado", "associated state",
    "commonwealth realm", "reino da comunidade",
    "cidade-estado", "city-state",
]

# Mapeamentos especiais → texto em português
_P31_MAP = {
    "reino da comunidade de nações": "Monarquia constitucional (Reino da Comunidade de Nações)",
    "commonwealth realm": "Monarquia constitucional (Reino da Comunidade de Nações)",
    "república islâmica": "República islâmica",
    "república parlamentarista": "República parlamentarista",
    "república presidencialista": "República presidencialista",
    "monarquia constitucional": "Monarquia constitucional",
    "estado associado": "Estado associado",
    "cidade-estado": "Cidade-Estado",
    "principado": "Principado",
    "sultanato": "Sultanato",
    "emirado": "Emirado",
}


def _is_gov_type(label: str) -> bool:
    """Retorna True se o label P31 descreve um tipo de governo relevante."""
    lo = label.lower()
    return any(kw in lo for kw in _P31_GOV_KEYWORDS) and lo not in _P31_SKIP


def _normalize_gov(label: str) -> str:
    """Aplica mapeamentos especiais, capitaliza a primeira letra."""
    lo = label.lower().strip()
    for key, val in _P31_MAP.items():
        if key in lo:
            return val
    return label.strip().capitalize()


def sparql_query(query: str) -> dict:
    """Executa uma query SPARQL no Wikidata e retorna o JSON de resultados."""
    params = urllib.parse.urlencode({"query": query, "format": "json"})
    url = f"{SPARQL_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "flashcards-enrichment/1.0 (educational project)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── P122 queries (primary) ────────────────────────────────────────────────────

def build_p122_query(iso_codes: list[str]) -> str:
    """Query P122 (forma de governo) + P571 (ano de fundação)."""
    values = " ".join(f'"{code.upper()}"' for code in iso_codes)
    return f"""
SELECT ?iso ?govLabel ?inception WHERE {{
  VALUES ?iso {{ {values} }}
  ?country wdt:P297 ?iso .
  OPTIONAL {{
    ?country wdt:P122 ?gov .
    ?gov rdfs:label ?govLabel .
    FILTER(LANG(?govLabel) = "pt" || LANG(?govLabel) = "en")
  }}
  OPTIONAL {{ ?country wdt:P571 ?inception . }}
}}
ORDER BY ?iso LANG(?govLabel)
"""


def fetch_p122_batch(iso_codes: list[str]) -> dict[str, dict]:
    query = build_p122_query(iso_codes)
    try:
        data = sparql_query(query)
    except urllib.error.HTTPError as e:
        print(f"  [ERRO HTTP {e.code}] lote {iso_codes[:3]}... — pulando")
        return {}
    except Exception as e:
        print(f"  [ERRO] {e} — pulando lote {iso_codes[:3]}...")
        return {}

    results: dict[str, dict] = {}

    for row in data.get("results", {}).get("bindings", []):
        iso = row["iso"]["value"].lower()
        if iso not in results:
            results[iso] = {"governo": "", "ano": ""}

        if "govLabel" in row:
            label_val = row["govLabel"]["value"]
            lang = row["govLabel"].get("xml:lang", "")
            # Prefere pt; só sobrescreve se ainda vazio ou se pt supera en
            if label_val and not results[iso]["governo"]:
                results[iso]["governo"] = label_val
            elif label_val and lang == "pt":
                results[iso]["governo"] = label_val

        if "inception" in row:
            raw = row["inception"]["value"]
            year_part = raw.lstrip("+").split("T")[0]
            year = year_part.split("-")[0]
            if year.lstrip("-").isdigit():
                if not results[iso]["ano"] or year < results[iso]["ano"]:
                    results[iso]["ano"] = year

    return results


# ── P31 queries (fallback) ────────────────────────────────────────────────────

def build_p31_query(iso_codes: list[str]) -> str:
    """Query P31 (instância de) para fallback de forma de governo."""
    values = " ".join(f'"{code.upper()}"' for code in iso_codes)
    return f"""
SELECT ?iso ?typeLabel WHERE {{
  VALUES ?iso {{ {values} }}
  ?country wdt:P297 ?iso .
  ?country wdt:P31 ?type .
  ?type rdfs:label ?typeLabel .
  FILTER(LANG(?typeLabel) = "pt" || LANG(?typeLabel) = "en")
}}
"""


def fetch_p31_batch(iso_codes: list[str]) -> dict[str, str]:
    """Retorna { iso_lower: governo_str } para países com tipos P31 relevantes."""
    query = build_p31_query(iso_codes)
    try:
        data = sparql_query(query)
    except urllib.error.HTTPError as e:
        print(f"  [P31 ERRO HTTP {e.code}] lote {iso_codes[:3]}... — pulando")
        return {}
    except Exception as e:
        print(f"  [P31 ERRO] {e} — pulando lote {iso_codes[:3]}...")
        return {}

    # Collect all types per country: pt preferred over en
    country_types: dict[str, dict[str, str]] = defaultdict(dict)  # iso -> {label: lang}
    for row in data.get("results", {}).get("bindings", []):
        iso = row["iso"]["value"].lower()
        label = row["typeLabel"]["value"]
        lang = row["typeLabel"].get("xml:lang", "")
        country_types[iso][label] = lang

    result: dict[str, str] = {}
    for iso, type_map in country_types.items():
        # Separate pt and en types; filter to gov-relevant ones
        pt_gov = [l for l, lg in type_map.items() if lg == "pt" and _is_gov_type(l)]
        en_gov = [l for l, lg in type_map.items() if lg == "en" and _is_gov_type(l)]

        candidates = pt_gov if pt_gov else en_gov
        if not candidates:
            continue

        # Prioritize more specific types (longer label = more specific)
        candidates.sort(key=lambda x: len(x), reverse=True)
        result[iso] = _normalize_gov(candidates[0])

    return result


# ── Wikipedia summary pass (final fallback for sovereign nations) ─────────────

# English Wikipedia titles for sovereign nations that Wikidata P122/P31 can't resolve
_ISO_TO_EN_WIKI: dict[str, str] = {
    "cr": "Costa Rica",
    "dj": "Djibouti",
    "dm": "Dominica",
    "do": "Dominican Republic",
    "er": "Eritrea",
    "fj": "Fiji",
    "gw": "Guinea-Bissau",
    "gq": "Equatorial Guinea",
    "ht": "Haiti",
    "ke": "Kenya",
    "ki": "Kiribati",
    "mv": "Maldives",
    "mh": "Marshall Islands",
    "ml": "Mali",
    "py": "Paraguay",
    "td": "Chad",
    "to": "Tonga",
    "vu": "Vanuatu",
    "ws": "Samoa",
    # territories that have an identifiable government
    "fo": "Faroe Islands",
    "gg": "Guernsey",
    "im": "Isle of Man",
    "gi": "Gibraltar",
    "gl": "Greenland",
    "hk": "Hong Kong",
    "mo": "Macau",
    "ps": "State of Palestine",
    "ck": "Cook Islands",
    "nu": "Niue",
}

# Map English official-name prefix → Portuguese government type
_EN_GOV_TO_PT: list[tuple[str, str]] = [
    ("islamic republic",           "República islâmica"),
    ("democratic republic",        "República democrática"),
    ("federal republic",           "República federal"),
    ("parliamentary republic",     "República parlamentarista"),
    ("constitutional republic",    "República constitucional"),
    ("presidential republic",      "República presidencialista"),
    ("republic",                   "República"),
    ("kingdom",                    "Monarquia constitucional"),
    ("principality",               "Principado"),
    ("sultanate",                  "Sultanato"),
    ("emirate",                    "Emirado"),
    ("federation",                 "Federação"),
    ("commonwealth",               "Comunidade de Nações"),
    ("duchy",                      "Ducado"),
    ("empire",                     "Império"),
    ("state",                      "Estado"),
]

_WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
# Pattern: "officially the [X] of [Country]"
_OFFICIAL_RE = re.compile(r"officially (?:the |known as )([A-Za-z\s']+?) of ", re.IGNORECASE)


def _wikipedia_gov_type(iso: str) -> str:
    """Fetch English Wikipedia lead and extract government type. Returns '' on failure."""
    title = _ISO_TO_EN_WIKI.get(iso)
    if not title:
        return ""
    url = _WIKI_SUMMARY_URL.format(urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={"User-Agent": "flashcards-enrichment/1.0 (educational project)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        extract = data.get("extract", "")
        m = _OFFICIAL_RE.search(extract)
        if not m:
            return ""
        official_type = m.group(1).strip().lower()
        for en_key, pt_val in _EN_GOV_TO_PT:
            if en_key in official_type:
                return pt_val
    except Exception:
        pass
    return ""


def fetch_wikipedia_gov_pass(iso_codes: list[str]) -> dict[str, str]:
    """Returns { iso_lower: gov_str } for countries resolved via Wikipedia."""
    result: dict[str, str] = {}
    for iso in iso_codes:
        gov = _wikipedia_gov_type(iso.lower())
        if gov:
            result[iso.lower()] = gov
        time.sleep(0.3)   # be polite to Wikipedia
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        countries = json.load(f)

    total = len(countries)
    print(f"Países carregados: {total}")

    need_gov = [c for c in countries if not c.get("forma_de_governo")]
    need_year = [c for c in countries if not c.get("ano_independencia_fundacao")]
    need_codes = list({
        c["codigo_iso"]
        for c in countries
        if c.get("codigo_iso") and (
            not c.get("forma_de_governo") or not c.get("ano_independencia_fundacao")
        )
    })

    print(f"  forma_de_governo vazio: {len(need_gov)}")
    print(f"  ano_independencia_fundacao vazio: {len(need_year)}")
    print(f"  Códigos ISO a consultar: {len(need_codes)}")

    if not need_codes:
        print("Nenhum campo vazio encontrado. Nada a fazer.")
        return

    # ── Passe 1: P122 + P571 ─────────────────────────────────────────────────
    print("\n[Passe 1] Consultando P122 (forma de governo) + P571 (ano)...")
    wikidata: dict[str, dict] = {}
    batches = [need_codes[i:i + BATCH_SIZE] for i in range(0, len(need_codes), BATCH_SIZE)]
    for idx, batch in enumerate(batches, 1):
        print(f"  Lote {idx}/{len(batches)} ({len(batch)} países)...")
        wikidata.update(fetch_p122_batch(batch))
        if idx < len(batches):
            time.sleep(DELAY_SECONDS)

    filled_gov = filled_year = 0
    for country in countries:
        iso = country.get("codigo_iso", "").lower()
        info = wikidata.get(iso, {})
        if not country.get("forma_de_governo") and info.get("governo"):
            country["forma_de_governo"] = info["governo"]
            filled_gov += 1
        if not country.get("ano_independencia_fundacao") and info.get("ano"):
            country["ano_independencia_fundacao"] = info["ano"]
            filled_year += 1

    print(f"  → governo: +{filled_gov} | ano: +{filled_year}")

    # ── Passe 2: P31 fallback para governo ainda vazio ────────────────────────
    still_missing_gov = [
        c["codigo_iso"] for c in countries
        if c.get("codigo_iso") and not c.get("forma_de_governo")
    ]
    if still_missing_gov:
        print(f"\n[Passe 2] Consultando P31 (instância de) para {len(still_missing_gov)} países sem governo...")
        p31_data: dict[str, str] = {}
        batches2 = [still_missing_gov[i:i + BATCH_SIZE] for i in range(0, len(still_missing_gov), BATCH_SIZE)]
        for idx, batch in enumerate(batches2, 1):
            print(f"  Lote {idx}/{len(batches2)} ({len(batch)} países)...")
            p31_data.update(fetch_p31_batch(batch))
            if idx < len(batches2):
                time.sleep(DELAY_SECONDS)

        filled_gov_p31 = 0
        for country in countries:
            iso = country.get("codigo_iso", "").lower()
            if not country.get("forma_de_governo") and iso in p31_data:
                country["forma_de_governo"] = p31_data[iso]
                filled_gov_p31 += 1
        print(f"  → governo (P31 fallback): +{filled_gov_p31}")
        filled_gov += filled_gov_p31

    # ── Passe 3: Wikipedia summary para soberanos ainda sem governo ───────────
    still_missing_gov2 = [
        c["codigo_iso"] for c in countries
        if c.get("codigo_iso") and not c.get("forma_de_governo")
           and c["codigo_iso"].lower() in _ISO_TO_EN_WIKI
    ]
    if still_missing_gov2:
        print(f"\n[Passe 3] Wikipedia summary para {len(still_missing_gov2)} países...")
        wiki_gov = fetch_wikipedia_gov_pass(still_missing_gov2)
        filled_gov_wiki = 0
        for country in countries:
            iso = country.get("codigo_iso", "").lower()
            if not country.get("forma_de_governo") and iso in wiki_gov:
                country["forma_de_governo"] = wiki_gov[iso]
                filled_gov_wiki += 1
        print(f"  → governo (Wikipedia fallback): +{filled_gov_wiki}")
        filled_gov += filled_gov_wiki

    # ── Salvar ────────────────────────────────────────────────────────────────
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(countries, f, ensure_ascii=False, indent=4)

    print("\n=== Resultado final ===")
    print(f"  forma_de_governo preenchidos : {filled_gov}")
    print(f"  ano preenchidos              : {filled_year}")
    still_gov = sum(1 for c in countries if not c.get("forma_de_governo"))
    still_year = sum(1 for c in countries if not c.get("ano_independencia_fundacao"))
    print(f"  forma_de_governo ainda vazios: {still_gov}")
    print(f"  ano ainda vazios             : {still_year}")
    if still_gov:
        print("\n  Países sem forma_de_governo:")
        for c in countries:
            if not c.get("forma_de_governo"):
                print(f"    {c['codigo_iso']:4} {c['nome']}")
    print(f"\ndata.json atualizado em: {DATA_PATH}")


if __name__ == "__main__":
    main()
