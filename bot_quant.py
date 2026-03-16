import os
import requests
import pandas as pd
import smtplib
import urllib.parse
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json

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

try:
    with open('config_banca.json', 'r') as f:
        BANCA_RS = float(json.load(f).get('banca', 250.0))
except:
    BANCA_RS = 218.0
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
    ("Tênis - ATP Singles", "tennis_atp_match"),
    ("Tênis - WTA Singles", "tennis_wta_match"),
    ("Futebol Americano - NFL", "americanfootball_nfl"),
]

# ==========================================
# 🏠 CASAS DE APOSTAS
# ==========================================
CASAS_ALVO = [
    'bet365', 'betano', '1xbet', 'betfair_ex_eu', 'betfair_sb_uk', 
    'sport888', 'unibet_eu', 'betsson', 'coolbet', 'matchbook', 
    'marathonbet', 'nordicbet', 'williamhill', 'bovada', 'betonlineag', 
    'draftkings', 'fanduel', 'betmgm', 'caesars', 'betrivers', 'skybet'
]

# ==========================================
# 🧠 TRIAGEM GRATUITA (CÉREBRO DO ROBÔ)
# ==========================================
def obter_ligas_ativas(api_key):
    """
    Bate no endpoint gratuito da The Odds API para descobrir 
    quais esportes têm odds abertas neste exato momento.
    Custo: 0 créditos.
    """
    url = 'https://api.the-odds-api.com/v4/sports/'
    try:
        res = requests.get(url, params={'apiKey': api_key})
        if res.status_code == 200:
            return {sport['key'] for sport in res.json()}
        else:
            print(f"⚠️ Erro ao buscar ligas ativas: {res.status_code}")
            return set()
    except Exception as e:
        print(f"⚠️ Erro de conexão na triagem: {e}")
        return set()

