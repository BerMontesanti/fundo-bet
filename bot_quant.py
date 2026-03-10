import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==========================================
# ⚙️ CONFIGURAÇÕES DO FUNDO & API
# ==========================================
API_KEY = 'f926d86f5279262d9eb0afb7f304520f'

# Parâmetros de Gestão
BANCA_RS = 300.0
TAXA_USD = 5.20
BANCA_USDC = BANCA_RS / TAXA_USD
TARGET_EV = 0.05    # 5.0% ROI Mínimo
TARGET_EDGE = 0.025 # 2.5% Edge Mínimo

# Ligas a Monitorar
LIGAS = [
    ("Futebol - Premier League", "soccer_epl"),
    ("Futebol - Brasil Série A", "soccer_brazil_campeonato"),
    ("Futebol - Brasil Série B", "soccer_brazil_serie_b"),
    ("Futebol - Libertadores", "soccer_conmebol_libertadores"),
    ("Tênis - ATP Singles", "tennis_atp_match"),
    ("Basquete - NBA", "basketball_nba")
]

# Casas de Apostas Alvo
CASAS_ALVO = ['bet365', 'betano', '1xbet', 'bovada']

# Configurações de Email (Remetente e Destinatários)
EMAIL_REMETENTE = "bernardo.montesanti@gmail.com" 
SENHA_APP_GMAIL = "qvwkdpbyvlgmihfp"

EMAILS_DESTINO = [
    "bernardo.montesanti@gmail.com",
    "eduasy@hotmail.com"
]

# ==========================================
# 🚀 MOTOR DE BUSCA (API)
# ==========================================
def buscar_oportunidades():
    target_bookmakers = 'pinnacle,' + ','.join(CASAS_ALVO)
    apostas_aprovadas = []
    
    print("Iniciando varredura na API...")
    for nome_liga, sport_key in LIGAS:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu,us,uk', 'markets': 'h2h', 'bookmakers': target_bookmakers})
            if res.status_code == 200:
                for ev in res.json():
                    dt = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    
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
                                            "Edge": f"{edge*100:.2f}%",
                                            "ROI": f"{roi*100:.2f}%",
                                            "Stake": f"R$ {stake:.2f}"
                                        })
        except Exception as e:
            print(f"Erro ao buscar {nome_liga}: {e}")
            
    return apostas_aprovadas

# ==========================================
# 📧 FUNÇÃO DE ENVIO DE EMAIL
# ==========================================
def enviar_email(dados_aprovados):
    df = pd.DataFrame(dados_aprovados)
    df = df.drop_duplicates().sort_values(by="ROI", ascending=False)
    
    tabela_html = df.to_html(index=False, justify='center', border=1, classes='table table-striped')
    
    corpo_email = f"""
    <html>
      <head>
        <style>
          table {{ border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }}
          th, td {{ padding: 8px; text-align: center; border-bottom: 1px solid #ddd; }}
          th {{ background-color: #4CAF50; color: white; }}
        </style>
      </head>
      <body>
        <h2>🤖 Alerta Quant: {len(df)} Oportunidades Encontradas!</h2>
        <p>Abaixo estão as apostas de Valor Esperado Positivo (+EV) identificadas agora:</p>
        <br>
        {tabela_html}
        <br><br>
        <p><i>Varredura automática finalizada em {datetime.now().strftime("%d/%m/%Y %H:%M")}</i></p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔥 Alerta +EV: {len(df)} Oportunidades Encontradas"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = ", ".join(EMAILS_DESTINO)
    msg.attach(MIMEText(corpo_email, "html"))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
        server.sendmail(EMAIL_REMETENTE, EMAILS_DESTINO, msg.as_string())
        server.quit()
        print("Emails enviados com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

if __name__ == "__main__":
    print(f"Iniciando Bot Quant às {datetime.now().strftime('%H:%M:%S')}...")
    oportunidades = buscar_oportunidades()
    
    if oportunidades:
        print(f"{len(oportunidades)} apostas de valor encontradas. Preparando emails...")
        enviar_email(oportunidades)
    else:
        print("Nenhuma oportunidade encontrada. Nenhum email será enviado.")
