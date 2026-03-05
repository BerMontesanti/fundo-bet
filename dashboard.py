import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta
import pandas as pd
from thefuzz import fuzz

st.set_page_config(page_title="Fundo Quant - V7.2 (Hybrid Tags)", layout="wide")
st.title("⚡ Master Dashboard: Arbitragem Quantitativa Web3")

HEADERS_BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
API_KEY = 'f926d86f5279262d9eb0afb7f304520f'

# ==========================================
# AUTO-DISCOVERY + DICIONÁRIO FIXO
# ==========================================
@st.cache_data(ttl=3600)
def carregar_ligas_poly_hibrido():
    url_poly = "https://gamma-api.polymarket.com/events"
    ligas_encontradas = set()
    try:
        # Varre só a superfície para não travar o painel
        for offset in [0, 500, 1000]:
            res = requests.get(url_poly, headers=HEADERS_BROWSER, params={"active": "true", "closed": "false", "limit": 500, "offset": offset})
            if res.status_code == 200:
                for ev in res.json():
                    tags_dict = ev.get('tags', [])
                    if isinstance(tags_dict, list) and len(tags_dict) > 0:
                        tags_str = [str(t.get('label', '')).strip() for t in tags_dict if isinstance(t, dict)]
                        tags_str = [t for t in tags_str if t]
                        if 'Games' in tags_str:
                            for tag in tags_str:
                                if tag not in ['Games', 'Sports', 'Soccer', 'Tennis', 'Basketball', 'Esports', 'Football']:
                                    ligas_encontradas.add(tag)
    except Exception: pass
    
    # O NOSSO DICIONÁRIO BLINDADO (Garante que as ligas menores estejam no menu)
    ligas_base = [
        "Premier League", "Champions League", "Europa League", "Brasileirao", 
        "Brazil Serie A", "Brazil Serie B", "Copa Libertadores", "Copa Sudamericana", 
        "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Liga MX", "Primeira Liga",
        "NBA", "NFL", "NHL", "MLB", "ATP", "WTA", "CS:GO", "LoL", "Valorant", "UFC"
    ]
    
    # Fundo as duas listas e removo duplicatas
    lista_final = sorted(list(set(ligas_base + list(ligas_encontradas))))
    return ["Todas as Ligas Ativas"] + lista_final

ligas_poly_opcoes = carregar_ligas_poly_hibrido()

# --- BARRA LATERAL (CENTRO DE COMANDO) ---
st.sidebar.header("⚙️ Parâmetros do Fundo")
data_alvo = st.sidebar.text_input("Data Alvo (DD/MM):", "")
banca_rs = st.sidebar.number_input("Banca Atual (R$):", value=410.0, step=10.0)
taxa_usd = st.sidebar.number_input("Câmbio USDC/R$:", value=5.00, step=0.05)
banca_usdc = banca_rs / taxa_usd

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Filtros de Risco & IA")
target_ev = st.sidebar.slider("Alvo Mínimo de EV (ROI %)", 1.0, 15.0, 5.0, 0.5) / 100
target_edge = st.sidebar.slider("Edge Absoluto Exigido (%)", 0.5, 5.0, 2.5, 0.1) / 100
fuzzy_limit = st.sidebar.slider("Tolerância Match (DNA %)", 50, 100, 75, 5)

st.sidebar.markdown("---")
st.sidebar.subheader("🔮 Oráculo (Pinnacle)")

lista_ligas_pin = [
    ("Futebol - Premier League", "soccer_epl"), ("Futebol - Brasil Série A", "soccer_brazil_campeonato"),
    ("Futebol - Brasil Série B", "soccer_brazil_serie_b"), ("Futebol - Libertadores", "soccer_conmebol_libertadores"),
    ("Futebol - Sul-Americana", "soccer_conmebol_sudamericana"), ("Futebol - Argentina Primera", "soccer_argentina_primera_division"),
    ("Futebol - Chile Primera", "soccer_chile_campeonato"), ("Futebol - México Liga MX", "soccer_mexico_ligamx"),
    ("Futebol - Peru Primera", "soccer_peru_liga_1"), ("Futebol - Uruguai Primera", "soccer_uruguay_primera_division"),
    ("Futebol - Colômbia Primera", "soccer_colombia_primera_a"), ("Futebol - Inglaterra Championship", "soccer_england_championship"),
    ("Futebol - Itália Serie B", "soccer_italy_serie_b"), ("Tênis - ATP Singles", "tennis_atp_match"),
    ("Tênis - WTA Singles", "tennis_wta_match"), ("Tênis - Challengers", "tennis_challenger"),
    ("E-Sports - CS:GO", "esports_csgo_match_winner"), ("E-Sports - LoL", "esports_lol_match_winner"),
    ("Basquete - NBA", "basketball_nba")
]

