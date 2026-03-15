import os
import requests
import json
from datetime import datetime

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
FOOTBALL_DATA_TOKEN = os.environ.get('FOOTBALL_DATA_TOKEN')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
ARQUIVO_ESTADO = 'live_state.json'

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown", "disable_web_page_preview": True})

def carregar_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        try:
            with open(ARQUIVO_ESTADO, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, 'w') as f:
        json.dump(estado, f)

# ==========================================
# ⚽ MOTOR DO RADAR DE GOLOS AO VIVO
# ==========================================
def rastrear_todos_os_gols():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando varredura do Radar de Golos...")
    
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    # O parâmetro status=IN_PLAY,PAUSED garante que a API só nos devolve jogos que estão a acontecer AGORA.
    url_api = "https://api.football-data.org/v4/matches?status=IN_PLAY,PAUSED"
    
    try:
        resposta = requests.get(url_api, headers=headers)
        if resposta.status_code != 200:
            print(f"❌ Erro na API Football-Data: {resposta.status_code}")
            return
            
        jogos_ao_vivo = resposta.json().get('matches', [])
    except Exception as e:
        print(f"❌ Erro ao conectar na API: {e}")
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

        # Se o jogo é novo (não estava no nosso JSON)
        if id_jogo not in estado_atual:
            estado_atual[id_jogo] = placar_str
            # Só avisa se o jogo já tiver começado com golo, senão apenas guarda o 0x0
            if gols_casa > 0 or gols_fora > 0:
                houve_golo = True
                enviar_alerta_golo(competicao, minuto, casa, fora, gols_casa, gols_fora)
        
        # Se o jogo já existia no JSON, vamos comparar os placares
        else:
            placar_antigo = estado_atual[id_jogo]
            if placar_str != placar_antigo:
                # O PLACAR MUDOU! É GOLO!
                estado_atual[id_jogo] = placar_str
                houve_golo = True
                enviar_alerta_golo(competicao, minuto, casa, fora, gols_casa, gols_fora)

    # Limpeza de memória: Remove do JSON os jogos que já acabaram (não vieram no IN_PLAY da API)
    ids_ao_vivo = [str(j['id']) for j in jogos_ao_vivo]
    chaves_para_remover = [k for k in estado_atual.keys() if k not in ids_ao_vivo]
    for k in chaves_para_remover:
        del estado_atual[k]

    salvar_estado(estado_atual)
    if not houve_golo:
        print("Nenhum golo novo detetado nesta varredura.")

# ==========================================
# 🚨 FORMATADOR DE MENSAGENS E DEEP LINKS
# ==========================================
def enviar_alerta_golo(competicao, minuto, casa, fora, gols_casa, gols_fora):
    
    # Criação Inteligente de Links de Busca
    # Como as casas mudam as URLs constantemente, a forma mais robusta de deep link 
    # é forçar a busca (Search) pelas equipas dentro do site da casa de apostas.
    
    termo_busca = f"{casa} {fora}".replace(" ", "%20")
    
    # Pinnacle aceita query de busca direta na URL
    link_pinnacle = f"https://www.pinnacle.com/pt/search?q={termo_busca}"
    
    # BetMGM: Como a pesquisa deles é por Javascript, usamos um truque de busca avançada do Google 
    # que redireciona o utilizador diretamente para a página exata da partida dentro da BetMGM.
    link_betmgm = f"https://www.google.com/search?q=site:sports.betmgm.com+%22{casa}%22+%22{fora}%22"

    msg = (
        f"🚨 **GOOOOOOOOOL!** 🚨\n\n"
        f"🏆 {competicao} | ⏱️ {minuto}'\n"
        f"⚽ **{casa} {gols_casa} x {gols_fora} {fora}**\n\n"
        f"⚡ _O mercado vai recalcular as odds agora!_\n\n"
        f"🦁 [Verificar na BetMGM]({link_betmgm})\n"
        f"🟠 [Verificar na Pinnacle]({link_pinnacle})"
    )
    
    enviar_telegram(msg)
    print(f"⚽ ALERTA ENVIADO: {casa} {gols_casa}x{gols_fora} {fora}")

if __name__ == "__main__":
    rastrear_todos_os_gols()
