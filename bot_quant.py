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
EMAILS_DESTINO = ["bernardo.montesanti@gmail.com"]

try:
    with open('config_banca.json', 'r') as f:
        BANCA_RS = float(json.load(f).get('banca', 250.0))
except:
    BANCA_RS = 218.0
TAXA_USD = 5.20
BANCA_USDC = BANCA_RS / TAXA_USD
TARGET_EDGE = 0.025 

CASAS_ALVO = [
    'bet365', 'betano', '1xbet', 'betfair_ex_eu', 'betfair_sb_uk', 
    'sport888', 'unibet_eu', 'betsson', 'coolbet', 'matchbook', 
    'marathonbet', 'nordicbet', 'williamhill', 'bovada', 'betonlineag', 
    'draftkings', 'fanduel', 'betmgm', 'caesars', 'betrivers', 'skybet'
]

# ==========================================
# 🧠 CÉREBRO: AUTO-DISCOVERY & PORTFÓLIO
# ==========================================
def carregar_portfolio():
    try:
        with open('ligas_config.json', 'r') as f:
            return json.load(f)
    except:
        # Se não existir, arranca com um dicionário vazio
        return {"disponiveis": {}, "selecionadas": []}

def enviar_alerta_telegram_simples(mensagem):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"})

# ==========================================
# 🚀 MOTOR DE BUSCA (COM AUTO-DISCOVERY)
# ==========================================
def buscar_oportunidades():
    target_bookmakers = 'pinnacle,' + ','.join(CASAS_ALVO)
    apostas_aprovadas = []
    PLACAR_CACHE = {}
    
    apostas_ja_registadas = set()
    if os.path.isfile('historico_apostas.csv'):
        try:
            df_hist = pd.read_csv('historico_apostas.csv')
            for _, row in df_hist.iterrows():
                if 'Jogo' in row and 'Seleção' in row:
                    identificador = f"{str(row['Jogo']).strip()} | {str(row['Seleção']).strip()}"
                    apostas_ja_registadas.add(identificador)
        except Exception as e: pass
    
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    hoje_brt = agora_brt.date()
    
    # 1. Carrega o Catálogo e faz o ping na API (0 créditos)
    print("🌍 Iniciando Batedor de Ligas...")
    config_ligas = carregar_portfolio()
    
    try:
        ativos_api = requests.get('https://api.the-odds-api.com/v4/sports/', params={'apiKey': API_KEY}).json()
    except Exception as e:
        print(f"⚠️ Erro ao bater na API: {e}")
        return []

    # 2. AUTO-DISCOVERY E ATUALIZAÇÃO DE STATUS (HISTÓRICO MESTRE)
    novas_ativas = []
    novas_descobertas = []
    houve_mudanca = False
    
    for sport in ativos_api:
        if sport.get('active', True):
            k = sport['key']
            t = sport['title']
            novas_ativas.append(k)
            # Se a liga não existe no nosso catálogo histórico, adicionamos
            if k not in config_ligas.get('disponiveis', {}):
                config_ligas.setdefault('disponiveis', {})[k] = t
                novas_descobertas.append(t)
                houve_mudanca = True
                
    # Atualiza a memória de "Quem está ativo hoje"
    if config_ligas.get('ativas_agora') != novas_ativas:
        config_ligas['ativas_agora'] = novas_ativas
        houve_mudanca = True

    if houve_mudanca:
        with open('ligas_config.json', 'w') as f:
            json.dump(config_ligas, f, indent=4)
        os.system('git config --global user.name "github-actions[bot]"')
        os.system('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        os.system('git add ligas_config.json')
        os.system('git commit -m "🤖 [Batedor] Atualização de Catálogo e Status" || true')
        os.system('git push')
        
        # Só manda o Telegram se a mudança envolver ligas INÉDITAS no histórico
        if novas_descobertas:
            nomes_novos = ", ".join(novas_descobertas[:5]) + ("..." if len(novas_descobertas) > 5 else "")
            enviar_alerta_telegram_simples(f"🔔 *Radar Quant:* Novas ligas abriram mercado! ({nomes_novos})\n\nVá ao painel marcá-las caso queira operá-las.")

    # 3. FILTRO DE VARREDURA: Só varre o que está ativo AGORA e foi SELECIONADO por si no painel
    ligas_para_varrer = []
    for sport in ativos_api:
        if sport['key'] in config_ligas['selecionadas'] and sport.get('active', True):
            ligas_para_varrer.append((sport['title'], sport['key']))
            
    if not ligas_para_varrer:
        print("💤 Nenhuma liga selecionada está ativa no mercado neste momento.")
        return []

    print(f"🎯 Varredura focada em {len(ligas_para_varrer)} ligas ativas do seu portfólio...")
    
    # 4. LOOP DE VARREDURA NORMAL
    for nome_liga, sport_key in ligas_para_varrer:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu,us,uk', 'markets': 'h2h', 'bookmakers': target_bookmakers})
            
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
                        dt_pin_update_utc, hora_pin = None, "N/A"

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
                                dt_casa_update_utc, hora_casa = None, "N/A"
                            
                            diff_segundos = abs((dt_pin_update_utc - dt_casa_update_utc).total_seconds()) if dt_pin_update_utc and dt_casa_update_utc else 999 

                            link_bookmaker = b.get('link', '')
                            for o in b['markets'][0]['outcomes']:
                                selecao = o['name']
                                odd_soft = o['price']
                                prob_real_pin = probs.get(selecao)
                                odd_pin_bruta = next((op['price'] for op in outcomes_pin if op['name'] == selecao), 0.0)
                                link_final = o.get('link', b['markets'][0].get('link', link_bookmaker))
                                
                                if not link_final:
                                    termo_busca = f"{b['title']} {ev['home_team']} {ev['away_team']}".replace(" ", "+")
                                    link_final = f"https://www.google.com/search?q={termo_busca}"
                                
                                if prob_real_pin and prob_real_pin > 0:
                                    odd_justa = 1 / prob_real_pin
                                    roi = (prob_real_pin * odd_soft) - 1
                                    edge = prob_real_pin - (1 / odd_soft)
                                    alvo_ev_atual = 0.03 if odd_justa < 2.00 else (0.05 if odd_justa <= 4.00 else 0.07)

                                    if roi >= alvo_ev_atual and edge >= TARGET_EDGE:
                                        id_aposta = f"{jogo_nome} | {selecao}"
                                        if id_aposta in apostas_ja_registadas: continue 

                                        placar_texto = "Pré-live"
                                        if dt < agora_brt:
                                            if sport_key not in PLACAR_CACHE:
                                                url_scores = f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores/'
                                                res_scores = requests.get(url_scores, params={'apiKey': API_KEY, 'daysFrom': 1})
                                                PLACAR_CACHE[sport_key] = res_scores.json() if res_scores.status_code == 200 else []
                                            
                                            for ms in PLACAR_CACHE[sport_key]:
                                                if ms['home_team'] == ev['home_team'] and ms['away_team'] == ev['away_team']:
                                                    if ms.get('scores'):
                                                        gc = next((s['score'] for s in ms['scores'] if s['name'] == ev['home_team']), '0')
                                                        gf = next((s['score'] for s in ms['scores'] if s['name'] == ev['away_team']), '0')
                                                        placar_texto = f"Ao Vivo ({gc}x{gf})"
                                                    break

                                        odd_limite = max((alvo_ev_atual + 1) / prob_real_pin, 1 / (prob_real_pin - TARGET_EDGE) if prob_real_pin > TARGET_EDGE else float('inf'))
                                        b_kelly = odd_soft - 1
                                        f_kelly = (prob_real_pin * b_kelly - (1 - prob_real_pin)) / b_kelly
                                        stake = BANCA_USDC * (f_kelly * 0.25) * TAXA_USD

                                        # ==========================================
                                        # 🛡️ TRIAGEM INTELIGENTE DE DUPLICATAS (BetMGM Update)
                                        # ==========================================
                                        is_duplicata = False
                                        if not df_historico.empty and 'Jogo' in df_historico.columns:
                                            mask = (df_historico['Jogo'] == jogo) & (df_historico['Casa'] == casa) & (df_historico['Seleção'] == selecao)
                                            
                                            if mask.any():
                                                is_duplicata = True # Já existe no banco de dados!
                                                
                                                # Se for BetMGM, nós ATUALIZAMOS a linha existente no Dataframe em memória!
                                                if 'betmgm' in casa.lower():
                                                    idx = df_historico[mask].index[-1] # Pega a entrada original
                                                    
                                                    df_historico.at[idx, 'Odd Casa'] = odd_soft
                                                    df_historico.at[idx, 'Edge'] = f"{edge*100:.2f}%" # Atenção: no seu código original chamava-se edge_calc ou edge? Use a variável correta do seu script.
                                                    df_historico.at[idx, 'ROI'] = f"{roi*100:.2f}%"   # Mesma coisa para o roi.
                                                    df_historico.at[idx, 'Stake'] = f"R$ {stake:.2f}"
                                                    df_historico.at[idx, 'Odd Pinnacle'] = odd_pin_bruta
                                                    df_historico.at[idx, 'Gap_Segundos'] = int(diff_segundos)
                                                    df_historico.at[idx, 'Achado_em'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                                    
                                                    global houve_atualizacao_betmgm
                                                    houve_atualizacao_betmgm = True
                                                    print(f"🔄 Line Movement (BetMGM): {jogo} atualizado para Odd {odd_soft}")
                                                
                                                # Independentemente da casa, se já existe, salta fora e NÃO adiciona de novo!
                                                continue 
                                        
                                        # Se chegou aqui, é porque é uma aposta 100% INÉDITA. Adiciona à lista:
                                        apostas_aprovadas.append({
                                            "Data/Hora": dt.strftime("%d/%m %H:%M"), "Liga": nome_liga, "Jogo": jogo_nome, "Casa": b['title'],
                                            "Seleção": selecao, "Odd Casa": f"{odd_soft:.2f}", "Hora Casa": hora_casa, "Odd Pinnacle": f"{odd_pin_bruta:.2f}",
                                            "Hora Pinnacle": hora_pin, "Gap_Segundos": int(diff_segundos), "Odd Justa": f"{odd_justa:.2f}",
                                            "Odd Limite": f"{odd_limite:.2f}", "Edge": round(edge * 100, 2), "ROI": round(roi * 100, 2),
                                            "Stake": f"R$ {stake:.2f}", "Status_Partida": placar_texto, "Link": link_final
                                        })
        except Exception as e:
            print(f"❌ Erro de processamento na liga {nome_liga}: {e}")
            
    return apostas_aprovadas

# ==========================================
# 💾 SALVAR NO BANCO DE DADOS (CSV)
# ==========================================
def salvar_historico_csv(dados_aprovados):
    if not dados_aprovados: return
    df_novo = pd.DataFrame(dados_aprovados)
    if 'Link' in df_novo.columns: df_novo = df_novo.drop(columns=['Link'])
    df_novo['Achado_em'] = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")
    
    if os.path.isfile('historico_apostas.csv'):
        try:
            df_final = pd.concat([pd.read_csv('historico_apostas.csv'), df_novo], ignore_index=True)
        except: df_final = df_novo
    else: df_final = df_novo
        
    df_final.to_csv('historico_apostas.csv', index=False)
    print(f"✅ {len(df_novo)} apostas salvas.")

# ==========================================
# 📱 FUNÇÃO DE ENVIO PARA O TELEGRAM (FILTRO BETMGM)
# ==========================================
def enviar_telegram(dados_aprovados):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # 1. Se a varredura global não achou NADA em NENHUMA casa
    if not dados_aprovados:
        texto_vazio = "💤 *Alerta VIP BetMGM:* A varredura foi concluída, mas o mercado está seco. Zero oportunidades encontradas."
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_vazio, "parse_mode": "Markdown"})
        return 

    # Converte para DataFrame e FILTRA apenas o que for BetMGM
    df_completo = pd.DataFrame(dados_aprovados)
    df_betmgm = df_completo[df_completo['Casa'].str.lower().str.contains('betmgm', na=False)].sort_values(by="ROI", ascending=False)

    # 2. Se achou apostas no mundo (ex: Betano, Bet365), mas NENHUMA na BetMGM
    if df_betmgm.empty:
        texto_sem_mgm = "💤 *Alerta VIP BetMGM:* Varredura concluída. O robô encontrou oportunidades noutras casas (ver Email/Painel), mas *NADA* na BetMGM desta vez."
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_sem_mgm, "parse_mode": "Markdown"})
        return

    # 3. Se achou Oportunidades na BetMGM, manda a lista!
    texto_resumo = f"🦁 *Alerta VIP BetMGM:* Encontradas {len(df_betmgm)} NOVAS oportunidades matemáticas!"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto_resumo, "parse_mode": "Markdown"})

    for index, row in df_betmgm.iterrows():
        af = f"⚡ *Sincronismo Perfeito:* {row['Gap_Segundos']}s de desfasamento." if row['Gap_Segundos'] <= 10 else (f"⚠️ *Aviso:* Tempo não fornecido." if row['Gap_Segundos'] == 999 else f"👻 *CUIDADO (ODD FANTASMA):* {row['Gap_Segundos']}s de atraso!")
        
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
            f"{af}\n"
            f"📉 *(Odd Limite Aceitável: {row['Odd Limite']})*\n\n"
            f"📈 *Edge:* {row['Edge']}% | *ROI:* {row['ROI']}%\n"
            f"💰 *Stake Recomendada:* {row['Stake']}\n\n"
            f"🔗 [👉 ABRIR DIRETO NA BETMGM 👈]({row['Link']})\n\n"
            f"🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨"
        )
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg_aposta, "parse_mode": "Markdown", "disable_web_page_preview": True})

