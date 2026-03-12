import os
import requests
import pandas as pd
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
API_KEY = os.environ.get('ODDS_API_KEY')
SENHA_APP_GMAIL = os.environ.get('GMAIL_PASS')

# 📱 Novas Credenciais do Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

EMAIL_REMETENTE = "bernardo.montesanti@gmail.com"
EMAILS_DESTINO = [
    "bernardo.montesanti@gmail.com",
    "eduasy@hotmail.com"
]

BANCA_RS = 250.0
TAXA_USD = 5.20
BANCA_USDC = BANCA_RS / TAXA_USD
TARGET_EV = 0.07   # 7.0% ROI Mínimo
TARGET_EDGE = 0.03 # 3% Edge Mínimo

# ==========================================
# 🏆 LIGAS E ESPORTES A MONITORAR (Resumido para o exemplo)
# ==========================================
LIGAS = [
    ("Futebol - Premier League (ING)", "soccer_epl"),
    ("Futebol - Champions League", "soccer_uefa_champs_league"),
    ("Futebol - Brasileirão", "soccer_brazil_campeonato"),
    ("Basquete - NBA", "basketball_nba"),
    ("Tênis - ATP Singles", "tennis_atp_match"),
    # Pode manter a sua lista completa de ligas aqui!
]

CASAS_ALVO = [
    'bet365', 'betano', '1xbet', 'betfair_ex_eu', 'betfair_sb_uk', 
    'sport888', 'unibet_eu', 'betsson', 'coolbet', 'matchbook', 
    'pinnacle'
]

# ==========================================
# 🚀 MOTOR DE BUSCA (A mesma lógica que já tínhamos)
# ==========================================
def buscar_oportunidades():
    target_bookmakers = 'pinnacle,' + ','.join(CASAS_ALVO)
    apostas_aprovadas = []
    
    hoje_brt = (datetime.utcnow() - timedelta(hours=3)).date()
    print(f"A iniciar varredura para os jogos do dia {hoje_brt}...")
    
    for nome_liga, sport_key in LIGAS:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu,us,uk', 'markets': 'h2h', 'bookmakers': target_bookmakers})
            if res.status_code == 200:
                for ev in res.json():
                    dt = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    if dt.date() != hoje_brt: continue
                    
                    bookie_pin = next((b for b in ev['bookmakers'] if b['key'] == 'pinnacle'), None)
                    if not bookie_pin: continue
                    
                    outcomes_pin = bookie_pin['markets'][0]['outcomes']
                    sum_inv = sum([1/o['price'] for o in outcomes_pin])
                    probs = {o['name']: (1/o['price']) / sum_inv for o in outcomes_pin}
                    
                    for b in ev['bookmakers']:
                        if b['key'] in CASAS_ALVO:
                            for o in b['markets'][0]['outcomes']:
                                selecao = o['name']
                                odd_soft = o['price']
                                prob_real_pin = probs.get(selecao)
                                
                                if prob_real_pin and prob_real_pin > 0:
                                    odd_justa = 1 / prob_real_pin
                                    roi = (prob_real_pin * odd_soft) - 1
                                    edge = prob_real_pin - (1 / odd_soft)
                                    
                                    if roi >= TARGET_EV and edge >= TARGET_EDGE:
                                        odd_min_ev = (TARGET_EV + 1) / prob_real_pin
                                        odd_min_edge = 1 / (prob_real_pin - TARGET_EDGE) if prob_real_pin > TARGET_EDGE else float('inf')
                                        odd_limite = max(odd_min_ev, odd_min_edge)

                                        b_kelly = odd_soft - 1
                                        f_kelly = (prob_real_pin * b_kelly - (1 - prob_real_pin)) / b_kelly
                                        stake = BANCA_USDC * (f_kelly * 0.25) * TAXA_USD
                                        
                                        apostas_aprovadas.append({
                                            "Data/Hora": dt.strftime("%d/%m %H:%M"),
                                            "Liga": nome_liga,
                                            "Jogo": f"{ev['home_team']} x {ev['away_team']}",
                                            "Casa": b['title'],
                                            "Seleção": selecao,
                                            "Odd Casa": f"{odd_soft:.2f}",
                                            "Odd Justa": f"{odd_justa:.2f}",
                                            "Odd Limite": f"{odd_limite:.2f}",
                                            "Edge": round(edge * 100, 2), # Alterado para número para o sort funcionar melhor
                                            "ROI": round(roi * 100, 2),
                                            "Stake": f"R$ {stake:.2f}"
                                        })
        except Exception as e:
            pass
    return apostas_aprovadas

# ==========================================
# 💾 SALVAR NO BANCO DE DADOS (CSV)
# ==========================================
def salvar_historico_csv(dados_aprovados):
    if not dados_aprovados: return
    arquivo_csv = 'historico_apostas.csv'
    df = pd.DataFrame(dados_aprovados)
    df['Achado_em'] = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")
    existe = os.path.isfile(arquivo_csv)
    df.to_csv(arquivo_csv, mode='a', index=False, header=not existe)
    print(f"✅ {len(df)} apostas guardadas no ficheiro (CSV).")

# ==========================================
# 📱 FUNÇÃO DE ENVIO PARA O TELEGRAM
# ==========================================
def enviar_telegram(dados_aprovados):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Credenciais do Telegram não encontradas nas variáveis de ambiente.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    if not dados_aprovados:
        texto = "💤 *Alerta Quant:* A varredura foi concluída, mas nenhuma oportunidade atendeu aos critérios matemáticos de momento."
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"})
        print("📱 Notificação de zero apostas enviada para o Telegram.")
        return

    df = pd.DataFrame(dados_aprovados).sort_values(by="ROI", ascending=False)
    
    texto_resumo = f"🔥 *Alerta Quant:* Encontradas {len(df)} oportunidades +EV!\n\nA enviar o Top 5 mais lucrativo:"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_resumo, "parse_mode": "Markdown"})

    # Envia apenas as 5 melhores para não criar spam no chat
    for index, row in df.head(5).iterrows():
        msg_aposta = (
            f"⚽ *{row['Jogo']}*\n"
            f"🏆 {row['Liga']} | ⏰ {row['Data/Hora']}\n"
            f"🏠 *Casa:* {row['Casa']}\n"
            f"🎯 *Seleção:* {row['Seleção']}\n"
            f"📊 *Odd Atual:* {row['Odd Casa']} *(Limite: {row['Odd Limite']})*\n"
            f"📈 *Edge:* {row['Edge']}% | *ROI:* {row['ROI']}%\n"
            f"💰 *Stake Recomendada:* {row['Stake']}"
        )
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg_aposta, "parse_mode": "Markdown"})
    
    print("📱 Mensagens enviadas com sucesso para o Telegram!")

# ==========================================
# 📧 FUNÇÃO DE ENVIO DE E-MAIL (Opcional: pode manter ou remover depois)
# ==========================================
# (Coloque aqui a sua função atual enviar_email() se quiser manter ambas as notificações)

# ==========================================
# ⚙️ EXECUÇÃO PRINCIPAL
# ==========================================
if __name__ == "__main__":
    oportunidades = buscar_oportunidades()
    salvar_historico_csv(oportunidades)
    
    # Envia para o Telegram!
    enviar_telegram(oportunidades) 
    
    enviar_email(oportunidades) # Descomente se ainda quiser receber o E-mail com a lista completa
