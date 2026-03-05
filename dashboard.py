import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta
import pandas as pd
from thefuzz import fuzz

st.set_page_config(page_title="Fundo Quant - V7.8 (Terminal Trading)", layout="wide")
st.title("⚡ Master Dashboard: Terminal de Auditoria Quantitativa")

HEADERS_BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
API_KEY = 'f926d86f5279262d9eb0afb7f304520f'

if 'pin_report' not in st.session_state:
    st.session_state['pin_report'] = pd.DataFrame()

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
                        tags_str = [t for t in tags_str if t]
                        if 'Games' in tags_str:
                            for tag in tags_str:
                                if tag not in ['Games', 'Sports', 'Soccer', 'Tennis', 'Basketball', 'Esports', 'Football']:
                                    ligas_encontradas.add(tag)
    except Exception: pass
    ligas_base = ["Premier League", "Champions League", "Europa League", "Brasileirao", "Brazil Serie A", "Brazil Serie B", "Copa Libertadores", "Copa Sudamericana", "NBA", "UFC"]
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
    ("Futebol - Premier League", "soccer_epl"), ("Futebol - Brasil Série A", "soccer_brazil_campeonato"),
    ("Futebol - Brasil Série B", "soccer_brazil_serie_b"), ("Futebol - Libertadores", "soccer_conmebol_libertadores"),
    ("Tênis - ATP Singles", "tennis_atp_match"), ("Basquete - NBA", "basketball_nba")
]
esportes_selecionados_raw = st.sidebar.multiselect("Ligas (Oráculo):", options=lista_ligas_pin, format_func=lambda x: x[0], default=[lista_ligas_pin[1]])
esportes_selecionados = lista_ligas_pin[1:] if any(l[1] == "all" for l in esportes_selecionados_raw) else esportes_selecionados_raw

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Blockchain (Polymarket)")
tipo_evento_poly = st.sidebar.radio("Filtro de Contrato:", ["Apenas Jogos (Tag 'Games')", "Mostrar Tudo"])
ligas_poly = st.sidebar.multiselect("Filtrar por Liga:", options=ligas_poly_opcoes, default=["Todas as Ligas Ativas"])

def parse_poly_list(data_field):
    if isinstance(data_field, str):
        try: return json.loads(data_field)
        except: return []
    return data_field if isinstance(data_field, list) else []

tab1, tab2, tab3 = st.tabs(["🚀 MOTOR DE FUSÃO", "🔮 Auditoria Universal", "🌐 Blockchain (Polymarket)"])

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
                        games.append({'Liga': nome_liga, 'Home': event['home_team'], 'Away': event['away_team'], 'Probs_Reais': probs, 'Data_Local': dt_local.strftime("%d/%m %H:%M"), '_dt': dt_local})
        except Exception: pass
    games.sort(key=lambda x: x['_dt'])
    return games

# ================= ABA 2 (AUDITORIA UNIVERSAL COM LIMITES) =================
with tab2:
    st.markdown("### 🔮 Oráculo: Limites de Valor & Auditoria")
    
    if st.button("Obter Oráculo", type="primary"):
        with st.spinner("Buscando Projecções..."):
            pin_games = fetch_pinnacle_data(esportes_selecionados, data_alvo)
            if pin_games:
                rel = []
                for g in pin_games:
                    for selecao, prob in g['Probs_Reais'].items():
                        # CÁLCULO DA ODD MÍNIMA:
                        # Para ROI: Odd_min = (1 + target_roi) / prob
                        # Para Edge: Odd_min = 1 / (prob - target_edge)
                        odd_min_roi = (1 + target_ev) / prob
                        odd_min_edge = 1 / (prob - target_edge) if (prob - target_edge) > 0 else 999
                        odd_de_corte = max(odd_min_roi, odd_min_edge)
                        
                        rel.append({
                            "Data/Hora": g['Data_Local'],
                            "Jogo": f"{g['Home']} x {g['Away']}",
                            "Seleção": selecao,
                            "Prob Real": f"{prob*100:.1f}%",
                            "💰 Odd Mínima (Valor)": round(odd_de_corte, 2),
                            "Odd Manual ✏️": None,
                            "_prob_raw": prob,
                            "_odd_min_raw": odd_de_corte
                        })
                st.session_state['pin_report'] = pd.DataFrame(rel)

    if not st.session_state['pin_report'].empty:
        st.info(f"💡 **Como ler:** Se você encontrar uma odd **MAIOR** que a 'Odd Mínima', a aposta tem valor matemático positivo.")
        
        df_editado = st.data_editor(
            st.session_state['pin_report'],
            column_config={
                "Odd Manual ✏️": st.column_config.NumberColumn("Sua Odd ✏️", min_value=1.01, step=0.01, format="%.2f"),
                "_prob_raw": None, "_odd_min_raw": None
            },
            disabled=["Data/Hora", "Jogo", "Seleção", "Prob Real", "💰 Odd Mínima (Valor)"],
            use_container_width=True, hide_index=True
        )
        
        # LÓGICA DA TABELA DE OPORTUNIDADES
        df_calculado = df_editado[df_editado['Odd Manual ✏️'].notna()].copy()
        if not df_calculado.empty:
            st.markdown("### 🧮 Auditoria de Oportunidades")
            
            # Cálculos de Validação
            df_calculado['ROI %'] = ((df_calculado['_prob_raw'] * df_calculado['Odd Manual ✏️']) - 1) * 100
            df_calculado['Edge %'] = (df_calculado['_prob_raw'] - (1 / df_calculado['Odd Manual ✏️'])) * 100
            
            def check_opportunity(row):
                if row['Odd Manual ✏️'] >= row['_odd_min_raw']:
                    return "✅ 🔥 OPORTUNIDADE"
                return "❌ Sem Valor"
            
            df_calculado['Status'] = df_calculado.apply(check_opportunity, axis=1)
            
            # Exibição Final
            df_final = df_calculado[['Data/Hora', 'Jogo', 'Seleção', '💰 Odd Mínima (Valor)', 'Odd Manual ✏️', 'Edge %', 'ROI %', 'Status']]
            
            st.dataframe(
                df_final.style.apply(lambda x: ['background-color: #004d00' if v == "✅ 🔥 OPORTUNIDADE" else '' for v in x], axis=1, subset=['Status'])
                .format({"Edge %": "{:.2f}%", "ROI %": "{:.2f}%"}),
                use_container_width=True, hide_index=True
            )

# ================= ABA 1 (Motor de Fusão - Mantido) =================
with tab1:
    st.markdown("### 🚀 Motor de Fusão (Pinnacle + Polymarket)")
    # ... (Código da Aba 1 conforme Versão 7.5, adaptado para usar o novo motor de Auditoria se necessário)
    st.write("Execute a varredura para cruzar dados automaticamente com a Web3.")

# ================= ABA 3 (Polymarket - Mantido) =================
with tab3:
    st.markdown("### 🌐 Blockchain: Livro de Ofertas Polymarket")
    # ... (Código da Aba 3 conforme Versão 7.5)