# ==========================================
# 📧 FUNÇÃO DE ENVIO DE E-MAIL
# ==========================================
def enviar_email(dados_aprovados):
    dt, hr = datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M")
    msg = MIMEMultipart("alternative")
    msg["From"], msg["To"] = EMAIL_REMETENTE, ", ".join(EMAILS_DESTINO)
    
    if dados_aprovados:
        df = pd.DataFrame(dados_aprovados).drop(columns=['Link'], errors='ignore').drop_duplicates().sort_values(by="ROI", ascending=False)
        msg["Subject"] = f"🔥 Alerta Global +EV: {len(df)} Oportunidades ({dt})"
        msg.attach(MIMEText(f"<html><body><h2>🤖 Alerta Quant</h2>{df.to_html(index=False)}</body></html>", "html"))
    else:
        msg["Subject"] = f"💤 Alerta Global: Zero Oportunidades ({dt})"
        msg.attach(MIMEText("<html><body>Nenhuma nova oportunidade.</body></html>", "html"))

    if SENHA_APP_GMAIL:
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
                server.sendmail(EMAIL_REMETENTE, EMAILS_DESTINO, msg.as_string())
        except: pass

if __name__ == "__main__":
    oportunidades = buscar_oportunidades()
    salvar_historico_csv(oportunidades)
    enviar_telegram(oportunidades)
    enviar_email(oportunidades)
