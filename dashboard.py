import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta
import pandas as pd
from thefuzz import fuzz

st.set_page_config(page_title="Fundo Quant - V9.1 (Casas Dinâmicas)", layout="wide")
st.title("⚡ Master Dashboard: Gestão Quantitativa Total")

HEADERS_BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
API_KEY = 'f926d86f5279262d9eb0afb7f304520f'

# --- PERSISTÊNCIA DE DADOS ---
if 'pin_report' not in st.session_state:
    st.session_state['pin_report'] = pd.DataFrame()

# --- CACHE 1: LIGAS DINÂMICAS POLYMARKET ---
@st.cache_data(ttl=3600)
def carregar_ligas_poly_hibrido():
    url_poly = "https://gamma-api.polymarket.com/events"
    ligas_encontradas = set()
    try:
        for offset in [0, 500, 1000]:
            res = requests.get(url_poly, headers=HEADERS_BROWSER, params={"active": "true", "closed": "false", "limit": 500, "offset": offset})
            if res.status_code == 200:
                for ev in res.json():
                    tags_dict = ev.get('tags', [])
                    if isinstance(tags_dict, list) and len(tags_dict) > 0:
                        tags_str = [str(t.get('label', '')).strip() for t in tags_dict if isinstance(t, dict)]
                        if 'Games' in tags_str and 'Sports' in tags_str:
                            for tag in tags_str:
                                if tag not in ['Games', 'Sports', 'Soccer', 'Tennis', 'Basketball', 'Esports', 'Football']:
                                    ligas_encontradas.add(tag)
    except Exception: pass
    ligas_base = ["Premier League", "Champions League", "Europa League", "Brasileirao", "Brazil Serie A", "Brazil Serie B", "Copa Libertadores", "NBA", "UFC", "ATP", "WTA"]
    return ["Todas as Ligas Ativas"] + sorted(list(set(ligas_base + list(ligas_encontradas))))

# --- CACHE 2: TODAS AS TAGS POLYMARKET ---
@st.cache_data(ttl=3600)
def carregar_todas_tags_poly():
    url_poly = "https://gamma-api.polymarket.com/events"
    todas_tags = set()
    try:
        for offset in [0, 500, 1000]:
            res = requests.get(url_poly, headers=HEADERS_BROWSER, params={"active": "true", "closed": "false", "limit": 500, "offset": offset})
            if res.status_code == 200:
                for ev in res.json():
                    tags_dict = ev.get('tags', [])
                    if isinstance(tags_dict, list) and len(tags_dict) > 0:
                        for t in tags_dict:
                            if isinstance(t, dict) and 'label' in t:
                                todas_tags.add(str(t['label']).strip())
    except Exception: pass
    
    tags_base = ["Soccer", "Tennis", "Basketball", "Esports", "Football", "Politics", "Crypto", "Pop Culture"]
    lista_final = sorted(list(set(tags_base + list(todas_tags))))
    
    tags_prioridade = [
        "TUDO (Sem Filtro)", 
        "Sports", "Games", 
        "Soccer", "Football", "Basketball", "Tennis", "Esports"
    ]
    
    for t in tags_prioridade:
        if t in lista_final:
            lista_final.remove(t)
            
    return tags_prioridade + lista_final

ligas_poly_opcoes = carregar_ligas_poly_hibrido()
tags_poly_opcoes = carregar_todas_tags_poly()

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Parâmetros do Fundo")
data_alvo = st.sidebar.text_input("Data Alvo (DD/MM):", "")
banca_rs = st.sidebar.number_input("Banca Atual (R$):", value=410.0, step=10.0)
taxa_usd = st.sidebar.number_input("Câmbio USDC/R$:", value=5.00, step=0.05)
banca_usdc = banca_rs / taxa_usd

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Filtros de Risco & IA")
target_ev = st.sidebar.slider("Alvo Mínimo de ROI (%)", 1.0, 15.0, 5.0, 0.5) / 100
target_edge = st.sidebar.slider("Edge Absoluto Exigido (%)", 0.5, 5.0, 2.5, 0.1) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("🔮 Oráculo (Pinnacle)")

