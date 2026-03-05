import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta
import pandas as pd
from thefuzz import fuzz

st.set_page_config(page_title="Fundo Quant - V8.2 (Full Data)", layout="wide")
st.title("⚡ Master Dashboard: Gestão Quantitativa Total")

HEADERS_BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
API_KEY = 'f926d86f5279262d9eb0afb7f304520f'

# --- PERSISTÊNCIA DE DADOS ---
if 'pin_report' not in st.session_state:
    st.session_state['pin_report'] = pd.DataFrame()

# --- CACHE DE LIGAS DINÂMICAS ---
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
                        if 'Games' in tags_str:
                            for tag in tags_str:
                                if tag not in ['Games', 'Sports', 'Soccer', 'Tennis', 'Basketball', 'Esports', 'Football']:
                                    ligas_encontradas.add(tag)
    except Exception: pass
    ligas_base = ["Premier League", "Champions League", "Europa League", "Brasileirao", "Brazil Serie A", "Brazil Serie B", "Copa Libertadores", "NBA", "UFC", "ATP", "WTA"]
    return ["Todas as Ligas Ativas"] + sorted(list(set(ligas_base + list(ligas_encontradas))))

ligas_poly_opcoes = carregar_ligas_poly_hibrido()

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
fuzzy_limit = st.sidebar.slider("Tolerância Match (DNA %)", 50, 100, 75, 5)

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
esportes_raw = st.sidebar.multiselect("Ligas Oráculo:", options=lista_ligas_pin, format_func=lambda x: x[0], default=[lista_ligas_pin[1]])
esportes_selecionados = lista_ligas_pin[1:] if any(l[1] == "all" for l in esportes_raw) else esportes_raw

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Blockchain (Polymarket)")
tipo_evento_poly = st.sidebar.radio("Filtro Contrato:", ["Apenas Jogos (Tag 'Games')", "Mostrar Tudo"])
ligas_poly_sel = st.sidebar.multiselect("Filtrar por Liga:", options=ligas_poly_opcoes, default=["Todas as Ligas Ativas"])
tag_manual = st.sidebar.text_input("Tag Manual:", "")
cats_poly = st.sidebar.multiselect("Categorias:", options=["TUDO (Sem Filtro)", "Sports", "Soccer", "Tennis", "Basketball", "Esports"], default=["TUDO (Sem Filtro)"])

# --- FUNÇÕES AUXILIARES ---
def parse_poly_list(field):
    if isinstance(field, str):
        try: return json.loads(field)
        except: return []
    return field if isinstance(field, list) else []

def extract_clean_tags(raw_tags, fallback):
    if isinstance(raw_tags, list) and len(raw_tags) > 0 and isinstance(raw_tags[0], dict):
        return ", ".join([str(t.get('label', '')) for t in raw_tags if 'label' in t])
    return fallback

def fetch_pinnacle_data(ligas, date):
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

def passa_filtros_poly(ev, cats, tipo, ligas, manual):
    tags = str(ev.get('tags', [])).lower()
    slug = str(ev.get('slug', '')).lower()
    if "TUDO (Sem Filtro)" not in cats:
        if not any(c.lower() in tags or c.lower() in slug for c in cats): return False
    if tipo == "Apenas Jogos (Tag 'Games')" and "games" not in tags and "games" not in slug: return False
    passou = False
    if "Todas as Ligas Ativas" in ligas: passou = True
    elif any(l.lower() in tags or l.lower() in slug for l in ligas): passou = True
    if manual:
        if manual.lower() in tags or manual.lower() in slug: passou = True
        else: return False
    return passou

# --- INTERFACE ---
tab1, tab2, tab3 = st.tabs(["🚀 MOTOR DE FUSÃO", "🔮 p implícita - Pinnacle", "🌐 RELATÓRIO POLYMARKET"])

