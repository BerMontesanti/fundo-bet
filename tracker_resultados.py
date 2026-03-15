import os
import requests
import pandas as pd
from datetime import datetime
import time

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
FOOTBALL_DATA_TOKEN = os.environ.get('FOOTBALL_DATA_TOKEN') # Sua nova chave da Football-Data.org
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
ARQUIVO_CSV = 'historico_apostas.csv'

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"})

# ==========================================
# ⚽ FUNÇÃO PRINCIPAL DO TRACKER LIVE
# ==========================================
def rastrear_jogos_pendentes():
    if not os.path.exists(ARQUIVO_CSV):
        print("Nenhum histórico encontrado para rastrear.")
        return

    df = pd.read_csv(ARQUIVO_CSV)

    # Cria colunas de placar se for a primeira vez que o tracker roda
    if 'Gols_Casa' not in df.columns: df['Gols_Casa'] = 0
    if 'Gols_Visitante' not in df.columns: df['Gols_Visitante'] = 0

    # Filtra apenas os jogos de Futebol que estão "Pendentes" e que já foram "Apostados"
    # Se quiser rastrear todos (mesmo os não apostados), remova a condição df['Aposta_Realizada'] == True
    mask_pendentes = (df['Vencedor_Partida'] == 'Pendente') & (df['Liga'].str.contains('Futebol', na=False)) & (df['Aposta_Realizada'] == True)
    df_pendentes = df[mask_pendentes]

    if df_pendentes.empty:
        print("Nenhum jogo de futebol pendente/apostado para rastrear no momento.")
        return

    # Chama a API da Football-Data (Puxa todos os jogos do dia atual)
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    url_api = "https://api.football-data.org/v4/matches"
    
    try:
        resposta = requests.get(url_api, headers=headers)
        if resposta.status_code != 200:
            print(f"Erro na API Football-Data: {resposta.status_code}")
            return
            
        jogos_hoje = resposta.json().get('matches', [])
    except Exception as e:
        print(f"Erro ao conectar na API: {e}")
        return

    houve_alteracao = False

    # Percorre as nossas apostas pendentes
    for index, aposta in df_pendentes.iterrows():
        try:
            equipa_casa_nossa, equipa_fora_nossa = str(aposta['Jogo']).split(' x ')
        except:
            continue # Pula se o formato do jogo não for válido
            
        # Procura correspondência na API (Atenção: Nomes podem variar ligeiramente entre APIs)
        for jogo_api in jogos_hoje:
            casa_api = jogo_api['homeTeam']['name']
            fora_api = jogo_api['awayTeam']['name']
            
            # Lógica de "Fuzzy Match" simples para contornar diferenças de nomes (ex: "Man Utd" vs "Manchester United")
            # Se uma palavra principal do nosso CSV estiver no nome da API, ele assume que é o mesmo jogo
            palavra_chave_casa = equipa_casa_nossa.split()[0].lower()
            palavra_chave_fora = equipa_fora_nossa.split()[0].lower()
            
            if (palavra_chave_casa in casa_api.lower()) and (palavra_chave_fora in fora_api.lower()):
                
                status_atual = jogo_api['status'] # Pode ser SCHEDULED, TIMED, IN_PLAY, PAUSED, FINISHED
                
                placar_casa_api = jogo_api['score']['fullTime']['home']
                placar_fora_api = jogo_api['score']['fullTime']['away']
                
                # Previne erros se o jogo não começou e o placar for None
                if placar_casa_api is None: placar_casa_api = 0
                if placar_fora_api is None: placar_fora_api = 0
                
                placar_casa_antigo = int(aposta['Gols_Casa']) if pd.notnull(aposta['Gols_Casa']) else 0
                placar_fora_antigo = int(aposta['Gols_Visitante']) if pd.notnull(aposta['Gols_Visitante']) else 0

                # 1. ALERTA DE GOLO AO VIVO 🚨
                if status_atual in ['IN_PLAY', 'PAUSED']:
                    if placar_casa_api > placar_casa_antigo or placar_fora_api > placar_fora_antigo:
                        msg_gol = (
                            f"🚨 **GOOOOOOOOOL!** 🚨\n\n"
                            f"⚽ {equipa_casa_nossa} **{placar_casa_api}** x **{placar_fora_api}** {equipa_fora_nossa}\n"
                            f"⏱️ _Ao Vivo (Status: {status_atual})_\n"
                            f"🎯 Sua Seleção: {aposta['Seleção']}"
                        )
                        enviar_telegram(msg_gol)
                        print(f"Golo detetado: {equipa_casa_nossa} {placar_casa_api} x {placar_fora_api} {equipa_fora_nossa}")
                        
                        # Atualiza os golos na memória para não repetir o alerta
                        df.at[index, 'Gols_Casa'] = placar_casa_api
                        df.at[index, 'Gols_Visitante'] = placar_fora_api
                        houve_alteracao = True

                # 2. AUTO-RESOLUÇÃO (FIM DE JOGO) 🏁
                elif status_atual == 'FINISHED':
                    print(f"Jogo Finalizado: {aposta['Jogo']}")
                    if placar_casa_api > placar_fora_api:
                        vencedor = equipa_casa_nossa
                    elif placar_fora_api > placar_casa_api:
                        vencedor = equipa_fora_nossa
                    else:
                        vencedor = "Draw"
                    
                    df.at[index, 'Vencedor_Partida'] = vencedor
                    df.at[index, 'Data_Resolucao'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    df.at[index, 'Gols_Casa'] = placar_casa_api
                    df.at[index, 'Gols_Visitante'] = placar_fora_api
                    
                    # Mensagem de liquidação
                    msg_fim = (
                        f"🏁 **FIM DE JOGO! (AUTO-RESOLUÇÃO)** 🏁\n\n"
                        f"⚽ {equipa_casa_nossa} **{placar_casa_api}** x **{placar_fora_api}** {equipa_fora_nossa}\n"
                        f"🏆 Vencedor Resolvido: *{vencedor}*\n"
                        f"🔄 O seu painel Streamlit será atualizado automaticamente com o Green/Red!"
                    )
                    enviar_telegram(msg_fim)
                    houve_alteracao = True
                
                break # Sai do loop da API e vai para a próxima aposta

    # Se teve golo ou jogo acabou, salva o CSV
    if houve_alteracao:
        df.to_csv(ARQUIVO_CSV, index=False)
        # Se você estiver usando GitHub, pode inserir a sua função de salvar_no_github(df) aqui.
        print("✅ Base de dados de resultados atualizada com sucesso.")

if __name__ == "__main__":
    rastrear_jogos_pendentes()
