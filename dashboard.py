import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta

# Configuração da página e Título
st.set_page_config(page_title="Fundo Quant - Arbitragem", layout="wide")
st.title("⚡ Painel de Arbitragem Institucional (Web3 + Oráculo)")

# --- CONFIGURAÇÕES GLOBAIS (BARRA LATERAL) ---
st.sidebar.header("⚙️ Configurações Globais")
data_alvo = st.sidebar.text_input("Data Alvo (DD/MM):", "04/03")

st.sidebar.markdown("---")
st.sidebar.subheader("🔮 Configuração do Oráculo")
API_KEY = 'f926d86f5279262d9eb0afb7f304520f'
esporte_pinnacle = st.sidebar.selectbox(
    "Liga na Pinnacle:",
    [
        ("Futebol - Premier League", "soccer_epl"),
        ("Futebol - Champions League", "soccer_uefa_champions_league"),
        ("Basquete - NBA", "basketball_nba"),
        ("Tênis - ATP Singles", "tennis_atp_match")
    ],
    format_func=lambda x: x[0]
)[1]

# --- ABAS DA INTERFACE ---
tab1, tab2 = st.tabs(["🌐 Polymarket (Execução Web3)", "🔮 Pinnacle (Oráculo de Probabilidade)"])

# ==========================================
# ABA 1: POLYMARKET (Varejo / Execução)
# ==========================================
with tab1:
    st.markdown("### 🌐 Livro de Ofertas: Polymarket (H2H)")
    st.info("Varre a blockchain em busca de liquidez e calcula o Spread invisível.")
    
    if st.button("🔍 Escavar Polymarket"):
        with st.spinner(f"Escavando a blockchain por jogos no dia {data_alvo}..."):
            url = "https://gamma-api.polymarket.com/events"
            limit = 500
            offset = 0
            dados_poly = []

            while offset < 5000:
                params = {"active": "true", "closed": "false", "limit": limit, "offset": offset}
                try:
                    response = requests.get(url, params=params)
                    if response.status_code != 200: break
                    eventos = response.json()
                    if not eventos: break

                    for evento in eventos:
                        titulo = evento.get('title', '')
                        if " vs " not in titulo.lower() and " vs. " not in titulo.lower(): continue

                        data_raw = evento.get('endDate') or evento.get('startDate', '')
                        if not data_raw: continue

                        try:
                            dt_utc = datetime.strptime(data_raw[:19], "%Y-%m-%dT%H:%M:%S")
                            dt_local = dt_utc - timedelta(hours=3)
                            if dt_local.strftime("%d/%m") != data_alvo: continue
                            hora_str = dt_local.strftime("%H:%M")
                        except: continue

                        mercados = evento.get('markets', [])
                        if not mercados: continue
                        mercado = mercados[0]
                        
                        try:
                            outcomes = json.loads(mercado.get('outcomes', '[]'))
                            prices = json.loads(mercado.get('outcomePrices', '[]'))
                            bids = mercado.get('bestBids', [])
                            asks = mercado.get('bestAsks', [])
                            if isinstance(bids, str): bids = json.loads(bids)
                            if isinstance(asks, str): asks = json.loads(asks)
                        except: continue
                        
                        if len(outcomes) == len(prices):
                            for i in range(len(outcomes)):
                                try:
                                    bid = float(bids[i]) if i < len(bids) and bids[i] else float(prices[i])
                                    ask = float(asks[i]) if i < len(asks) and asks[i] else float(prices[i])
                                    spread = ask - bid if (ask - bid) > 0 else 0.0
                                    
                                    if 0.001 < ask < 0.999:
                                        status = "🟢 Líquido" if spread <= 0.03 else "🔴 Tóxico"
                                        dados_poly.append({
                                            "Hora": hora_str,
                                            "Jogo": titulo[:45],
                                            "Opção": str(outcomes[i])[:15],
                                            "ASK (Pagar $)": round(ask, 3),
                                            "BID (Vender $)": round(bid, 3),
                                            "Spread": f"{spread*100:.1f}%",
                                            "Status": status
                                        })
                                except: pass
                    offset += limit
                    time.sleep(0.3)
                except Exception as e:
                    st.error(f"Erro: {e}")
                    break

            if dados_poly:
                st.success(f"{len(dados_poly)} cotações encontradas.")
                st.dataframe(dados_poly, use_container_width=True, hide_index=True)
            else:
                st.warning(f"Nenhum jogo encontrado no Polymarket para {data_alvo}.")


# ==========================================
# ABA 2: PINNACLE (Oráculo / Verdade Absoluta)
# ==========================================
with tab2:
    st.markdown("### 🔮 Verdade Absoluta: Pinnacle (Fair Odds)")
    st.info("Remove a margem de lucro da casa (Juice) para revelar a probabilidade matemática real.")
    
    if st.button("📊 Extrair Oráculo"):
        with st.spinner(f"Conectando com a API da Pinnacle via The Odds API..."):
            url_pin = f'https://api.the-odds-api.com/v4/sports/{esporte_pinnacle}/odds/'
            params_pin = {
                'apiKey': API_KEY,
                'regions': 'eu',
                'markets': 'h2h',
                'bookmakers': 'pinnacle'
            }
            
            try:
                response = requests.get(url_pin, params=params_pin)
                dados_pin = []
                
                if response.status_code == 200:
                    data = response.json()
                    for event in data:
                        # Tratamento de Data/Hora
                        dt_utc = datetime.strptime(event['commence_time'], "%Y-%m-%dT%H:%M:%SZ")
                        dt_local = dt_utc - timedelta(hours=3)
                        data_str = dt_local.strftime("%d/%m")
                        hora_str = dt_local.strftime("%H:%M")
                        
                        # Só processa se for a data alvo
                        if data_str == data_alvo:
                            home = event['home_team']
                            away = event['away_team']
                            
                            bookie = next((b for b in event['bookmakers'] if b['key'] == 'pinnacle'), None)
                            if not bookie: continue
                            
                            outcomes = bookie['markets'][0]['outcomes']
                            inv_odds = [1/o['price'] for o in outcomes]
                            sum_inv = sum(inv_odds)
                            
                            for outcome in outcomes:
                                p_real = (1/outcome['price']) / sum_inv
                                fair_odd = 1 / p_real
                                
                                dados_pin.append({
                                    "Hora": hora_str,
                                    "Jogo": f"{home} x {away}",
                                    "Seleção": outcome['name'],
                                    "Odd Suja (C/ Vig)": round(outcome['price'], 2),
                                    "Fair Odd": round(fair_odd, 2),
                                    "Probabilidade Real (%)": f"{p_real*100:.2f}%"
                                })
                    
                    if dados_pin:
                        st.success(f"Oráculo processou {len(dados_pin)} linhas perfeitas.")
                        st.dataframe(dados_pin, use_container_width=True, hide_index=True)
                    else:
                        st.warning(f"Sem jogos dessa liga na Pinnacle para {data_alvo}.")
                else:
                    st.error(f"Erro na API da Pinnacle. (A liga pode estar sem liquidez).")
            except Exception as e:
                st.error(f"Falha de Conexão: {e}")
