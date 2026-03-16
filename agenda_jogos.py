import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
API_KEY = os.environ.get('ODDS_API_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def carregar_portfolio():
    try:
        with open('ligas_config.json', 'r') as f:
            return json.load(f)
    except:
        return {"disponiveis": {}, "selecionadas": []}

def enviar_telegram(df_agenda, hoje_str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    if df_agenda.empty:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": f"📅 <b>Agenda QuantBet ({hoje_str}):</b>\n\n💤 Não há jogos programados para as suas ligas.", "parse_mode": "HTML"})
        return

    texto_atual = f"📅 <b>Agenda QuantBet ({hoje_str}):</b>\n\n"
    for liga in sorted(df_agenda['Liga'].unique()):
        bloco_liga = f"🏆 <b>{liga}</b>\n"
        for _, row in df_agenda[df_agenda['Liga'] == liga].iterrows():
            bloco_liga += f"⏰ {row['Horário']} - {row['Jogo']}\n"
        bloco_liga += "\n"
        
        if len(texto_atual) + len(bloco_liga) > 3800:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_atual, "parse_mode": "HTML"})
            texto_atual = bloco_liga 
        else: texto_atual += bloco_liga
            
    if texto_atual.strip(): requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_atual, "parse_mode": "HTML"})

def gerar_agenda_do_dia():
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    hoje_brt = agora_brt.date()
    hoje_str = hoje_brt.strftime("%d/%m/%Y")
    
    config_ligas = carregar_portfolio()
    chaves_selecionadas = config_ligas.get("selecionadas", [])
    nomes_disponiveis = config_ligas.get("disponiveis", {})
    
    if not chaves_selecionadas:
        print("⚠️ O seu portfólio está vazio. Vá ao Streamlit adicionar ligas.")
        return

    print(f"📅 A gerar agenda para {len(chaves_selecionadas)} ligas do portfólio...")
    jogos_do_dia = []

    for sport_key in chaves_selecionadas:
        nome_liga = nomes_disponiveis.get(sport_key, sport_key)
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'h2h'})
            if res.status_code == 200:
                for ev in res.json():
                    dt = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    if dt.date() == hoje_brt:
                        esporte_limpo = str(nome_liga).split(' - ')[0].strip() if ' - ' in str(nome_liga) else 'Outro'
                        jogos_do_dia.append({
                            "Hora_Sort": dt, "Horário": dt.strftime("%H:%M"), "Esporte": esporte_limpo, "Liga": nome_liga, "Jogo": f"{ev['home_team']} x {ev['away_team']}"
                        })
        except Exception as e:
            print(f"❌ Erro ao extrair agenda de {nome_liga}: {e}")

    if jogos_do_dia:
        df = pd.DataFrame(jogos_do_dia).sort_values(by="Hora_Sort").drop(columns=["Hora_Sort"])
        df.to_csv("agenda_hoje.csv", index=False)
        print(f"✅ Agenda salva! {len(df)} jogos hoje.")
        enviar_telegram(df, hoje_str)
    else:
        pd.DataFrame(columns=["Horário", "Esporte", "Liga", "Jogo"]).to_csv("agenda_hoje.csv", index=False)
        print("⚠️ Nenhum jogo agendado para hoje.")
        enviar_telegram(pd.DataFrame(), hoje_str)

if __name__ == "__main__":
    gerar_agenda_do_dia()
