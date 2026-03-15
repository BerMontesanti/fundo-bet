import requests
import json
import time
from datetime import datetime

# ==========================================
# ⚙️ CONFIGURAÇÕES (COLE AS SUAS CHAVES AQUI)
# ==========================================
FOOTBALL_DATA_TOKEN = "COLE_AQUI_SEU_TOKEN_DA_FOOTBALL_DATA"
TELEGRAM_TOKEN = "COLE_AQUI_SEU_TOKEN_DO_TELEGRAM"
TELEGRAM_CHAT_ID = "COLE_AQUI_SEU_CHAT_ID"

ARQUIVO_ESTADO = 'live_state.json'

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown", "disable_web_page_preview": True})

def carregar_estado():
    try:
        with open(ARQUIVO_ESTADO, 'r') as f:
            return json.load(f)
    except:
        return {}

def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, 'w') as f:
        json.dump(estado, f)

# ==========================================
# ⚽ MOTOR DO RADAR DE GOLOS AO VIVO
# ==========================================
def rastrear_todos_os_gols():
    agora = datetime.now().strftime('%H:%M:%S')
    print(f"[{agora}] A varrer os relvados...")
    
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    url_api = "https://api.football-data.org/v4/matches?status=IN_PLAY,PAUSED"
    
    try:
        resposta = requests.get(url_api, headers=headers)
        if resposta.status_code != 200:
            print(f"❌ Erro na API: {resposta.status_code}")
            return
            
        jogos_ao_vivo = resposta.json().get('matches', [])
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return

    estado_atual = carregar_estado()
    houve_golo = False

    for jogo in jogos_ao_vivo:
        id_jogo = str(jogo['id'])
        competicao = jogo['competition']['name']
        minuto = jogo.get('minute', 'Ao Vivo')
        
        casa = jogo['homeTeam']['name']
        fora = jogo['awayTeam']['name']
        
        gols_casa = jogo['score']['fullTime']['home']
        gols_fora = jogo['score']['fullTime']['away']
        
        if gols_casa is None: gols_casa = 0
        if gols_fora is None: gols_fora = 0
        
        placar_str = f"{gols_casa}-{gols_fora}"

        if id_jogo not in estado_atual:
            estado_atual[id_jogo] = placar_str
            if gols_casa > 0 or gols_fora > 0:
                houve_golo = True
                hora_exata_detecao = datetime.now().strftime('%H:%M:%S')
                enviar_alerta_golo(competicao, minuto, casa, fora, gols_casa, gols_fora, hora_exata_detecao)
        else:
            placar_antigo = estado_atual[id_jogo]
            if placar_str != placar_antigo:
                estado_atual[id_jogo] = placar_str
                houve_golo = True
                hora_exata_detecao = datetime.now().strftime('%H:%M:%S')
                enviar_alerta_golo(competicao, minuto, casa, fora, gols_casa, gols_fora, hora_exata_detecao)

    ids_ao_vivo = [str(j['id']) for j in jogos_ao_vivo]
    chaves_para_remover = [k for k in estado_atual.keys() if k not in ids_ao_vivo]
    for k in chaves_para_remover:
        del estado_atual[k]

    salvar_estado(estado_atual)

# ==========================================
# 🚨 FORMATADOR DE MENSAGENS E DEEP LINKS
# ==========================================
def enviar_alerta_golo(competicao, minuto, casa, fora, gols_casa, gols_fora, hora_exata):
    termo_busca = f"{casa} {fora}".replace(" ", "%20")
    link_pinnacle = f"https://www.pinnacle.com/pt/search?q={termo_busca}"
    link_betmgm = f"https://www.google.com/search?q=site:sports.betmgm.com+%22{casa}%22+%22{fora}%22"

    msg = (
        f"🚨 **GOOOOOOOOOL!** 🚨\n\n"
        f"🏆 {competicao} | ⏱️ {minuto}'\n"
        f"⏰ **Detetado às:** {hora_exata}\n"
        f"⚽ **{casa} {gols_casa} x {gols_fora} {fora}**\n\n"
        f"⚡ _O mercado vai recalcular as odds!_\n\n"
        f"🦁 [Verificar na BetMGM]({link_betmgm})\n"
        f"🟠 [Verificar na Pinnacle]({link_pinnacle})"
    )
    
    enviar_telegram(msg)
    print(f"⚽ ALERTA ENVIADO [{hora_exata}]: {casa} {gols_casa}x{gols_fora} {fora}")

# ==========================================
# ⚙️ EXECUÇÃO EM LOOP INFINITO (LOCAL)
# ==========================================
if __name__ == "__main__":
    print("🚀 Radar de Golos (Modo Local) iniciado!")
    print("O robô fará uma varredura a cada 30 segundos.")
    print("Pressione Ctrl+C nesta janela para parar o radar.\n")
    
    while True:
        rastrear_todos_os_gols()
        # Pausa de 30 segundos entre cada varredura (2 requests por minuto = totalmente seguro para a API)
        time.sleep(30)