lista_ligas_pin = [
    ("🌟 TODAS AS LIGAS", "all"),
    ("Futebol - Premier League", "soccer_epl"),
    ("Futebol - Brasil Série A", "soccer_brazil_campeonato"),
    ("Futebol - Brasil Série B", "soccer_brazil_serie_b"),
    ("Futebol - Libertadores", "soccer_conmebol_libertadores"),
    ("Futebol - Sul-Americana", "soccer_conmebol_sudamericana"),
    ("Futebol - Argentina Primera", "soccer_argentina_primera_division"),
    ("Futebol - Chile Primera", "soccer_chile_campeonato"),
    ("Futebol - México Liga MX", "soccer_mexico_ligamx"),
    ("Futebol - Peru Primera", "soccer_peru_liga_1"),
    ("Futebol - Uruguai Primera", "soccer_uruguay_primera_division"),
    ("Futebol - Colômbia Primera", "soccer_colombia_primera_a"),
    ("Futebol - Inglaterra Championship", "soccer_england_championship"),
    ("Futebol - Itália Serie B", "soccer_italy_serie_b"),
    ("Tênis - ATP Singles", "tennis_atp_match"),
    ("Tênis - WTA Singles", "tennis_wta_match"),
    ("Tênis - Challengers", "tennis_challenger"),
    ("E-Sports - CS:GO", "esports_csgo_match_winner"),
    ("E-Sports - LoL", "esports_lol_match_winner"),
    ("Basquete - NBA", "basketball_nba")
]

esportes_raw = st.sidebar.multiselect("Ligas Oráculo:", options=lista_ligas_pin, format_func=lambda x: x[0], default=[lista_ligas_pin[0]])
esportes_selecionados = lista_ligas_pin[1:] if any(l[1] == "all" for l in esportes_raw) else esportes_raw

# --- NOVO FILTRO: CASAS DE APOSTAS ALVO ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Casas Alvo (+EV)")

lista_casas_alvo = [
    ("Bet365", "bet365"),
    ("Betano", "betano"),
    ("1xBet", "1xbet"),
    ("Betfair (Exchange)", "betfair_ex_eu"),
    ("Betfair (Sportsbook)", "betfair_sb_uk"),
    ("Bovada", "bovada"),
    ("888sport", "sport888"),
    ("Unibet", "unibet_eu"),
    ("William Hill", "williamhill"),
    ("Matchbook", "matchbook"),
    ("Betsson", "betsson"),
    ("Coolbet", "coolbet"),
    ("DraftKings", "draftkings"),
    ("FanDuel", "fanduel"),
    ("BetMGM", "betmgm"),
    ("BetOnline.ag", "betonlineag"),
    ("MyBookie.ag", "mybookieag")
]
# Selecionadas por defeito as mais famosas do Brasil
casas_selecionadas_raw = st.sidebar.multiselect(
    "Filtrar Casas de Apostas:", 
    options=lista_casas_alvo, 
    format_func=lambda x: x[0], 
    default=[lista_casas_alvo[0], lista_casas_alvo[1], lista_casas_alvo[2], lista_casas_alvo[3]]
)
# Extraímos apenas as 'keys' das APIs para o motor
casas_alvo_keys = [casa[1] for casa in casas_selecionadas_raw]

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Blockchain (Polymarket)")

tipo_evento_poly = st.sidebar.radio("Filtro Contrato:", ["Apenas Jogos E Esportes (Tags 'Games' E 'Sports')", "Mostrar Tudo"])
ligas_poly_sel = st.sidebar.multiselect("Filtrar por Liga:", options=ligas_poly_opcoes, default=["Todas as Ligas Ativas"])
cats_poly = st.sidebar.multiselect("Filtrar por Tags:", options=tags_poly_opcoes, default=["TUDO (Sem Filtro)"])
tag_manual = st.sidebar.text_input("Tag Manual:", "")

# --- FUNÇÕES AUXILIARES POLYMARKET ---
def parse_poly_list(field):
    if isinstance(field, str):
        try: return json.loads(field)
        except: return []
    return field if isinstance(field, list) else []

def extract_clean_tags(raw_tags, fallback):
    if isinstance(raw_tags, list) and len(raw_tags) > 0 and isinstance(raw_tags[0], dict):
        return ", ".join([str(t.get('label', '')) for t in raw_tags if 'label' in t])
    return fallback

