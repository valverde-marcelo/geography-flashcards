import requests
import json

def fetch_data_with_translations():
    # A API REST Countries (mledoze dataset) geralmente contém traduções.
    # Vamos usar o dataset do mledoze novamente, pois ele tem o campo 'translations'.
    url = "https://raw.githubusercontent.com/mledoze/countries/master/dist/countries.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao acessar dataset: {e}")
        return None

def translate_and_process(data):
    translated_countries = []
    for country in data:
        # Extrair traduções para PT (Português)
        translations = country.get('translations', {})
        pt_data = translations.get('por', {}) # 'por' é o código para português no dataset
        
        name_common_pt = pt_data.get('common', country.get('name', {}).get('common', 'N/A'))
        name_official_pt = pt_data.get('official', country.get('name', {}).get('official', 'N/A'))
        
        # Capitais, idiomas e moedas geralmente não vêm traduzidos no dataset básico.
        # No entanto, nomes de países e nomes oficiais costumam ser o principal.
        # Para capitais, vamos manter o original ou tentar uma tradução simples se for o caso.
        capitals = country.get('capital', [])
        capital = capitals[0] if isinstance(capitals, list) and capitals else (capitals if isinstance(capitals, str) else 'N/A')
        
        languages_dict = country.get('languages', {})
        languages_list = list(languages_dict.values()) if isinstance(languages_dict, dict) else []
        languages_str = ", ".join(languages_list) if languages_list else 'N/A'
        
        currencies_dict = country.get('currencies', {})
        currency_list = []
        if isinstance(currencies_dict, dict):
            for code, info in currencies_dict.items():
                if isinstance(info, dict):
                    c_name = info.get('name', 'N/A')
                    c_symbol = info.get('symbol', '')
                    currency_list.append(f"{c_name} ({c_symbol})" if c_symbol else c_name)
                else:
                    currency_list.append(code)
        currency_str = ", ".join(currency_list) if currency_list else 'N/A'
        
        iso_code = country.get('cca2', '').lower()
        
        translated_countries.append({
            "nome": name_common_pt,
            "nome_oficial": name_official_pt,
            "capital": capital,
            "idioma": languages_str,
            "moeda": currency_str,
            "forma_de_governo": "Pesquisa adicional necessária",
            "ano_independencia_fundacao": "Pesquisa adicional necessária",
            "codigo_iso": iso_code,
            "arquivo_bandeira": f"{iso_code}.png"
        })
    return translated_countries

if __name__ == "__main__":
    print("Baixando dataset com traduções...")
    raw_data = fetch_data_with_translations()
    if raw_data:
        translated = translate_and_process(raw_data)
        with open("/home/ubuntu/flags_project/countries_data_ptbr.json", "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=4)
        print(f"Processados {len(translated)} países com traduções para PT-BR.")
