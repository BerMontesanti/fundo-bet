import requests
from datetime import datetime, timedelta
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==========================================
# ⚙️ CONFIGURAÇÕES DO FUNDO
# ==========================================
API_KEY = 'f926d86f5279262d9eb0afb7f304520f'

BANCA_RS = 410.0
TAXA_USD = 5.00
BANCA_USDC = BANCA_RS / TAXA_USD
TARGET_EV = 0.05    # 5.0% ROI Mínimo
TARGET_EDGE = 0.025 # 2.5% Edge Mínimo

# 1. As 8 Ligas Pré-definidas
LIGAS = [
    ("Basquete - NBA", "basketball_nba"),
    ("Tênis - ATP Singles", "tennis_atp_match"),
    ("E-Sports - CS:GO", "esports_csgo_match_winner"),
    ("MMA - UFC", "mma_mixed_martial_arts"),
    ("Futebol - Premier League", "soccer_epl"),
    ("Futebol - La Liga", "soccer_spain_la_liga"),
    ("Futebol - Brasil Série A", "soccer_brazil_campeonato"),
    ("Futebol - Brasil Série B", "soccer_brazil_serie_b")
]

# 2. Apenas Betano e Bet365
CASAS_ALVO = ['betano', 'bet365']

EMAIL_REMETENTE = "bernardo.montesanti@gmail.com" 
SENHA_APP_GMAIL = "qvwkdpbyvlgmihfp"
EMAILS_DESTINO = [
    "bernardo.montesanti@gmail.com",
    "eduasy@hotmail.com"
]

# ==========================================
# 🚀 MOTOR DE BUSCA (3. Pinnacle como Oráculo)
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
                    
                    # Pinnacle como Oráculo
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
# 📧 FUNÇÃO DE ENVIO (5. Envia mesmo sem apostas)
# ==========================================
def enviar_email(dados_aprovados):
    data_atual = datetime.now().strftime("%d/%m/%Y")
    hora_atual = datetime.now().strftime("%H:%M")
    
    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = ", ".join(EMAILS_DESTINO)
    
    if dados_aprovados:
        df = pd.DataFrame(dados_aprovados)
        df = df.drop_duplicates().sort_values(by="ROI", ascending=False)
        tabela_html = df.to_html(index=False, justify='center', border=1, classes='table table-striped')
        
        msg["Subject"] = f"🔥 Alerta +EV: {len(df)} Oportunidades ({data_atual})"
        corpo_email = f"""
        <html><body>
          <h2>🤖 Alerta Quant: {len(df)} Oportunidades Encontradas!</h2>
          <p>Varredura de {data_atual}. Abaixo estão as apostas identificadas:</p>
          {tabela_html}
          <br><p><i>Finalizada em {data_atual} às {hora_atual}</i></p>
        </body></html>
        """
    else:
        msg["Subject"] = f"💤 Alerta Quant: Nenhuma Oportunidade ({data_atual})"
        corpo_email = f"""
        <html><body>
          <h2>🤖 Alerta Quant: Zero Oportunidades</h2>
          <p>A varredura de {data_atual} às {hora_atual} foi concluída.</p>
          <p>Nenhuma aposta atendeu aos nossos critérios matemáticos no momento.</p>
        </body></html>
        """

    msg.attach(MIMEText(corpo_email, "html"))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
        server.sendmail(EMAIL_REMETENTE, EMAILS_DESTINO, msg.as_string())
        server.quit()
        print(f"Relatório enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

if __name__ == "__main__":
    oportunidades = buscar_oportunidades()
    enviar_email(oportunidades)
