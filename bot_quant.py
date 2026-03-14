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
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

EMAIL_REMETENTE = "bernardo.montesanti@gmail.com"
EMAILS_DESTINO = [
    "bernardo.montesanti@gmail.com"
]

BANCA_RS = 250.0
TAXA_USD = 5.20
BANCA_USDC = BANCA_RS / TAXA_USD

TARGET_EDGE = 0.025 # 2.5% Edge Mínimo de Segurança Inegociável

# ==========================================
# 🏆 LIGAS E ESPORTES A MONITORAR
# ==========================================
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
    ("Basquete - NBL (Austrália)", "basketball_nbl"),
    ("Tênis - ATP Singles", "tennis_atp_match"),
    ("Tênis - WTA Singles", "tennis_wta_match"),
    ("Futebol Americano - NFL", "americanfootball_nfl"),
    ("Futebol Americano - NCAA", "americanfootball_ncaaf"),
    ("Futebol Americano - CFL", "americanfootball_cfl"),
    ("Beisebol - MLB", "baseball_mlb"),
    ("Beisebol - NCAA", "baseball_ncaa"),
    ("MMA - UFC", "mma_mixed_martial_arts"),
    ("Boxe - Combates", "boxing_boxing_match"),
    ("E-Sports - CS:GO / CS2", "esports_csgo_match_winner"),
    ("E-Sports - League of Legends", "esports_lol_match_winner"),
    ("E-Sports - Dota 2", "esports_dota2_match_winner"),
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
# 🚀 MOTOR DE BUSCA (COM MEMÓRIA ANTI-SPAM)
# ==========================================
def buscar_oportunidades():
    target_bookmakers = 'pinnacle,' + ','.join(CASAS_ALVO)
    apostas_aprovadas = []
    
    # --- LER O HISTÓRICO PARA CRIAR A MEMÓRIA DO ROBÔ ---
    apostas_ja_registadas = set()
    arquivo_csv = 'historico_apostas.csv'
    if os.path.isfile(arquivo_csv):
        try:
            df_hist = pd.read_csv(arquivo_csv)
            for _, row in df_hist.iterrows():
                if 'Jogo' in row and 'Seleção' in row:
                    identificador = f"{str(row['Jogo']).strip()} | {str(row['Seleção']).strip()}"
                    apostas_ja_registadas.add(identificador)
        except Exception as e:
            print(f"Aviso: Não foi possível carregar o histórico para memória ({e})")
    # ----------------------------------------------------
    
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
                    
                    jogo_nome = f"{ev['home_team']} x {ev['away_team']}"
                    
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
                                    
                                    if odd_justa < 2.00:
                                        alvo_ev_atual = 0.03
                                    elif odd_justa <= 4.00:
                                        alvo_ev_atual = 0.05
                                    else:
                                        alvo_ev_atual = 0.07

                                    if roi >= alvo_ev_atual and edge >= TARGET_EDGE:
                                        
                                        # --- FILTRO DE MEMÓRIA (ANTI-SPAM) ---
                                        id_aposta = f"{jogo_nome} | {selecao}"
                                        if id_aposta in apostas_ja_registadas:
                                            continue 
                                        # --------------------------------------

                                        odd_min_ev = (alvo_ev_atual + 1) / prob_real_pin
                                        odd_min_edge = 1 / (prob_real_pin - TARGET_EDGE) if prob_real_pin > TARGET_EDGE else float('inf')
                                        odd_limite = max(odd_min_ev, odd_min_edge)

                                        b_kelly = odd_soft - 1
                                        f_kelly = (prob_real_pin * b_kelly - (1 - prob_real_pin)) / b_kelly
                                        stake = BANCA_USDC * (f_kelly * 0.25) * TAXA_USD
                                        
                                        apostas_aprovadas.append({
                                            "Data/Hora": dt.strftime("%d/%m %H:%M"),
                                            "Liga": nome_liga,
                                            "Jogo": jogo_nome,
                                            "Casa": b['title'],
                                            "Seleção": selecao,
                                            "Odd Casa": f"{odd_soft:.2f}",
                                            "Odd Justa": f"{odd_justa:.2f}",
                                            "Odd Limite": f"{odd_limite:.2f}",
                                            "Edge": round(edge * 100, 2),
                                            "ROI": round(roi * 100, 2),
                                            "Stake": f"R$ {stake:.2f}"
                                        })
            else:
                print(f"❌ Erro na API para a liga {nome_liga}. Status: {res.status_code}")
        except Exception as e:
            print(f"❌ Erro de processamento na liga {nome_liga}: {e}")
            
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
    print(f"✅ {len(df)} apostas novas guardadas no ficheiro (CSV).")

