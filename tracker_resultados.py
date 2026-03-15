import os
import requests
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
FOOTBALL_DATA_TOKEN = os.environ.get('FOOTBALL_DATA_TOKEN')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
ARQUIVO_CSV = 'historico_apostas.csv'

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"})

# ==========================================
# 🏁 MOTOR DE AUTO-RESOLUÇÃO (2x ao dia)
# ==========================================
def resolver_apostas_pendentes():
    if not os.path.exists(ARQUIVO_CSV):
        print("Nenhum histórico encontrado para rastrear.")
        return

    df = pd.read_csv(ARQUIVO_CSV)

    # Filtra apenas os jogos de Futebol que estão "Pendentes" e que foram "Apostados"
    mask_pendentes = (df['Vencedor_Partida'] == 'Pendente') & (df['Liga'].str.contains('Futebol', na=False)) & (df['Aposta_Realizada'] == True)
    df_pendentes = df[mask_pendentes]

    if df_pendentes.empty:
        print("Nenhum jogo de futebol pendente para ser resolvido hoje.")
        return

    # Para garantir que pegamos jogos da madrugada, buscamos os jogos de ontem e de hoje
    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)
    
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    url_api = f"https://api.football-data.org/v4/matches?dateFrom={ontem}&dateTo={hoje}"
    
    try:
        resposta = requests.get(url_api, headers=headers)
        if resposta.status_code != 200:
            print(f"Erro na API Football-Data: {resposta.status_code}")
            return
            
        jogos_api = resposta.json().get('matches', [])
    except Exception as e:
        print(f"Erro ao conectar na API: {e}")
        return

    apostas_resolvidas_agora = 0
    mensagem_resumo = "🏁 **RESUMO DE AUTO-RESOLUÇÃO** 🏁\n\n"

    for index, aposta in df_pendentes.iterrows():
        try:
            equipa_casa_nossa, equipa_fora_nossa = str(aposta['Jogo']).split(' x ')
        except:
            continue
            
        for jogo_api in jogos_api:
            casa_api = jogo_api['homeTeam']['name']
            fora_api = jogo_api['awayTeam']['name']
            
            palavra_chave_casa = equipa_casa_nossa.split()[0].lower()
            palavra_chave_fora = equipa_fora_nossa.split()[0].lower()
            
            if (palavra_chave_casa in casa_api.lower()) and (palavra_chave_fora in fora_api.lower()):
                
                status_atual = jogo_api['status']
                
                # SÓ NOS INTERESSA SE O JOGO JÁ ESTIVER TERMINADO
                if status_atual == 'FINISHED':
                    placar_casa = jogo_api['score']['fullTime']['home']
                    placar_fora = jogo_api['score']['fullTime']['away']
                    
                    if placar_casa > placar_fora:
                        vencedor = equipa_casa_nossa
                    elif placar_fora > placar_casa:
                        vencedor = equipa_fora_nossa
                    else:
                        vencedor = "Draw"
                    
                    # Atualiza o CSV
                    df.at[index, 'Vencedor_Partida'] = vencedor
                    df.at[index, 'Data_Resolucao'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Define Green ou Red com base na seleção
                    selecao = str(aposta['Seleção']).strip()
                    status_final = "Green ✅" if selecao == vencedor else "Red ❌"
                    df.at[index, 'Status_Aposta'] = status_final
                    
                    mensagem_resumo += f"⚽ {equipa_casa_nossa} {placar_casa}x{placar_fora} {equipa_fora_nossa}\n"
                    mensagem_resumo += f"🎯 Aposta: {selecao} ➡️ **{status_final}**\n\n"
                    
                    apostas_resolvidas_agora += 1
                
                break # Sai do loop da API e vai para a próxima aposta

    # Se alguma aposta foi liquidada, salva o CSV e envia o resumo
    if apostas_resolvidas_agora > 0:
        df.to_csv(ARQUIVO_CSV, index=False)
        mensagem_resumo += f"📊 O seu Dashboard foi atualizado com estes resultados!"
        enviar_telegram(mensagem_resumo)
        print(f"✅ {apostas_resolvidas_agora} apostas liquidadas e guardadas no CSV.")
    else:
        print("Nenhum jogo dos que apostamos terminou ainda.")

if __name__ == "__main__":
    resolver_apostas_pendentes()