# ==========================================
# 🚀 MOTOR DE BUSCA (LABORATÓRIO DE GHOST ODDS)
# ==========================================
def buscar_oportunidades():
    target_bookmakers = 'pinnacle,' + ','.join(CASAS_ALVO)
    apostas_aprovadas = []
    PLACAR_CACHE = {}
    
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
            print(f"Aviso: Não foi possível carregar o histórico ({e})")
    
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    hoje_brt = agora_brt.date()
    
    print("🔍 Iniciando triagem de ligas ativas (Custo: 0 créditos)...")
    ligas_ativas_api = obter_ligas_ativas(API_KEY)
    
    ligas_para_varrer = []
    if ligas_ativas_api:
        for nome, chave in LIGAS:
            if chave in ligas_ativas_api:
                ligas_para_varrer.append((nome, chave))
        print(f"🎯 Triagem concluída: Das {len(LIGAS)} ligas monitoradas, apenas {len(ligas_para_varrer)} estão com mercado aberto agora.")
    else:
        print("⚠️ Falha na triagem ou nenhuma liga ativa. Varrendo todas por segurança.")
        ligas_para_varrer = LIGAS

    print(f"A iniciar varredura para os jogos do dia {hoje_brt} nas ligas ativas...")
    
    for nome_liga, sport_key in ligas_para_varrer:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url, params={
                'apiKey': API_KEY, 
                'regions': 'eu,us,uk', 
                'markets': 'h2h', 
                'bookmakers': target_bookmakers,
                'includeLinks': 'true'
            })
            
            if res.status_code == 200:
                for ev in res.json():
                    dt = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    if dt.date() != hoje_brt: continue
                    
                    bookie_pin = next((b for b in ev['bookmakers'] if b['key'] == 'pinnacle'), None)
                    if not bookie_pin: continue
                    
                    try:
                        dt_pin_update_utc = datetime.strptime(bookie_pin.get('last_update', ''), "%Y-%m-%dT%H:%M:%SZ")
                        hora_pin = (dt_pin_update_utc - timedelta(hours=3)).strftime("%H:%M:%S")
                    except:
                        dt_pin_update_utc = None
                        hora_pin = "N/A"

                    outcomes_pin = bookie_pin['markets'][0]['outcomes']
                    sum_inv = sum([1/o['price'] for o in outcomes_pin])
                    probs = {o['name']: (1/o['price']) / sum_inv for o in outcomes_pin}
                    
                    jogo_nome = f"{ev['home_team']} x {ev['away_team']}"
                    
                    for b in ev['bookmakers']:
                        if b['key'] in CASAS_ALVO:
                            try:
                                dt_casa_update_utc = datetime.strptime(b.get('last_update', ''), "%Y-%m-%dT%H:%M:%SZ")
                                hora_casa = (dt_casa_update_utc - timedelta(hours=3)).strftime("%H:%M:%S")
                            except:
                                dt_casa_update_utc = None
                                hora_casa = "N/A"
                            
                            # 🛑 CÁLCULO DA GHOST ODD (SEM BLOQUEAR)
                            if dt_pin_update_utc and dt_casa_update_utc:
                                diff_segundos = abs((dt_pin_update_utc - dt_casa_update_utc).total_seconds())
                            else:
                                diff_segundos = 999 

                            link_bookmaker = b.get('link', '')
                            
                            for o in b['markets'][0]['outcomes']:
                                selecao = o['name']
                                odd_soft = o['price']
                                prob_real_pin = probs.get(selecao)
                                
                                odd_pin_bruta = next((op['price'] for op in outcomes_pin if op['name'] == selecao), 0.0)
                                
                                link_mercado = b['markets'][0].get('link', link_bookmaker)
                                link_final = o.get('link', link_mercado)
                                
                                if 'betmgm' in b['key'].lower():
                                    time_busca = urllib.parse.quote(ev['home_team'])
                                    link_final = f"https://sports.betmgm.com/en/sports/search?q={time_busca}"
                                elif not link_final:
                                    termo_busca = f"{b['title']} {ev['home_team']} {ev['away_team']}".replace(" ", "+")
                                    link_final = f"https://www.google.com/search?q={termo_busca}"
                                
                                if prob_real_pin and prob_real_pin > 0:
                                    odd_justa = 1 / prob_real_pin
                                    roi = (prob_real_pin * odd_soft) - 1
                                    edge = prob_real_pin - (1 / odd_soft)
                                    
                                    if odd_justa < 2.00: alvo_ev_atual = 0.03
                                    elif odd_justa <= 4.00: alvo_ev_atual = 0.05
                                    else: alvo_ev_atual = 0.07

                                    if roi >= alvo_ev_atual and edge >= TARGET_EDGE:
                                        
                                        id_aposta = f"{jogo_nome} | {selecao}"
                                        if id_aposta in apostas_ja_registadas:
                                            continue 

                                        placar_texto = "Pré-live"
                                        
                                        if dt < agora_brt:
                                            if sport_key not in PLACAR_CACHE:
                                                url_scores = f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores/'
                                                res_scores = requests.get(url_scores, params={'apiKey': API_KEY, 'daysFrom': 1})
                                                if res_scores.status_code == 200:
                                                    PLACAR_CACHE[sport_key] = res_scores.json()
                                                else:
                                                    PLACAR_CACHE[sport_key] = []
                                            
                                            for match_score in PLACAR_CACHE[sport_key]:
                                                if match_score['home_team'] == ev['home_team'] and match_score['away_team'] == ev['away_team']:
                                                    if match_score.get('scores'):
                                                        gols_casa = next((s['score'] for s in match_score['scores'] if s['name'] == ev['home_team']), '0')
                                                        gols_fora = next((s['score'] for s in match_score['scores'] if s['name'] == ev['away_team']), '0')
                                                        placar_texto = f"Ao Vivo ({gols_casa}x{gols_fora})"
                                                    break

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
                                            "Hora Casa": hora_casa,
                                            "Odd Pinnacle": f"{odd_pin_bruta:.2f}",
                                            "Hora Pinnacle": hora_pin,
                                            "Gap_Segundos": int(diff_segundos),
                                            "Odd Justa": f"{odd_justa:.2f}",
                                            "Odd Limite": f"{odd_limite:.2f}",
                                            "Edge": round(edge * 100, 2),
                                            "ROI": round(roi * 100, 2),
                                            "Stake": f"R$ {stake:.2f}",
                                            "Status_Partida": placar_texto,
                                            "Link": link_final
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
    
    df_novo = pd.DataFrame(dados_aprovados)
    if 'Link' in df_novo.columns:
        df_novo = df_novo.drop(columns=['Link'])
        
    df_novo['Achado_em'] = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")
    
    # VACINA: Prevenção de Data-Shift usando pd.concat
    if os.path.isfile(arquivo_csv):
        try:
            df_existente = pd.read_csv(arquivo_csv)
            df_final = pd.concat([df_existente, df_novo], ignore_index=True)
        except Exception as e:
            print(f"Erro ao cruzar com o CSV antigo: {e}. A criar ficheiro novo.")
            df_final = df_novo
    else:
        df_final = df_novo
        
    df_final.to_csv(arquivo_csv, index=False)
    print(f"✅ {len(df_novo)} apostas novas guardadas de forma segura (sem Data Shift).")