# ==========================================
# 📱 FUNÇÃO DE ENVIO PARA O TELEGRAM (ATUALIZADA)
# ==========================================
def enviar_telegram(dados_aprovados):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Credenciais do Telegram não encontradas nas variáveis de ambiente.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    if not dados_aprovados:
        texto = "💤 *Alerta Quant:* A varredura foi concluída, mas não há NOVAS oportunidades de valor no momento."
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"})
        print("📱 Notificação de zero novas apostas enviada para o Telegram.")
        return

    df = pd.DataFrame(dados_aprovados).sort_values(by="ROI", ascending=False)
    
    texto_resumo = f"🔥 *Alerta Quant:* Encontradas {len(df)} NOVAS oportunidades +EV!\n\nA enviar a lista abaixo:"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_resumo, "parse_mode": "Markdown"})

    for index, row in df.iterrows():
        # --- LÓGICA DE DESTAQUE PARA BETMGM ---
        if "betmgm" in str(row['Casa']).lower():
            alerta_topo = "🦁 🚨 *OPORTUNIDADE EXCLUSIVA BETMGM* 🚨 🦁\n\n"
        else:
            alerta_topo = ""
        # --------------------------------------

        msg_aposta = (
            f"{alerta_topo}"
            f"⚽ *{row['Jogo']}*\n"
            f"🏆 {row['Liga']} | ⏰ {row['Data/Hora']}\n"
            f"🏠 *Casa:* {row['Casa']}\n"
            f"🎯 *Seleção:* {row['Seleção']}\n"
            f"📊 *Odd Atual:* {row['Odd Casa']} *(Limite: {row['Odd Limite']})*\n"
            f"📈 *Edge:* {row['Edge']}% | *ROI:* {row['ROI']}%\n"
            f"💰 *Stake Recomendada:* {row['Stake']}"
        )
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg_aposta, "parse_mode": "Markdown"})
    
    print(f"📱 {len(df)} novas mensagens enviadas com sucesso para o Telegram!")

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
        
        msg["Subject"] = f"🔥 Alerta +EV: {len(df)} Novas Oportunidades ({data_atual})"
        corpo_email = f"""
        <html><body>
          <h2>🤖 Alerta Quant: {len(df)} Novas Oportunidades Encontradas!</h2>
          <p>Varredura de {data_atual}. Abaixo estão as apostas identificadas (sem repetições):</p>
          {tabela_html}
          <br><p><i>Finalizada em {data_atual} às {hora_atual}</i></p>
        </body></html>
        """
    else:
        msg["Subject"] = f"💤 Alerta Quant: Nenhuma Nova Oportunidade ({data_atual})"
        corpo_email = f"""
        <html><body>
          <h2>🤖 Alerta Quant: Zero Novas Oportunidades</h2>
          <p>A varredura de {data_atual} às {hora_atual} foi concluída.</p>
          <p>Nenhuma aposta inédita atendeu aos nossos critérios matemáticos no momento.</p>
        </body></html>
        """

    msg.attach(MIMEText(corpo_email, "html"))

    try:
        if not SENHA_APP_GMAIL:
            return

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
        server.sendmail(EMAIL_REMETENTE, EMAILS_DESTINO, msg.as_string())
        server.quit()
        print("📧 Relatório enviado com sucesso via E-mail!")
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")

# ==========================================
# ⚙️ EXECUÇÃO PRINCIPAL
# ==========================================
if __name__ == "__main__":
    oportunidades = buscar_oportunidades()
    salvar_historico_csv(oportunidades)
    enviar_telegram(oportunidades)
    enviar_email(oportunidades)