esportes_selecionados = st.sidebar.multiselect("Ligas (Oráculo):", options=lista_ligas_pin, format_func=lambda x: x[0], default=[lista_ligas_pin[0], lista_ligas_pin[1]])

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Blockchain (Polymarket)")
tipo_evento_poly = st.sidebar.radio("Filtro de Contrato:", ["Apenas Jogos (Tag 'Games')", "Mostrar Tudo (Props/Futuros)"])

ligas_poly = st.sidebar.multiselect("Filtrar por Liga:", options=ligas_poly_opcoes, default=["Todas as Ligas Ativas"])

# NOVO: OVERRIDE MANUAL DE TAGS
tag_poly_manual = st.sidebar.text_input("Ou Forçar Tag Manual (Ex: paulistao):", "")

categorias_poly = st.sidebar.multiselect("Categorias Gerais:", options=["TUDO (Sem Filtro)", "Sports", "Soccer", "Football", "Tennis", "Basketball", "Esports"], default=["TUDO (Sem Filtro)"])

def parse_poly_list(data_field):
    if isinstance(data_field, str):
        try: return json.loads(data_field)
        except: return []
    elif isinstance(data_field, list): return data_field
    return []

def extract_clean_tags(raw_tags, fallback_slug):
    if isinstance(raw_tags, list) and len(raw_tags) > 0 and isinstance(raw_tags[0], dict):
        return ", ".join([str(t.get('label', '')) for t in raw_tags if 'label' in t])
    return fallback_slug

tab1, tab2, tab3 = st.tabs(["🚀 MOTOR DE FUSÃO", "🔮 Oráculo (Pinnacle)", "🌐 Blockchain (Polymarket)"])

