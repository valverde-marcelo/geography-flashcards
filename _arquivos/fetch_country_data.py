import requests
import json

def process_data(data):
    processed_countries = []
    for country in data:
        # O dataset do mledoze tem uma estrutura ligeiramente diferente
        name_common = country.get('name', {}).get('common', 'N/A')
        name_official = country.get('name', {}).get('official', 'N/A')
        
        capitals = country.get('capital', [])
        if isinstance(capitals, str):
            capital = capitals
        else:
            capital = capitals[0] if capitals else 'N/A'
            
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
        
        processed_countries.append({
            "nome": name_common,
            "nome_oficial": name_official,
            "capital": capital,
            "idioma": languages_str,
            "moeda": currency_str,
            "forma_de_governo": "N/A", # Será preenchido na próxima fase se possível
            "ano_independencia_fundacao": "N/A",
            "codigo_iso": iso_code,
            "arquivo_bandeira": f"{iso_code}.png"
        })
    return processed_countries

if __name__ == "__main__":
    print("Baixando dataset do GitHub...")
    url = "https://raw.githubusercontent.com/mledoze/countries/master/dist/countries.json"
    response = requests.get(url)
    if response.status_code == 200:
        raw_data = response.json()
        processed = process_data(raw_data)
        with open("/home/ubuntu/flags_project/countries_data_temp.json", "w", encoding="utf-8") as f:
            json.dump(processed, f, ensure_ascii=False, indent=4)
        print(f"Processados {len(processed)} países.")
    else:
        print("Falha ao baixar dataset.")