# TAB 1: MOTOR DE FUSÃO
with tab1:
    st.markdown("### 🎯 Fusão Oráculo + Blockchain (H2H Strict)")
    if st.button("🔥 INICIAR VARREDURA CRUZADA", type="primary"):
        pin_games = fetch_pinnacle_data(esportes_selecionados, data_alvo)
        if not pin_games: st.warning("Sem dados Pinnacle.")
        else:
            with st.spinner("Escavando Polymarket..."):
                url = "https://gamma-api.polymarket.com/events"
                offset, aprovadas = 0, []
                pb = st.progress(0)
                while offset < 15000:
                    pb.progress(min(offset/15000, 1.0))
                    try:
                        res = requests.get(url, headers=HEADERS_BROWSER, params={"active":"true","closed":"false","limit":500,"offset":offset})
                        if res.status_code != 200: break
                        for ev in res.json():
                            title = ev.get('title', '')
                            if not title or not passa_filtros_poly(ev, cats_poly, tipo_evento_poly, ligas_poly_sel, tag_manual): continue
                            
                            match = None
                            for pin in pin_games:
                                score_h = fuzz.partial_ratio(pin['Home'].lower(), title.lower())
                                score_a = fuzz.partial_ratio(pin['Away'].lower(), title.lower())
                                if score_h >= fuzzy_limit and score_a >= fuzzy_limit:
                                    match = pin; break
                            if not match: continue
                            
                            mks = ev.get('markets', [])
                            if not mks: continue
                            outs = parse_poly_list(mks[0].get('outcomes', []))
                            asks = parse_poly_list(mks[0].get('bestAsks', []))
                            if not asks: asks = parse_poly_list(mks[0].get('outcomePrices', []))
                            
                            if len(outs) == len(asks) and len(outs) > 0:
                                for i, out_n in enumerate(outs):
                                    ask = float(asks[i])
                                    prob_p = 0
                                    if out_n in ["Yes", "No"]:
                                        if out_n == "Yes": prob_p = match['Probs'].get(match['Home'], 0)
                                        else: prob_p = match['Probs'].get(match['Away'], 0) + match['Probs'].get('Draw', 0)
                                    else:
                                        if fuzz.partial_ratio(out_n.lower(), match['Home'].lower()) > 75: prob_p = match['Probs'].get(match['Home'], 0)
                                        elif fuzz.partial_ratio(out_n.lower(), match['Away'].lower()) > 75: prob_p = match['Probs'].get(match['Away'], 0)
                                    
                                    if 0.01 < ask < 0.99 and prob_p > 0:
                                        edge = prob_p - ask
                                        roi = (prob_p / ask) - 1
                                        if roi >= target_ev and edge >= target_edge:
                                            b = (1-ask)/ask
                                            fk = (prob_p * b - (1-prob_p))/b
                                            
                                            aprovadas.append({
                                                "Horário": match['Data'], 
                                                "Jogo Pinnacle": f"{match['Home']} x {match['Away']}",
                                                "Contrato Poly": title, 
                                                "Seleção": out_n, 
                                                "Prob. Pin": prob_p * 100,
                                                "Prob. Poly": ask * 100, 
                                                "Edge": edge * 100, 
                                                "ROI": roi * 100,
                                                "Stake": banca_usdc * fk * 0.25 * taxa_usd
                                            })
                        offset += 500
                    except: break
                pb.empty()
                if aprovadas: 
                    st.dataframe(
                        pd.DataFrame(aprovadas), 
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Prob. Pin": st.column_config.NumberColumn(format="%.1f%%"),
                            "Prob. Poly": st.column_config.NumberColumn(format="%.1f%%"),
                            "Edge": st.column_config.NumberColumn(format="%.2f%%"),
                            "ROI": st.column_config.NumberColumn(format="%.2f%%"),
                            "Stake": st.column_config.NumberColumn(format="R$ %.2f")
                        }
                    )
                else: st.info("Nenhuma oportunidade H2H encontrada.")

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
    paginas = st.slider("Profundidade (Páginas)", 2, 40, 10)
    if st.button("Buscar no Polymarket", key="btn_poly"):
        with st.spinner("Lendo Blockchain..."):
            rel_poly = []
            for offset in range(0, paginas * 500, 500):
                res = requests.get("https://gamma-api.polymarket.com/events", headers=HEADERS_BROWSER, params={"active":"true","closed":"false","limit":500,"offset":offset})
                if res.status_code == 200:
                    for ev in res.json():
                        if passa_filtros_poly(ev, cats_poly, tipo_evento_poly, ligas_poly_sel, tag_manual):
                            outs = parse_poly_list(ev.get('markets',[{}])[0].get('outcomes',[]))
                            asks = parse_poly_list(ev.get('markets',[{}])[0].get('bestAsks',[]))
                            for i, o in enumerate(outs):
                                if i < len(asks): rel_poly.append({"Jogo": ev.get('title'), "Opção": o, "Preço": float(asks[i]), "Tags": extract_clean_tags(ev.get('tags'), ev.get('slug'))})
            if rel_poly: 
                st.dataframe(
                    pd.DataFrame(rel_poly), 
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Preço": st.column_config.NumberColumn(format="$ %.3f")
                    }
                )
