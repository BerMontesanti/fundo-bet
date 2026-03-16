import os
import requests
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
API_KEY = os.environ.get('ODDS_API_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

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

def enviar_telegram(df_agenda, hoje_str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Credenciais do Telegram não encontradas. Saltando envio.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    if df_agenda.empty:
        texto = f"📅 <b>Agenda QuantBet ({hoje_str}):</b>\n\n💤 Não há jogos programados para hoje nas nossas ligas."
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"})
        return

    # Constrói a mensagem agrupada por Ligas usando HTML (mais seguro contra caracteres especiais)
    cabecalho = f"📅 <b>Agenda QuantBet ({hoje_str}):</b>\n\n"
    texto_atual = cabecalho
    
    ligas_hoje = sorted(df_agenda['Liga'].unique())

    for liga in ligas_hoje:
        bloco_liga = f"🏆 <b>{liga}</b>\n"
        df_liga = df_agenda[df_agenda['Liga'] == liga]
        for _, row in df_liga.iterrows():
            bloco_liga += f"⏰ {row['Horário']} - {row['Jogo']}\n"
        bloco_liga += "\n"
        
        # Se a adição desta liga ultrapassar os 3800 caracteres, enviamos o que temos e recomeçamos!
        if len(texto_atual) + len(bloco_liga) > 3800:
            resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_atual, "parse_mode": "HTML"})
            if resp.status_code != 200: print(f"❌ Erro do Telegram: {resp.text}")
            texto_atual = bloco_liga # A nova mensagem começa com a liga atual
        else:
            texto_atual += bloco_liga
            
    # Envia o texto que sobrou no final
    if texto_atual.strip():
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_atual, "parse_mode": "HTML"})
        if resp.status_code != 200: print(f"❌ Erro do Telegram: {resp.text}")
    
    print("📲 Processo de envio para o Telegram concluído!")

def gerar_agenda_do_dia():
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    hoje_brt = agora_brt.date()
    hoje_str = hoje_brt.strftime("%d/%m/%Y")
    print(f"📅 A gerar agenda para o dia {hoje_brt} (The Odds API)...")
    
    jogos_do_dia = []

    for nome_liga, sport_key in LIGAS:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
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

    if jogos_do_dia:
        df = pd.DataFrame(jogos_do_dia)
        df = df.sort_values(by="Hora_Sort").drop(columns=["Hora_Sort"])
        df.to_csv("agenda_hoje.csv", index=False)
        print(f"✅ Agenda salva no CSV! Encontrados {len(df)} jogos hoje.")
        enviar_telegram(df, hoje_str)
    else:
        df_vazio = pd.DataFrame(columns=["Horário", "Esporte", "Liga", "Jogo"])
        df_vazio.to_csv("agenda_hoje.csv", index=False)
        print("⚠️ Nenhum jogo agendado para hoje nas ligas selecionadas.")
        enviar_telegram(df_vazio, hoje_str)

if __name__ == "__main__":
    gerar_agenda_do_dia()