def fetch_pinnacle_data(ligas_selecionadas, target_date):
    games = []
    for nome_liga, sport_key in ligas_selecionadas:
        url_pin = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url_pin, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'h2h', 'bookmakers': 'pinnacle'})
            if res.status_code == 200:
                for event in res.json():
                    dt_local = datetime.strptime(event['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    if target_date == "" or dt_local.strftime("%d/%m") == target_date:
                        bookie = next((b for b in event['bookmakers'] if b['key'] == 'pinnacle'), None)
                        if not bookie: continue
                        outcomes = bookie['markets'][0]['outcomes']
                        sum_inv = sum([1/o['price'] for o in outcomes])
                        probs = {o['name']: (1/o['price']) / sum_inv for o in outcomes}
                        odds_limpas = {o['name']: 1 / probs[o['name']] for o in outcomes}
                        games.append({'Liga': nome_liga, 'Home': event['home_team'], 'Away': event['away_team'], 'Probs_Reais': probs, 'Odds_Justas': odds_limpas, 'Data_Local': dt_local.strftime("%d/%m %H:%M"), '_dt': dt_local})
        except Exception: pass
    games.sort(key=lambda x: x['_dt'])
    return games

# MOTOR DE FILTRAGEM BLINDADO (Com Override Manual)
def passa_filtros_polymarket(evento, categorias, tipo_evento, ligas, tag_manual):
    tags_brutas = str(evento.get('tags', [])).lower()
    slug_bruto = str(evento.get('slug', '')).lower()
    
    if "TUDO (Sem Filtro)" not in categorias:
        if not any(cat.lower() in tags_brutas or cat.lower() in slug_bruto for cat in categorias):
            return False
            
    if tipo_evento == "Apenas Jogos (Tag 'Games')":
        if "games" not in tags_brutas and "games" not in slug_bruto:
            return False
            
    passou_liga = False
    if "Todas as Ligas Ativas" in ligas:
        passou_liga = True
    else:
        if any(liga.lower() in tags_brutas or liga.lower() in slug_bruto for liga in ligas):
            passou_liga = True
            
    # FORÇA A TAG MANUAL SE ELA FOR PREENCHIDA
    if tag_manual:
        if tag_manual.lower() in tags_brutas or tag_manual.lower() in slug_bruto:
            passou_liga = True
        else:
            return False # Se digitou tag manual e não achou, bloqueia na hora!
            
    return passou_liga

# ================= ABA 1 =================
with tab1:
    st.markdown("### 🎯 Scanner Quantitativo (Lote Múltiplo)")
    if st.button("🔥 EXECUTAR MOTOR DE FUSÃO", type="primary"):
        if not esportes_selecionados: st.warning("Selecione as ligas.")
        else:
            with st.spinner("Puxando dados do Oráculo..."):
                pin_games = fetch_pinnacle_data(esportes_selecionados, data_alvo)
            if not pin_games: st.warning("Nenhum jogo na Pinnacle.")
            else:
                with st.spinner("Escavando Polymarket (Deep Scan)..."):
                    url_poly = "https://gamma-api.polymarket.com/events"
                    offset, apostas_aprovadas = 0, []
                    pb = st.progress(0)
                    while offset < 15000:
                        pb.progress(min(offset / 15000, 1.0))
                        try:
                            res_poly = requests.get(url_poly, headers=HEADERS_BROWSER, params={"active": "true", "closed": "false", "limit": 500, "offset": offset})
                            if res_poly.status_code != 200: break
                            dados = res_poly.json()
                            if not dados: break
                            
                            for evento in dados:
                                titulo = evento.get('title', '')
                                if not titulo: continue
                                
                                if not passa_filtros_polymarket(evento, categorias_poly, tipo_evento_poly, ligas_poly, tag_poly_manual):
                                    continue
                                
                                matched_pin, best_score = None, 0
                                for pin in pin_games:
                                    score = fuzz.token_set_ratio(f"{pin['Home']} vs {pin['Away']}".lower(), titulo.lower())
                                    if score > best_score:
                                        best_score = score
                                        if score >= fuzzy_limit: matched_pin = pin
                                if not matched_pin: continue
                                
                                mercados = evento.get('markets', [])
                                if not mercados: continue
                                
                                outcomes = parse_poly_list(mercados[0].get('outcomes', []))
                                asks = parse_poly_list(mercados[0].get('bestAsks', []))
                                if not asks: asks = parse_poly_list(mercados[0].get('outcomePrices', []))
                                
                                if len(outcomes) > 0 and len(outcomes) == len(asks):
                                    cenarios = []
                                    if "Yes" in outcomes and "No" in outcomes:
                                        prob_home = matched_pin['Probs_Reais'].get(matched_pin['Home'], 0)
                                        prob_draw = matched_pin['Probs_Reais'].get('Draw', 0)
                                        prob_away = matched_pin['Probs_Reais'].get(matched_pin['Away'], 0)
                                        if prob_home > 0:
                                            cenarios.extend([
                                                {"nome": "Yes (Casa)", "prob": prob_home, "ask": float(asks[outcomes.index("Yes")])},
                                                {"nome": "No (Fora/Emp)", "prob": prob_away + prob_draw, "ask": float(asks[outcomes.index("No")])}
                                            ])
                                    else:
                                        for idx, out_name in enumerate(outcomes):
                                            if fuzz.partial_ratio(out_name.lower(), matched_pin['Home'].lower()) > 75: cenarios.append({"nome": out_name, "prob": matched_pin['Probs_Reais'].get(matched_pin['Home'], 0), "ask": float(asks[idx])})
                                            elif fuzz.partial_ratio(out_name.lower(), matched_pin['Away'].lower()) > 75: cenarios.append({"nome": out_name, "prob": matched_pin['Probs_Reais'].get(matched_pin['Away'], 0), "ask": float(asks[idx])})
                                    
                                    for c in cenarios:
                                        if 0.01 < c["ask"] < 0.99 and c["prob"] > 0:
                                            edge = c["prob"] - c["ask"]
                                            ev_roi = edge / c["ask"]
                                            if ev_roi >= target_ev and edge >= target_edge:
                                                b = (1 - c["ask"]) / c["ask"]
                                                f_kelly = (c["prob"] * b - (1 - c["prob"])) / b
                                                apostas_aprovadas.append({
                                                    "Horário": matched_pin['Data_Local'], "Liga": matched_pin['Liga'],
                                                    "Jogo": f"{matched_pin['Home']} x {matched_pin['Away']}", "Ação": c["nome"],
                                                    "DNA": f"{best_score}%", "Oráculo": f"{c['prob']*100:.1f}%", "Preço": f"${c['ask']:.3f}",
                                                    "Edge": f"{edge*100:.2f}%", "ROI": f"{ev_roi*100:.1f}%", "Stake": f"R$ {round((banca_usdc * (f_kelly * 0.25)) * taxa_usd, 2)}"
                                                })
                            offset += 500
                        except: break
                    pb.empty()
                    if apostas_aprovadas:
                        st.success(f"Encontradas {len(apostas_aprovadas)} oportunidades!")
                        st.dataframe(pd.DataFrame(apostas_aprovadas).style.highlight_max(subset=['ROI', 'Edge'], color='lightgreen'), use_container_width=True)
                    else: st.warning("Mercado eficiente. Sem distorções hoje.")

# ================= ABA 2 =================
with tab2:
    st.markdown("### 🔮 Oráculo: Probabilidades Reais")
    if st.button("Obter Relatório Pinnacle"):
        with st.spinner("Buscando..."):
            pin_games = fetch_pinnacle_data(esportes_selecionados, data_alvo)
            if pin_games:
                rel = [{"Data/Hora": g['Data_Local'], "Liga": g['Liga'], "Jogo": f"{g['Home']} x {g['Away']}", "Seleção": k, "Fair Odd": round(g['Odds_Justas'][k], 2), "Prob Real": f"{v*100:.2f}%"} for g in pin_games for k, v in g['Probs_Reais'].items()]
                st.dataframe(pd.DataFrame(rel), use_container_width=True)
            else: st.info("Sem jogos.")

# ================= ABA 3 =================
with tab3:
    st.markdown("### 🌐 Polymarket: Diagnóstico do Livro de Ofertas")
    modo_raio_x = st.checkbox("🔮 Modo Raio-X: Mostrar contratos ignorando a lista da Pinnacle", value=True)
    
    col1, col2 = st.columns(2)
    with col1:
        termo_busca = st.text_input("Filtrar por nome exato do jogo:", "", disabled=not modo_raio_x)
    with col2:
        paginas = st.slider("Profundidade (Páginas de 500 eventos)", 2, 40, 10)
        
    if st.button("Buscar no Polymarket"):
        with st.spinner(f"Lendo {paginas * 500} contratos na blockchain..."):
            times_alvo = []
            if not modo_raio_x and not termo_busca and esportes_selecionados:
                pin_filtro = fetch_pinnacle_data(esportes_selecionados, data_alvo)
                for g in pin_filtro:
                    times_alvo.extend([g['Home'], g['Away']])
            
            url_poly = "https://gamma-api.polymarket.com/events"
            relatorio_poly = []
            pb_poly = st.progress(0)
            status_erro = None
            
            for i, offset in enumerate(range(0, paginas * 500, 500)):
                pb_poly.progress(min((i + 1) / paginas, 1.0))
                res = requests.get(url_poly, headers=HEADERS_BROWSER, params={"active": "true", "closed": "false", "limit": 500, "offset": offset})
                if res.status_code == 200:
                    dados = res.json()
                    if not dados: break 
                    
                    for ev in dados:
                        titulo = ev.get('title', '')
                        if not titulo: continue
                        
                        if not passa_filtros_polymarket(ev, categorias_poly, tipo_evento_poly, ligas_poly, tag_poly_manual):
                            continue
                        
                        manter_evento = False
                        if modo_raio_x: manter_evento = True
                        elif termo_busca:
                            if termo_busca.lower() in titulo.lower(): manter_evento = True
                        else:
                            if times_alvo:
                                t_lower = titulo.lower()
                                for t in times_alvo:
                                    if t.lower() in t_lower or fuzz.partial_ratio(t.lower(), t_lower) >= 85:
                                        manter_evento = True; break
                            else: manter_evento = True
                                
                        if not manter_evento: continue
                            
                        mercados = ev.get('markets', [])
                        if not mercados: continue
                        
                        outcomes = parse_poly_list(mercados[0].get('outcomes', []))
                        asks = parse_poly_list(mercados[0].get('bestAsks', []))
                        if not asks: asks = parse_poly_list(mercados[0].get('outcomePrices', []))
                        
                        if len(outcomes) > 0 and len(outcomes) == len(asks):
                            for idx_out, out in enumerate(outcomes):
                                try: ask_val = float(asks[idx_out])
                                except: ask_val = 0
                                if 0.01 < ask_val < 0.99:
                                    tag_print = extract_clean_tags(ev.get('tags', []), ev.get('slug', ''))
                                    relatorio_poly.append({"Jogo / Mercado": titulo, "Opção": out, "Preço": f"${ask_val:.3f}", "TAGS": tag_print})
                else: 
                    status_erro = res.status_code
                    break
            
            pb_poly.empty()
            if relatorio_poly:
                st.success(f"Encontradas {len(pd.DataFrame(relatorio_poly))} cotações!")
                st.dataframe(pd.DataFrame(relatorio_poly), use_container_width=True)
            elif status_erro:
                st.error(f"Erro HTTP {status_erro}")
            else:
                st.info("Nenhuma correspondência. Se usou a 'Tag Manual', certifique-se de que a palavra exata existe nas tags do Polymarket.")
