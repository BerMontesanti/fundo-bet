import os
import requests
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
API_KEY = os.environ.get('ODDS_API_KEY')

# A mesma lista do seu robô principal
LIGAS = [
    ("Futebol - Premier League (ING)", "soccer_epl"),
    ("Futebol - Championship (ING)", "soccer_england_championship"),
    ("Futebol - FA Cup (ING)", "soccer_fa_cup"),
    ("Futebol - La Liga (ESP)", "soccer_spain_la_liga"),
    ("Futebol - Serie A (ITA)", "soccer_italy_serie_a"),
    ("Futebol - Bundesliga (ALE)", "soccer_germany_bundesliga"),
    ("Futebol - Ligue 1 (FRA)", "soccer_france_ligue_one"),
    ("Futebol - Primeira Liga (POR)", "soccer_portugal_primeira_liga"),
    ("Futebol - Eredivisie (HOL)", "soccer_netherlands_eredivisie"),
    ("Futebol - Champions League", "soccer_uefa_champs_league"),
    ("Futebol - Europa League", "soccer_uefa_europa_league"),
    ("Futebol - Conference League", "soccer_uefa_europa_conference_league"),
    ("Futebol - Brasil Série A", "soccer_brazil_campeonato"),
    ("Futebol - Brasil Série B", "soccer_brazil_serie_b"),
    ("Futebol - Libertadores", "soccer_conmebol_libertadores"),
    ("Futebol - Sul-Americana", "soccer_conmebol_sudamericana"),
    ("Futebol - Argentina Primera", "soccer_argentina_primera_division"),
    ("Futebol - Colômbia Primera A", "soccer_colombia_primera_a"),
    ("Futebol - Chile Primera", "soccer_chile_campeonato"),
    ("Futebol - México Liga MX", "soccer_mexico_ligamx"),
    ("Futebol - MLS (EUA)", "soccer_usa_mls"),
    ("Basquete - NBA", "basketball_nba"),
    ("Basquete - WNBA", "basketball_wnba"),
    ("Basquete - NCAA", "basketball_ncaa"),
    ("Basquete - Euroleague", "basketball_euroleague"),
    ("Tênis - ATP Singles", "tennis_atp_match"),
    ("Tênis - WTA Singles", "tennis_wta_match"),
    ("Futebol Americano - NFL", "americanfootball_nfl"),
]

def gerar_agenda_do_dia():
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    hoje_brt = agora_brt.date()
    print(f"📅 A gerar agenda para o dia {hoje_brt}...")
    
    jogos_do_dia = []

    for nome_liga, sport_key in LIGAS:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            # Usamos apenas a região 'eu' para gastar apenas 1 crédito por esporte (é o suficiente para ver quem vai jogar)
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'h2h'})
            
            if res.status_code == 200:
                for ev in res.json():
                    dt_jogo_utc = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ")
                    dt_jogo_brt = dt_jogo_utc - timedelta(hours=3)
                    
                    if dt_jogo_brt.date() == hoje_brt:
                        esporte_limpo = str(nome_liga).split(' - ')[0].strip() if ' - ' in str(nome_liga) else 'Outro'
                        
                        jogos_do_dia.append({
                            "Hora_Sort": dt_jogo_brt,
                            "Horário": dt_jogo_brt.strftime("%H:%M"),
                            "Esporte": esporte_limpo,
                            "Liga": nome_liga,
                            "Jogo": f"{ev['home_team']} x {ev['away_team']}"
                        })
        except Exception as e:
            print(f"❌ Erro ao extrair agenda de {nome_liga}: {e}")

    # Salva os dados processados num novo CSV de agenda
    if jogos_do_dia:
        df = pd.DataFrame(jogos_do_dia)
        df = df.sort_values(by="Hora_Sort").drop(columns=["Hora_Sort"])
        df.to_csv("agenda_hoje.csv", index=False)
        print(f"✅ Agenda salva com sucesso! Encontrados {len(df)} jogos hoje.")
    else:
        df_vazio = pd.DataFrame(columns=["Horário", "Esporte", "Liga", "Jogo"])
        df_vazio.to_csv("agenda_hoje.csv", index=False)
        print("⚠️ Nenhum jogo agendado para hoje nas ligas selecionadas.")

if __name__ == "__main__":
    gerar_agenda_do_dia()