def passa_filtros_poly(ev, cats, tipo, ligas, manual):
    tags = str(ev.get('tags', [])).lower()
    slug = str(ev.get('slug', '')).lower()
    if "TUDO (Sem Filtro)" not in cats:
        if not any(c.lower() in tags or c.lower() in slug for c in cats): return False
    
    if tipo == "Apenas Jogos E Esportes (Tags 'Games' E 'Sports')":
        has_games = "games" in tags or "games" in slug
        has_sports = "sports" in tags or "sports" in slug
        if not (has_games and has_sports):
            return False
            
    passou = False
    if "Todas as Ligas Ativas" in ligas: passou = True
    elif any(l.lower() in tags or l.lower() in slug for l in ligas): passou = True
    if manual:
        if manual.lower() in tags or manual.lower() in slug: passou = True
        else: return False
    return passou

# --- FUNÇÕES DE BUSCA DE ODDS API ---
def fetch_pinnacle_data(ligas, date):
    """Função clássica usada apenas na Aba 2 e Aba 3"""
    games = []
    for nome, sport_key in ligas:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'h2h', 'bookmakers': 'pinnacle'})
            if res.status_code == 200:
                for ev in res.json():
                    dt = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    if date == "" or dt.strftime("%d/%m") == date:
                        bookie = next((b for b in ev['bookmakers'] if b['key'] == 'pinnacle'), None)
                        if bookie:
                            outcomes = bookie['markets'][0]['outcomes']
                            sum_inv = sum([1/o['price'] for o in outcomes])
                            probs = {o['name']: (1/o['price']) / sum_inv for o in outcomes}
                            odds_j = {o['name']: 1/probs[o['name']] for o in outcomes}
                            games.append({'Liga': nome, 'Home': ev['home_team'], 'Away': ev['away_team'], 'Probs': probs, 'Odds_J': odds_j, 'Data': dt.strftime("%d/%m %H:%M"), '_dt': dt})
        except: pass
    games.sort(key=lambda x: x['_dt'])
    return games

def fetch_soft_books_data(ligas, date, target_keys):
    """Motor Dinâmico: Busca Pinnacle + Casas selecionadas na Barra Lateral"""
    games = []
    
    # Junta pinnacle com as casas que o utilizador escolheu
    target_bookmakers = 'pinnacle,' + ','.join(target_keys)
    
    for nome, sport_key in ligas:
        url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
        try:
            # regions='eu,us,uk' garante que cobrimos casas globais, americanas e britânicas (como betfair)
            res = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu,us,uk', 'markets': 'h2h', 'bookmakers': target_bookmakers})
            if res.status_code == 200:
                for ev in res.json():
                    dt = datetime.strptime(ev['commence_time'], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3)
                    if date == "" or dt.strftime("%d/%m") == date:
                        
                        bookie_pin = next((b for b in ev['bookmakers'] if b['key'] == 'pinnacle'), None)
                        if not bookie_pin: continue
                        
                        outcomes_pin = bookie_pin['markets'][0]['outcomes']
                        sum_inv = sum([1/o['price'] for o in outcomes_pin])
                        probs = {o['name']: (1/o['price']) / sum_inv for o in outcomes_pin}
                        
                        softs_encontradas = {}
                        for b in ev['bookmakers']:
                            if b['key'] in target_keys:
                                # Guarda o nome oficial da casa na API (ex: "Bet365", "Betfair Exchange")
                                softs_encontradas[b['title']] = {o['name']: o['price'] for o in b['markets'][0]['outcomes']}
                        
                        if softs_encontradas:
                            games.append({
                                'Liga': nome, 
                                'Home': ev['home_team'], 
                                'Away': ev['away_team'], 
                                'Probs_Reais': probs, 
                                'Softs': softs_encontradas, 
                                'Data': dt.strftime("%d/%m %H:%M"), 
                                '_dt': dt
                            })
        except: pass
    games.sort(key=lambda x: x['_dt'])
    return games

# --- INTERFACE ---
tab1, tab2, tab3 = st.tabs(["🚀 +EV SCANNER (Soft Books)", "🔮 p implícita - Pinnacle", "🌐 RELATÓRIO POLYMARKET"])