# ==========================================
# 📱 FUNÇÃO DE ENVIO PARA O TELEGRAM
# ==========================================
def enviar_telegram(dados_aprovados):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    if not dados_aprovados:
        texto = "💤 *Alerta Quant:* A varredura foi concluída, mas não há NOVAS oportunidades de valor no momento."
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"})
        return

    df = pd.DataFrame(dados_aprovados).sort_values(by="ROI", ascending=False)
    
    texto_resumo = f"🔥 *Alerta Quant:* Encontradas {len(df)} NOVAS oportunidades matemáticas!\n\nA enviar a lista abaixo:"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_resumo, "parse_mode": "Markdown"})

    for index, row in df.iterrows():
        
        # 🛑 LÓGICA DE ALERTA DE GHOST ODD
        if row['Gap_Segundos'] <= 10:
            alerta_fantasma = f"⚡ *Sincronismo Perfeito:* {row['Gap_Segundos']}s de desfasamento."
        elif row['Gap_Segundos'] == 999:
            alerta_fantasma = f"⚠️ *Aviso:* Tempo de atualização não fornecido pelas casas."
        else:
            alerta_fantasma = f"👻 *CUIDADO (ODD FANTASMA):* {row['Gap_Segundos']}s de atraso na casa de aposta!"

        if "betmgm" in str(row['Casa']).lower():
            msg_aposta = (
                f"🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨\n"
                f"🦁 🚨 *OPORTUNIDADE BETMGM* 🚨 🦁\n"
                f"🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨\n\n"
                f"⚽ *{row['Jogo']}*\n"
                f"🏆 {row['Liga']} | ⏰ Jogo às {row['Data/Hora']}\n"
                f"⏱️ **Status:** {row['Status_Partida']}\n\n"
                f"🎯 *Seleção:* {row['Seleção']}\n"
                f"🔮 *Oráculo (Pinnacle):* {row['Odd Pinnacle']} _(às {row['Hora Pinnacle']})_\n"
                f"📊 *Odd Casa:* {row['Odd Casa']} _(às {row['Hora Casa']})_\n"
                f"{alerta_fantasma}\n"
                f"📉 *(Odd Limite Aceitável: {row['Odd Limite']})*\n\n"
                f"📈 *Edge:* {row['Edge']}% | *ROI:* {row['ROI']}%\n"
                f"💰 *Stake Recomendada:* {row['Stake']}\n\n"
                f"🔗 [👉 ABRIR DIRETO NA BETMGM 👈]({row['Link']})\n\n"
                f"🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨"
            )
        else:
            msg_aposta = (
                f"⚽ *{row['Jogo']}*\n"
                f"🏆 {row['Liga']} | ⏰ Jogo às {row['Data/Hora']}\n"
                f"⏱️ **Status:** {row['Status_Partida']}\n\n"
                f"🏠 *Casa:* {row['Casa']}\n"
                f"🎯 *Seleção:* {row['Seleção']}\n"
                f"🔮 *Oráculo (Pinnacle):* {row['Odd Pinnacle']} _(às {row['Hora Pinnacle']})_\n"
                f"📊 *Odd Atual:* {row['Odd Casa']} _(às {row['Hora Casa']})_\n"
                f"{alerta_fantasma}\n"
                f"📉 *(Odd Limite Aceitável: {row['Odd Limite']})*\n\n"
                f"📈 *Edge:* {row['Edge']}% | *ROI:* {row['ROI']}%\n"
                f"💰 *Stake Recomendada:* {row['Stake']}\n\n"
                f"🔗 [IR PARA A CASA DE APOSTAS]({row['Link']})"
            )
        
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg_aposta, "parse_mode": "Markdown", "disable_web_page_preview": True})

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
        if 'Link' in df.columns:
            df = df.drop(columns=['Link']) 
            
        df = df.drop_duplicates().sort_values(by="ROI", ascending=False)
        tabela_html = df.to_html(index=False, justify='center', border=1, classes='table table-striped')
        
        msg["Subject"] = f"🔥 Alerta +EV: {len(df)} Novas Oportunidades ({data_atual})"
        corpo_email = f"""
        <html><body>
          <h2>🤖 Alerta Quant: {len(df)} Novas Oportunidades Encontradas!</h2>
          <p>Varredura de {data_atual}. Abaixo estão as apostas identificadas (Com tracking de Ghost Odds):</p>
          {tabela_html}
          <br><p><i>Finalizada em {data_atual} às {hora_atual}</i></p>
        </body></html>
        """
    else:
        msg["Subject"] = f"💤 Alerta Quant: Nenhuma Nova Oportunidade ({data_atual})"
        corpo_email = f"<html><body><h2>🤖 Alerta Quant: Zero Novas Oportunidades</h2></body></html>"

    msg.attach(MIMEText(corpo_email, "html"))

    try:
        if not SENHA_APP_GMAIL: return
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
        server.sendmail(EMAIL_REMETENTE, EMAILS_DESTINO, msg.as_string())
        server.quit()
        print("📧 Relatório enviado com sucesso via E-mail!")
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")

if __name__ == "__main__":
    oportunidades = buscar_oportunidades()
    salvar_historico_csv(oportunidades)
    enviar_telegram(oportunidades)
    enviar_email(oportunidades)
