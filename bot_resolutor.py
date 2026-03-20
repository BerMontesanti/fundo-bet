import os
import requests
import pandas as pd
import json
from datetime import datetime
from github import Github

# ==========================================
# ⚙️ CONFIGURAÇÕES DA CONTA
# ==========================================
API_KEY = os.environ.get('ODDS_API_KEY')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_NAME = os.environ.get('REPO_NAME')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

ARQUIVO_CSV = 'historico_apostas.csv'
ARQUIVO_LIGAS = 'ligas_config.json'

def enviar_telegram(mensagem):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"})

def carregar_mapeamento_ligas():
    # Tenta ler o JSON para saber qual o "sport_key" da API com base no Nome da Liga
    if os.path.exists(ARQUIVO_LIGAS):
        try:
            with open(ARQUIVO_LIGAS, 'r') as f:
                config = json.load(f)
                disponiveis = config.get("disponiveis", {})
                # Inverte o dicionário: {Nome_da_Liga: sport_key}
                return {nome: chave for chave, nome in disponiveis.items()}
        except: pass
    return {}

def resolver_apostas():
    if not os.path.exists(ARQUIVO_CSV):
        print("CSV não encontrado.")
        return

    df = pd.read_csv(ARQUIVO_CSV)
    
    # Pega apenas as apostas que estão pendentes
    pendentes = df[df['Vencedor_Partida'].isin(['Pendente', 'nan', ''])]
    if pendentes.empty:
        print("💤 Nenhuma aposta pendente para auditar.")
        return

    mapa_ligas = carregar_mapeamento_ligas()
    
    # Descobre quais esportes (sport_keys) precisamos consultar hoje
    ligas_para_consultar = pendentes['Liga'].unique()
    chaves_para_consultar = set()
    
    for liga in ligas_para_consultar:
        chave = mapa_ligas.get(liga)
        if chave: chaves_para_consultar.add(chave)

    print(f"🔍 Auditando {len(pendentes)} apostas pendentes em {len(chaves_para_consultar)} esportes...")
    jogos_resolvidos = 0

    # Consulta a API para cada esporte pendente (daysFrom=3 pega os jogos dos últimos 3 dias)
    for sport_key in chaves_para_consultar:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores/'
        try:
            res = requests.get(url, params={'apiKey': API_KEY, 'daysFrom': 3})
            if res.status_code == 200:
                for match in res.json():
                    # Só processa jogos que já acabaram
                    if match.get('completed', False) and match.get('scores'):
                        home = match['home_team']
                        away = match['away_team']
                        nome_jogo = f"{home} x {away}"
                        
                        # Extrai os placares
                        score_home = next((int(s['score']) for s in match['scores'] if s['name'] == home), 0)
                        score_away = next((int(s['score']) for s in match['scores'] if s['name'] == away), 0)
                        
                        if score_home > score_away: vencedor = home
                        elif score_away > score_home: vencedor = away
                        else: vencedor = "Draw"

                        # Procura no CSV se temos esse jogo pendente
                        mask = (df['Jogo'] == nome_jogo) & (df['Vencedor_Partida'].isin(['Pendente', 'nan', '']))
                        if df[mask].shape[0] > 0:
                            df.loc[mask, 'Vencedor_Partida'] = vencedor
                            df.loc[mask, 'Data_Resolucao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            jogos_resolvidos += df[mask].shape[0]
                            print(f"✅ Jogo Resolvido: {nome_jogo} -> {vencedor}")
        except Exception as e:
            print(f"❌ Erro ao buscar resultados de {sport_key}: {e}")

    # Se resolveu alguma coisa, salva no GitHub
    if jogos_resolvidos > 0:
        df.to_csv(ARQUIVO_CSV, index=False)
        
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(REPO_NAME)
            contents = repo.get_contents(ARQUIVO_CSV)
            novo_csv = df.to_csv(index=False)
            repo.update_file(contents.path, f"🤖 [Auditor] {jogos_resolvidos} apostas resolvidas automaticamente", novo_csv, contents.sha)
            print("💾 Salvo no GitHub com sucesso!")
            enviar_telegram(f"⚖️ *Auditoria Concluída:*\nO Robô Juiz corrigiu o placar de {jogos_resolvidos} apostas que estavam pendentes! Acesse o painel para ver os novos lucros.")
        except Exception as e:
            print(f"❌ Erro ao salvar no GitHub: {e}")
    else:
        print("💤 Os jogos pendentes ainda não terminaram ou não foram encontrados.")

if __name__ == "__main__":
    resolver_apostas()