# TAB 1: O NOVO MOTOR (PINNACLE VS SOFT BOOKS DINÂMICAS)
with tab1:
    st.markdown("### 🎯 Varredura Automática (+EV, Value Bets)")
    
    nomes_casas_display = ", ".join([c[0] for c in casas_selecionadas_raw])
    st.info(f"🔥 **Casas Monitorizadas Atualmente:** {nomes_casas_display} (Comparadas contra o Oráculo Pinnacle).")
    
    if st.button("🚀 INICIAR CAÇADA NAS SOFT BOOKS", type="primary"):
        if not esportes_selecionados: 
            st.warning("Selecione as ligas do Oráculo.")
        elif not casas_alvo_keys:
            st.warning("Selecione pelo menos uma Casa Alvo na barra lateral.")
        else:
            with st.spinner("Analisando cotações em tempo real (Pinnacle vs Mundo)..."):
                
                # Envia as chaves das casas selecionadas para a função
                jogos_analisados = fetch_soft_books_data(esportes_selecionados, data_alvo, casas_alvo_keys)
                
                if not jogos_analisados: 
                    st.warning("Nenhum jogo encontrado com cotações abertas nas casas selecionadas em simultâneo com a Pinnacle.")
                else:
                    apostas_aprovadas = []
                    
                    for jogo in jogos_analisados:
                        for nome_casa, odds_oferecidas in jogo['Softs'].items():
                            for selecao, odd_soft in odds_oferecidas.items():
                                prob_real_pin = jogo['Probs_Reais'].get(selecao)
                                
                                if prob_real_pin and prob_real_pin > 0:
                                    odd_justa = 1 / prob_real_pin
                                    roi = (prob_real_pin * odd_soft) - 1
                                    edge = prob_real_pin - (1 / odd_soft)
                                    
                                    if roi >= target_ev and edge >= target_edge:
                                        b = odd_soft - 1
                                        f_kelly = (prob_real_pin * b - (1 - prob_real_pin)) / b
                                        stake_sugerida = banca_usdc * (f_kelly * 0.25) * taxa_usd
                                        
                                        apostas_aprovadas.append({
                                            "Horário": jogo['Data'],
                                            "Liga": jogo['Liga'],
                                            "Jogo": f"{jogo['Home']} x {jogo['Away']}",
                                            "Casa de Aposta": nome_casa,
                                            "Seleção": selecao,
                                            "Odd Casa 💰": odd_soft,
                                            "Odd Justa ⚖️": odd_justa,
                                            "Edge Absoluto": edge * 100,
                                            "ROI Projetado": roi * 100,
                                            "Stake (R$)": stake_sugerida
                                        })
                    
                    if apostas_aprovadas:
                        st.success(f"🏆 {len(apostas_aprovadas)} Oportunidades +EV encontradas com precisão de 100%!")
                        df_aprovadas = pd.DataFrame(apostas_aprovadas)
                        df_aprovadas = df_aprovadas.drop_duplicates()
                        df_aprovadas = df_aprovadas.sort_values(by="ROI Projetado", ascending=False)
                        
                        st.dataframe(
                            df_aprovadas, 
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Odd Casa 💰": st.column_config.NumberColumn(format="%.2f"),
                                "Odd Justa ⚖️": st.column_config.NumberColumn(format="%.2f"),
                                "Edge Absoluto": st.column_config.NumberColumn(format="%.2f%%"),
                                "ROI Projetado": st.column_config.NumberColumn(format="%.2f%%"),
                                "Stake (R$)": st.column_config.NumberColumn(format="R$ %.2f")
                            }
                        )
                    else:
                        st.info("📊 Nenhuma Distorção encontrada nos seus critérios. O mercado está perfeitamente ajustado no momento.")

