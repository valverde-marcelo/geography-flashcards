import json

def enrich():
    with open("/home/ubuntu/flags_project/countries_data_temp.json", "r", encoding="utf-8") as f:
        countries = json.load(f)

    for country in countries:
        # A API REST Countries e o dataset do mledoze não fornecem 'forma de governo' e 'ano de independência/fundação'
        # de forma estruturada e consistente para todos os países.
        # Para uma coleta precisa desses dados, seria necessário consultar fontes específicas
        # como a Wikipedia, CIA World Factbook, ou bases de dados acadêmicas, o que pode envolver
        # processamento de texto não estruturado ou pesquisa manual.
        # Por enquanto, vamos deixar um placeholder indicando a necessidade de pesquisa adicional.
        country["forma_de_governo"] = "Pesquisa adicional necessária"
        country["ano_independencia_fundacao"] = "Pesquisa adicional necessária"
            
    with open("/home/ubuntu/flags_project/countries_data_final.json", "w", encoding="utf-8") as f:
        json.dump(countries, f, ensure_ascii=False, indent=4)
    print("Dados enriquecidos e salvos.")

if __name__ == "__main__":
    enrich()
