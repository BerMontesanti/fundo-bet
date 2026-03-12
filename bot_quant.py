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
# O robô busca as chaves secretas de forma segura
API_KEY = os.environ.get('ODDS_API_KEY')
SENHA_APP_GMAIL = os.environ.get('GMAIL_PASS') # 🔒 Senha agora protegida!

EMAIL_REMETENTE = "bernardo.montesanti@gmail.com"
EMAILS_DESTINO = [
    "bernardo.montesanti@gmail.com",
    "eduasy@hotmail.com"
]

BANCA_RS = 250.0
TAXA_USD = 5.20
BANCA_USDC = BANCA_RS / TAXA_USD
TARGET_EV = 0.05   # 5.0% ROI Mínimo
TARGET_EDGE = 0.025 # 2,5% Edge Mínimo

# ==========================================
# 🏆 LIGAS E ESPORTES A MONITORAR
# ==========================================
LIGAS = [
    # FUTEBOL - EUROPA (Elite)
    ("Futebol - Premier League (ING)", "soccer_epl"),
    ("Futebol - Championship (ING)", "soccer_england_championship"),
    ("Futebol - FA Cup (ING)", "soccer_fa_cup"),
    ("Futebol - La Liga (ESP)", "soccer_spain_la_liga"),
    ("Futebol - Serie A (ITA)", "soccer_italy_serie_a"),
    ("Futebol - Bundesliga (ALE)", "soccer_germany_bundesliga"),
    ("Futebol - Ligue 1 (FRA)", "soccer_france_ligue_one"),
    ("Futebol - Primeira Liga (POR)", "soccer_portugal_primeira_liga"),
    ("Futebol - Eredivisie (HOL)", "soccer_netherlands_eredivisie"),
    
    # FUTEBOL - EUROPA (Copas Continentais)
    ("Futebol - Champions League", "soccer_uefa_champs_league"),
    ("Futebol - Europa League", "soccer_uefa_europa_league"),
    ("Futebol - Conference League", "soccer_uefa_europa_conference_league"),
    
    # FUTEBOL - AMÉRICAS
    ("Futebol - Brasil Série A", "soccer_brazil_campeonato"),
    ("Futebol - Brasil Série B", "soccer_brazil_serie_b"),
    ("Futebol - Libertadores", "soccer_conmebol_libertadores"),
    ("Futebol - Sul-Americana", "soccer_conmebol_sudamericana"),
    ("Futebol - Argentina Primera", "soccer_argentina_primera_division"),
    ("Futebol - Colômbia Primera A", "soccer_colombia_primera_a"),
    ("Futebol - Chile Primera", "soccer_chile_campeonato"),
    ("Futebol - México Liga MX", "soccer_mexico_ligamx"),
    ("Futebol - MLS (EUA)", "soccer_usa_mls"),
    
    # BASQUETEBOL
    ("Basquete - NBA", "basketball_nba"),
    ("Basquete - WNBA", "basketball_wnba"),
    ("Basquete - NCAA (Universitário)", "basketball_ncaa"),
    ("Basquete - Euroleague", "basketball_euroleague"),
    ("Basquete - NBL (Austrália)", "basketball_nbl"),
    
    # TÊNIS
    ("Tênis - ATP Singles", "tennis_atp_match"),
    ("Tênis - WTA Singles", "tennis_wta_match"),
    
    # ESPORTES AMERICANOS
    ("Futebol Americano - NFL", "americanfootball_nfl"),
    ("Futebol Americano - NCAA", "americanfootball_ncaaf"),
    ("Futebol Americano - CFL (Canadá)", "americanfootball_cfl"),
    ("Beisebol - MLB", "baseball_mlb"),
    ("Beisebol - NCAA", "baseball_ncaa"),
    
    # LUTAS (MMA & BOXE)
    ("MMA - UFC", "mma_mixed_martial_arts"),
    ("Boxe - Combates", "boxing_boxing_match"),
    
    # E-SPORTS
    ("E-Sports - CS:GO / CS2", "esports_csgo_match_winner"),
    ("E-Sports - League of Legends", "esports_lol_match_winner"),
    ("E-Sports - Dota 2", "esports_dota2_match_winner"),
    
    # CRÍQUETE & RUGBY
    ("Críquete - IPL", "cricket_ipl"),
    ("Críquete - Test Matches", "cricket_test_match"),
    ("Rugby - Union", "rugby_union"),
    ("Rugby - League", "rugby_league"),
]

# ==========================================
# 🏠 CASAS DE APOSTAS
# ==========================================
CASAS_ALVO = [
    'bet365', 'betano', '1xbet', 'betfair_ex_eu', 'betfair_sb_uk', 
    'sport888', 'unibet_eu', 'betsson', 'coolbet', 'matchbook', 
    'marathonbet', 'nordicbet', 'williamhill',
    'bovada', 'betonlineag', 'mybookieag', 'draftkings', 'fanduel', 
    'betmgm', 'caesars', 'betrivers', 'superbook', 'pointsbetus',
    'skybet', 'paddypower', 'ladbrokes', 'coral', 'boylesports', 
    'virginbet', 'casumo'
]

# ==========================================
# 🚀 MOTOR DE BUSCA
# ==========================================
def buscar_oportunidades():
    target_bookmakers = 'pinnacle,' + ','.join(CASAS_ALVO)
    apostas_aprovadas = []
    
    # Captura a data exata de HOJE no horário de Brasília
    hoje_brt = (datetime.utcnow() - timedelta(hours=3)).date()
    
    print(f"Iniciando varredura para os jogos do dia {hoje_brt}...")
    for nome_liga, sport_key in LIGAS:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu,us,uk', 'markets': 'h2h', 'bookmakers': target_bookmakers})
            if res.status_code == 200:
                for ev in res.json():
                    dt = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    
                    # 🛑 FILTRO DE DATA: Ignora o jogo se não for hoje
                    if dt.date() != hoje_brt:
                        continue
                    
                    # Oráculo Pinnacle
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
            pass
            
    return apostas_aprovadas

# ==========================================
# 💾 SALVAR NO BANCO DE DADOS (CSV)
# ==========================================
def salvar_historico_csv(dados_aprovados):
    if not dados_aprovados:
        return
    
    arquivo_csv = 'historico_apostas.csv'
    df = pd.DataFrame(dados_aprovados)
    
    # Adiciona a data/hora em que o bot rodou
    df['Achado_em'] = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")
    
    existe = os.path.isfile(arquivo_csv)
    df.to_csv(arquivo_csv, mode='a', index=False, header=not existe)
    print(f"✅ {len(df)} apostas guardadas no banco de dados (CSV).")

# ==========================================
# 📧 FUNÇÃO DE ENVIO DE E-MAIL
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
        if not SENHA_APP_GMAIL:
            print("⚠️ ERRO: A senha do Gmail não foi encontrada nas variáveis de ambiente.")
            return

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
        server.sendmail(EMAIL_REMETENTE, EMAILS_DESTINO, msg.as_string())
        server.quit()
        print(f"📧 Relatório enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")

# ==========================================
# ⚙️ EXECUÇÃO PRINCIPAL
# ==========================================
if __name__ == "__main__":
    oportunidades = buscar_oportunidades()
    salvar_historico_csv(oportunidades) # ⬅️ Aqui está a nova função salvando o histórico!
    enviar_email(oportunidades)