# TAB 2: p implícita - Pinnacle
with tab2:
    st.markdown("### 🔮 p implícita - Pinnacle (Calculadora de Valor)")
    if st.button("Obter Oráculo", type="primary", key="btn_auditoria"):
        pin_games = fetch_pinnacle_data(esportes_selecionados, data_alvo)
        if pin_games:
            rel = []
            for g in pin_games:
                for sel, prob in g['Probs'].items():
                    odd_min = max((1 + target_ev)/prob, 1/(prob - target_edge) if prob > target_edge else 99)
                    rel.append({"Data": g['Data'], "Jogo": f"{g['Home']} x {g['Away']}", "Seleção": sel, "Prob Real": prob * 100, "Odd Mínima": round(odd_min, 2), "Sua Odd ✏️": None, "_p": prob, "_om": odd_min})
            st.session_state['pin_report'] = pd.DataFrame(rel)

    if not st.session_state['pin_report'].empty:
        editado = st.data_editor(
            st.session_state['pin_report'], 
            column_config={
                "Sua Odd ✏️": st.column_config.NumberColumn(format="%.2f"),
                "Prob Real": st.column_config.NumberColumn(format="%.1f%%"),
                "_p": None, 
                "_om": None
            }, 
            use_container_width=True, 
            hide_index=True
        )
        calc = editado[editado['Sua Odd ✏️'].notna()].copy()
        if not calc.empty:
            calc['ROI %'] = ((calc['_p'] * calc['Sua Odd ✏️']) - 1) * 100
            calc['Status'] = calc.apply(lambda r: "✅ OPORTUNIDADE" if r['Sua Odd ✏️'] >= r['_om'] else "❌ Sem Valor", axis=1)
            st.dataframe(
                calc[['Data', 'Jogo', 'Seleção', 'Odd Mínima', 'Sua Odd ✏️', 'ROI %', 'Status']], 
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ROI %": st.column_config.NumberColumn(format="%.2f%%")
                }
            )

# TAB 3: RELATÓRIO POLYMARKET
with tab3:
    st.markdown("### 🌐 Escavadeira de Contratos Web3")
    
    modo_raio_x = st.checkbox("🔮 Modo Raio-X: Mostrar contratos ignorando a lista da Pinnacle", value=True)
    
    col1, col2 = st.columns(2)
    with col1:
        termo_busca = st.text_input("Filtrar por nome exato do jogo:", "", disabled=not modo_raio_x)
    with col2:
        paginas = st.slider("Profundidade (Páginas de 500 eventos)", 2, 40, 10)
        
    if st.button("Buscar no Polymarket", key="btn_poly"):
        with st.spinner(f"Lendo {paginas * 500} contratos na blockchain..."):
            
            times_alvo = []
            if not modo_raio_x and not termo_busca and esportes_selecionados:
                pin_filtro = fetch_pinnacle_data(esportes_selecionados, data_alvo)
                for g in pin_filtro:
                    times_alvo.append(g['Home'])
                    times_alvo.append(g['Away'])

            rel_poly = []
            pb_poly = st.progress(0)
            
            for offset in range(0, paginas * 500, 500):
                pb_poly.progress(min((offset + 500) / (paginas * 500), 1.0))
                try:
                    res = requests.get("https://gamma-api.polymarket.com/events", headers=HEADERS_BROWSER, params={"active":"true","closed":"false","limit":500,"offset":offset})
                    if res.status_code != 200: break
                    
                    for ev in res.json():
                        titulo = ev.get('title', '')
                        if not titulo: continue
                        
                        if not passa_filtros_poly(ev, cats_poly, tipo_evento_poly, ligas_poly_sel, tag_manual):
                            continue
                            
                        manter_evento = False
                        if modo_raio_x:
                            manter_evento = True
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
                        
                        outs = parse_poly_list(mercados[0].get('outcomes', []))
                        asks = parse_poly_list(mercados[0].get('bestAsks', []))
                        if not asks: asks = parse_poly_list(mercados[0].get('outcomePrices', []))
                        
                        if len(outs) > 0 and len(outs) == len(asks):
                            for i, o in enumerate(outs):
                                try:
                                    preco = float(asks[i])
                                except:
                                    preco = 0.0
                                    
                                if 0.01 < preco < 0.99:
                                    rel_poly.append({
                                        "Jogo / Mercado": titulo, 
                                        "Opção": o, 
                                        "Preço": preco, 
                                        "Tags": extract_clean_tags(ev.get('tags'), ev.get('slug'))
                                    })
                except Exception: break
            
            pb_poly.empty()
            if rel_poly: 
                st.dataframe(
                    pd.DataFrame(rel_poly), 
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Preço": st.column_config.NumberColumn(format="$ %.3f")
                    }
                )
            else:
                st.info("Nenhuma correspondência no Polymarket. Tente aumentar a profundidade ou diminuir os filtros.")
