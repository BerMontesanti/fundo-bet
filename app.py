import streamlit as st
import pandas as pd
import os
from github import Github
from datetime import datetime
import plotly.express as px

# ==========================================
# CONFIGURAÇÃO E LOGIN
# ==========================================
st.set_page_config(page_title="Dashboard Quant Bet", page_icon="📈", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acesso Restrito - Quant Bet EV")
    senha = st.text_input("Senha:", type="password")
    if st.button("Entrar"):
        if senha == st.secrets["SENHA_SITE"]:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("❌ Senha incorreta!")
    st.stop() 

st.title("📈 Dashboard Analítico - Quant Bet EV")

ARQUIVO = 'historico_apostas.csv'

if not os.path.exists(ARQUIVO):
    st.warning("Nenhum histórico encontrado ainda.")
    st.stop()

df = pd.read_csv(ARQUIVO)

colunas_padrao = {
    'Vencedor_Partida': 'Pendente',
    'Status_Aposta': 'Pendente',
    'Aposta_Realizada': False,
    'Odd_Real': 0.0,
    'Stake_Real': 0.0,
    'Data_Resolucao': "",
    'Achado_em': ""
}
for col, val in colunas_padrao.items():
    if col not in df.columns:
        df[col] = val

# ==========================================
# AUTO-CURA DA BASE DE DADOS (CORREÇÃO DE NaNs)
# ==========================================
df['Vencedor_Partida'] = df['Vencedor_Partida'].apply(lambda x: "Pendente" if str(x).strip().lower() in ["nan", "", "none"] else x)

def auto_corrigir_status(row):
    venc = str(row['Vencedor_Partida']).strip()
    sel = str(row['Seleção']).strip()
    if venc == "Pendente":
        return "Pendente"
    elif sel == venc:
        return "Green ✅"
    else:
        return "Red ❌"

df['Status_Aposta'] = df.apply(auto_corrigir_status, axis=1)

def salvar_no_github(dataframe, mensagem):
    dataframe.to_csv(ARQUIVO, index=False)
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["REPO_NAME"])
        contents = repo.get_contents(ARQUIVO)
        novo_csv = dataframe.to_csv(index=False)
        repo.update_file(contents.path, mensagem, novo_csv, contents.sha)
        st.success(f"✅ {mensagem} com sucesso na Nuvem!")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao sincronizar: {e}")
        return False

# ==========================================
# PREPARAÇÃO MATEMÁTICA GLOBAL
# ==========================================
df_calc = df.copy()
df_calc = df_calc.drop_duplicates(subset=['Data/Hora', 'Jogo', 'Casa', 'Seleção'], keep='last')

def classificar_momento(row):
    try:
        str_achado = str(row.get('Achado_em', ''))
        str_jogo = str(row.get('Data/Hora', ''))
        
        if str_achado.lower() in ['nan', 'nat', '', 'none']:
            return "Pré-live"
            
        dt_achado = datetime.strptime(str_achado, "%d/%m/%Y %H:%M:%S")
        ano = dt_achado.year
        dt_jogo = datetime.strptime(f"{str_jogo}/{ano}", "%d/%m %H:%M/%Y")
        
        if dt_achado < dt_jogo:
            return "Pré-live"
        else:
            return "Ao Vivo"
    except:
        return "Pré-live"

df_calc['Momento_Alerta'] = df_calc.apply(classificar_momento, axis=1)
df_calc['Esporte'] = df_calc['Liga'].apply(lambda x: str(x).split(' - ')[0].strip() if ' - ' in str(x) else 'Outro')

df_calc['Stake_Num'] = df_calc['Stake'].astype(str).str.replace('R$', '', regex=False).str.strip().astype(float)
df_calc['ROI_Num'] = df_calc['ROI'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Edge_Num'] = df_calc['Edge'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Odd_Num'] = df_calc['Odd Casa'].astype(float)

df_calc['Stake_Final'] = df_calc.apply(lambda x: x['Stake_Real'] if (x['Aposta_Realizada'] and pd.notnull(x['Stake_Real']) and float(x['Stake_Real']) > 0) else x['Stake_Num'], axis=1)
df_calc['Odd_Final'] = df_calc.apply(lambda x: x['Odd_Real'] if (x['Aposta_Realizada'] and pd.notnull(x['Odd_Real']) and float(x['Odd_Real']) > 0) else x['Odd_Num'], axis=1)

df_calc['EV_Esperado_R$'] = df_calc['Stake_Final'] * df_calc['ROI_Num']

def calc_payout_global(row):
    if row['Status_Aposta'] == 'Green ✅':
        return row['Stake_Final'] * (row['Odd_Final'] - 1)
    elif row['Status_Aposta'] == 'Red ❌':
        return -row['Stake_Final']
    return 0.0

df_calc['Payout'] = df_calc.apply(calc_payout_global, axis=1)

def calc_roi_realizado(row):
    if row['Status_Aposta'] in ['Green ✅', 'Red ❌'] and row['Stake_Final'] > 0:
        return row['Payout'] / row['Stake_Final']
    return 0.0

df_calc['ROI_Realizado'] = df_calc.apply(calc_roi_realizado, axis=1)

# Criação das Abas (Agora com a Calculadora EV!)
tab_dash, tab_calc, tab_apostas, tab_resultados, tab_hist, tab_estudos = st.tabs([
    "📊 Dashboard", "🧮 Calculadora EV", "🎯 Minhas Apostas", "📝 Alimentar Resultados", "🗄️ Histórico", "🔬 Estudos Estatísticos"
])

# ==========================================
# ABA 1: DASHBOARD
# ==========================================
with tab_dash:
    st.markdown("### 🎛️ Filtros de Análise")
    filtro_visao = st.radio("Filtro de Oportunidades:", ["Geral", "Apenas Apostadas", "Não Apostadas"], horizontal=True)
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        casas_disponiveis = ["Todas as Casas"] + sorted(df_calc['Casa'].dropna().unique().tolist())
        casa_selecionada = st.selectbox("Casa de Aposta:", casas_disponiveis, key="filtro_dash_casa")
    with col_f2:
        esportes_disp = ["Todos os Esportes"] + sorted(df_calc['Esporte'].dropna().unique().tolist())
        esporte_selecionado = st.selectbox("Esporte:", esportes_disp, key="filtro_dash_esporte")
    with col_f3:
        if esporte_selecionado != "Todos os Esportes":
            ligas_disp = ["Todas as Ligas"] + sorted(df_calc[df_calc['Esporte'] == esporte_selecionado]['Liga'].dropna().unique().tolist())
        else:
            ligas_disp = ["Todas as Ligas"] + sorted(df_calc['Liga'].dropna().unique().tolist())
        liga_selecionada = st.selectbox("Liga:", ligas_disp, key="filtro_dash_liga")
    with col_f4:
        tipos_disp = ["Todos os Momentos", "Pré-live", "Ao Vivo"]
        tipo_selecionado = st.selectbox("Momento do Alerta:", tipos_disp, key="filtro_dash_tipo")

    df_dash = df_calc.copy()
    
    if filtro_visao == "Apenas Apostadas": df_dash = df_dash[df_dash['Aposta_Realizada'] == True]
    elif filtro_visao == "Não Apostadas": df_dash = df_dash[df_dash['Aposta_Realizada'] == False]
        
    if casa_selecionada != "Todas as Casas": df_dash = df_dash[df_dash['Casa'] == casa_selecionada]
    if esporte_selecionado != "Todos os Esportes": df_dash = df_dash[df_dash['Esporte'] == esporte_selecionado]
    if liga_selecionada != "Todas as Ligas": df_dash = df_dash[df_dash['Liga'] == liga_selecionada]
    if tipo_selecionado != "Todos os Momentos": df_dash = df_dash[df_dash['Momento_Alerta'] == tipo_selecionado]

    df_resolvidas = df_dash[df_dash['Status_Aposta'].isin(['Green ✅', 'Red ❌'])].copy()

    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    col5, col6, col7, col8 = st.columns(4)
    
    col1.metric("Apostas Resolvidas", f"{len(df_resolvidas)}")
    taxa_acerto_global = (len(df_resolvidas[df_resolvidas['Status_Aposta'] == 'Green ✅']) / len(df_resolvidas) * 100) if not df_resolvidas.empty else 0.0
    col2.metric("Taxa de Acerto", f"{taxa_acerto_global:.1f}%")
    col3.metric("Edge Médio", f"{(df_resolvidas['Edge_Num'].mean() * 100):.2f}%" if not df_resolvidas.empty else "0%")
    stake_total_global = df_resolvidas['Stake_Final'].sum()
    col4.metric("Stake Total", f"R$ {stake_total_global:.2f}")
    
    ev_total_global = df_resolvidas['EV_Esperado_R$'].sum()
    col5.metric("EV Esperado", f"R$ {ev_total_global:.2f}")
    
    payout_total_global = df_resolvidas['Payout'].sum()
    col6.metric("Payout", f"R$ {payout_total_global:.2f}", delta=f"R$ {payout_total_global:.2f}")
    
    payout_ev_ratio = (payout_total_global / ev_total_global * 100) if ev_total_global != 0 else 0.0
    col7.metric("EV Realization Rate", f"{payout_ev_ratio:.1f}%")
    
    yield_global = (payout_total_global / stake_total_global * 100) if stake_total_global > 0 else 0.0
    col8.metric("Yield Global", f"{yield_global:.2f}%")

    if not df_resolvidas.empty:
        df_resolvidas['Data_Curta'] = df_resolvidas['Data/Hora'].str[:5] 
        grafico_dados = df_resolvidas.groupby('Data_Curta').agg(
            Payout_Diario=('Payout', 'sum'),
            Stake_Diaria=('Stake_Final', 'sum')
        ).reset_index()
        
        grafico_dados['Payout Acumulado'] = grafico_dados['Payout_Diario'].cumsum()
        grafico_dados['Stake Acumulada'] = grafico_dados['Stake_Diaria'].cumsum()
        grafico_dados['Yield Acumulado (%)'] = (grafico_dados['Payout Acumulado'] / grafico_dados['Stake Acumulada']) * 100
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown(f"### 📈 Evolução Financeira (R$)")
            fig_fin = px.line(
                grafico_dados, x='Data_Curta', y=['Stake Acumulada', 'Payout Acumulado'], 
                markers=True, labels={'value': 'Valor (R$)', 'variable': 'Métrica', 'Data_Curta': 'Data'}
            )
            fig_fin.for_each_trace(lambda t: t.update(name={'Stake Acumulada': 'Stake Total', 'Payout Acumulado': 'Payout'}.get(t.name, t.name)))
            st.plotly_chart(fig_fin, use_container_width=True)

        with col_g2:
            st.markdown(f"### 🚀 Evolução do Yield (%)")
            fig_yield = px.line(
                grafico_dados, x='Data_Curta', y='Yield Acumulado (%)', 
                markers=True, labels={'Yield Acumulado (%)': 'Yield (%)', 'Data_Curta': 'Data'}
            )
            fig_yield.update_traces(line_color="#00CC96" if yield_global >= 0 else "#EF553B")
            st.plotly_chart(fig_yield, use_container_width=True)

    st.divider()

    st.markdown("### 📊 Performance Detalhada (Agrupamento)")
    
    agrupamento = st.radio("Ver performance separada por:", ["Casa de Aposta", "Esporte", "Liga", "Momento_Alerta"], horizontal=True)
    col_grupo = "Casa" if agrupamento == "Casa de Aposta" else agrupamento

    analise_tabela = df_resolvidas.groupby(col_grupo).agg(
        Oportunidades=(col_grupo, 'count'),
        Greens=('Status_Aposta', lambda x: (x == 'Green ✅').sum()),
        Edge_Medio=('Edge_Num', 'mean'),
        EV_Medio=('ROI_Num', 'mean'),
        Stake_Total=('Stake_Final', 'sum'),
        EV_Esperado=('EV_Esperado_R$', 'sum'),
        Payout=('Payout', 'sum')
    ).reset_index()
    
    analise_tabela['Yield'] = analise_tabela.apply(lambda x: (x['Payout'] / x['Stake_Total'] * 100) if x['Stake_Total'] > 0 else 0.0, axis=1)
    analise_tabela['Taxa_Acerto'] = analise_tabela.apply(lambda x: (x['Greens'] / x['Oportunidades'] * 100) if x['Oportunidades'] > 0 else 0.0, axis=1)
    analise_tabela['EV Realization Rate'] = analise_tabela.apply(lambda x: (x['Payout'] / x['EV_Esperado'] * 100) if x['EV_Esperado'] != 0 else 0.0, axis=1)
    
    analise_tabela = analise_tabela.sort_values(by=['Yield', 'Oportunidades'], ascending=[False, False])

    tabela_exibicao = analise_tabela.copy()
    tabela_exibicao['Taxa_Acerto'] = tabela_exibicao['Taxa_Acerto'].apply(lambda x: f"{x:.1f}%")
    tabela_exibicao['Edge_Medio'] = (tabela_exibicao['Edge_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    tabela_exibicao['EV_Medio'] = (tabela_exibicao['EV_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    tabela_exibicao['Yield'] = tabela_exibicao['Yield'].apply(lambda x: f"{x:.2f}%")
    tabela_exibicao['EV Realization Rate'] = tabela_exibicao['EV Realization Rate'].apply(lambda x: f"{x:.1f}%")
    tabela_exibicao['Stake_Total'] = tabela_exibicao['Stake_Total'].apply(lambda x: f"R$ {x:.2f}")
    tabela_exibicao['EV_Esperado'] = tabela_exibicao['EV_Esperado'].apply(lambda x: f"R$ {x:.2f}")
    tabela_exibicao['Payout'] = tabela_exibicao['Payout'].apply(lambda x: f"R$ {x:.2f}")
    
    cols_ordem = [col_grupo, 'Oportunidades', 'Taxa_Acerto', 'Edge_Medio', 'EV_Medio', 'Stake_Total', 'EV_Esperado', 'Payout', 'EV Realization Rate', 'Yield']
    st.dataframe(tabela_exibicao[cols_ordem], hide_index=True, use_container_width=True)


# ==========================================
# ABA 2: CALCULADORA EV (NOVA!)
# ==========================================
with tab_calc:
    st.markdown("### 🧮 Calculadora Rápida de EV (Expected Value)")
    st.write("Introduza as odds para descobrir se há valor matemático na aposta e qual a stake ideal.")

    col_calc_1, col_calc_2 = st.columns(2)
    
    with col_calc_1:
        st.markdown("#### 1. Odd da Casa de Apostas (Soft)")
        odd_casa_input = st.number_input("Odd que você quer apostar (ex: BetMGM):", min_value=1.01, value=2.10, step=0.05, format="%.2f")
        banca_input = st.number_input("Banca Total (R$):", min_value=10.0, value=250.0, step=10.0)

    with col_calc_2:
        st.markdown("#### 2. Odds da Pinnacle (Sharp)")
        odd_pin_sel = st.number_input("Odd Pinnacle para a sua seleção:", min_value=1.01, value=1.95, step=0.05, format="%.2f")
        odd_pin_opp = st.number_input("Odd Pinnacle para o oponente (Lay/Dupla Chance):", min_value=1.01, value=1.85, step=0.05, format="%.2f")
        st.caption("*(Dica: Num mercado 1X2, some a probabilidade do Empate e do Visitante e converta para Odd, ou use um mercado Asiático 2-way)*")

    st.divider()

    # Matemática de Remoção de Margem (De-vigging) e Cálculo EV
    if odd_pin_sel > 1.0 and odd_pin_opp > 1.0 and odd_casa_input > 1.0:
        # Probabilidades Implícitas (com juice)
        imp_sel = 1 / odd_pin_sel
        imp_opp = 1 / odd_pin_opp
        margem_total = imp_sel + imp_opp
        
        # Probabilidade Real (sem juice)
        prob_real = imp_sel / margem_total
        odd_justa = 1 / prob_real
        
        # Cálculo de EV e Edge
        roi_calc = (prob_real * odd_casa_input) - 1
        edge_calc = prob_real - (1 / odd_casa_input)
        
        # Critério de Kelly Fracionado (25%)
        b_kelly = odd_casa_input - 1
        f_kelly = (prob_real * b_kelly - (1 - prob_real)) / b_kelly
        
        # Stake (Não permite stake negativa)
        if f_kelly > 0:
            stake_calc = banca_input * (f_kelly * 0.25)
        else:
            stake_calc = 0.0

        st.markdown("### 🎯 Resultados da Análise")
        
        res_c1, res_c2, res_c3, res_c4 = st.columns(4)
        res_c1.metric("Probabilidade Real", f"{(prob_real * 100):.1f}%")
        res_c2.metric("Odd Justa (Fair Odd)", f"{odd_justa:.2f}")
        
        if edge_calc > 0:
            res_c3.metric("Edge (Vantagem)", f"{(edge_calc * 100):.2f}%", "Aposta de Valor +EV")
            res_c4.metric("Stake Recomendada", f"R$ {stake_calc:.2f}", f"ROI Esperado: {(roi_calc * 100):.1f}%")
            st.success("✅ **SINAL VERDE!** A casa está a oferecer um prémio superior ao risco real. O modelo recomenda apostar.")
        else:
            res_c3.metric("Edge (Vantagem)", f"{(edge_calc * 100):.2f}%", "-EV (Não Apostar)")
            res_c4.metric("Stake Recomendada", "R$ 0.00", "Aposta com Prejuízo Matemático")
            st.error("❌ **SINAL VERMELHO!** A odd da casa não compensa o risco. A longo prazo, esta aposta vai drenar a sua banca.")


# ==========================================
# ABA 3: MINHAS APOSTAS
# ==========================================
with tab_apostas:
    st.info("💡 **Dica:** Marque as oportunidades que apostou. Insira a Odd e Stake finais para maior precisão.")
    df_pendentes_aposta = df[df['Status_Aposta'] == 'Pendente'].copy()
    if df_pendentes_aposta.empty:
        st.success("Nenhuma aposta pendente!")
    else:
        colunas_edicao = ['Data/Hora', 'Jogo', 'Casa', 'Seleção', 'Aposta_Realizada', 'Odd_Real', 'Stake_Real']
        editado = st.data_editor(
            df_pendentes_aposta[colunas_edicao],
            column_config={
                "Aposta_Realizada": st.column_config.CheckboxColumn("Foi Apostada?", default=False),
                "Odd_Real": st.column_config.NumberColumn("Odd Real Pega", format="%.2f"),
                "Stake_Real": st.column_config.NumberColumn("Stake Colocada (R$)", format="%.2f"),
            },
            disabled=["Data/Hora", "Jogo", "Casa", "Seleção"],
            hide_index=True, use_container_width=True, key="editor_apostas"
        )
        if st.button("💾 Salvar Registros de Apostas", type="primary"):
            with st.spinner('A enviar...'):
                df.update(editado[['Aposta_Realizada', 'Odd_Real', 'Stake_Real']])
                if salvar_no_github(df, "🤖 Atualizando apostas realizadas"):
                    st.rerun()

# ==========================================
# ABA 4: RESULTADOS
# ==========================================
with tab_resultados:
    st.info("Apenas jogos pendentes ou finalizados nas últimas 24h são exibidos aqui.")
    def eh_recente(d_str):
        if pd.isna(d_str) or d_str == "": return False
        try:
            dt = datetime.strptime(str(d_str), "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - dt).total_seconds() < 86400 
        except: return False

    df['Recente'] = df['Data_Resolucao'].apply(eh_recente)
    mostrar_antigos = st.checkbox("Forçar exibição de jogos antigos")
    
    mask_exibicao = (df['Vencedor_Partida'] == 'Pendente') | (df['Recente'] == True)
    if mostrar_antigos: df_mostrar = df.copy()
    else: df_mostrar = df[mask_exibicao].copy()

    jogos_unicos = df_mostrar[['Data/Hora', 'Liga', 'Jogo', 'Vencedor_Partida']].drop_duplicates(subset=['Data/Hora', 'Jogo']).copy()
    jogos_unicos['Ordem'] = jogos_unicos['Vencedor_Partida'].apply(lambda x: 0 if x == 'Pendente' else 1)
    jogos_unicos = jogos_unicos.sort_values(by=['Ordem', 'Data/Hora'], ascending=[True, False])

    with st.form("form_resultados"):
        novos_resultados = []
        for index, row in jogos_unicos.iterrows():
            opcoes = ["Pendente", "Draw"]
            if ' x ' in row['Jogo']:
                c, f = row['Jogo'].split(' x ')
                opcoes = ["Pendente", c, f, "Draw"]
                
            valor_atual = str(row['Vencedor_Partida']).strip()
            if valor_atual not in opcoes: opcoes.append(valor_atual)
            idx_padrao = opcoes.index(valor_atual) if valor_atual in opcoes else 0
            
            col_txt, col_sel = st.columns([3, 2])
            with col_txt:
                st.markdown(f"⚽ **{row['Jogo']}**<br><span style='font-size:0.85em; color:gray;'>🏆 {row['Liga']} &nbsp;|&nbsp; ⏰ {row['Data/Hora']}</span>", unsafe_allow_html=True)
            
            with col_sel: escolha = st.selectbox("Vencedor", options=opcoes, index=idx_padrao, key=f"sel_{row['Jogo']}_{row['Data/Hora']}", label_visibility="collapsed")
            novos_resultados.append({'Jogo': row['Jogo'], 'Data/Hora': row['Data/Hora'], 'Vencedor_Partida': escolha})
            st.markdown("---")
            
        if st.form_submit_button("💾 Salvar Resultados", type="primary"):
            with st.spinner('A processar Greens e Reds...'):
                for item in novos_resultados:
                    mask = (df['Jogo'] == item['Jogo']) & (df['Data/Hora'] == item['Data/Hora'])
                    if item['Vencedor_Partida'] != "Pendente" and df.loc[mask, 'Vencedor_Partida'].iloc[0] == "Pendente":
                        df.loc[mask, 'Data_Resolucao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.loc[mask, 'Vencedor_Partida'] = item['Vencedor_Partida']
                    for idx in df[mask].index:
                        sel = str(df.at[idx, 'Seleção']).strip()
                        venc = str(item['Vencedor_Partida']).strip()
                        if venc == "Pendente" or venc == "" or venc == "nan": df.at[idx, 'Status_Aposta'] = "Pendente"
                        elif sel == venc: df.at[idx, 'Status_Aposta'] = "Green ✅"
                        else: df.at[idx, 'Status_Aposta'] = "Red ❌"
                df = df.drop(columns=['Recente'], errors='ignore')
                if salvar_no_github(df, "🤖 Resultados alimentados"): st.rerun()

# ==========================================
# ABA 5: ARQUIVO / HISTÓRICO COMPLETO
# ==========================================
with tab_hist:
    st.subheader("🗄️ Histórico Completo de Apostas")
    df_hist = df_calc.copy()
    
    col_h1, col_h2, col_h3, col_h4 = st.columns(4)
    with col_h1:
        casas_hist = ["Todas as Casas"] + sorted(df_hist['Casa'].dropna().unique().tolist())
        filtro_casa_hist = st.selectbox("Casa de Aposta:", casas_hist, key="filtro_hist_casa")
    with col_h2:
        esportes_hist = ["Todos os Esportes"] + sorted(df_hist['Esporte'].dropna().unique().tolist())
        filtro_esp_hist = st.selectbox("Esporte:", esportes_hist, key="filtro_hist_esporte")
    with col_h3:
        if filtro_esp_hist != "Todos os Esportes":
            ligas_hist = ["Todas as Ligas"] + sorted(df_hist[df_hist['Esporte'] == filtro_esp_hist]['Liga'].dropna().unique().tolist())
        else:
            ligas_hist = ["Todas as Ligas"] + sorted(df_hist['Liga'].dropna().unique().tolist())
        filtro_liga_hist = st.selectbox("Liga:", ligas_hist, key="filtro_hist_liga")
    with col_h4:
        tipos_hist = ["Todos os Momentos", "Pré-live", "Ao Vivo"]
        filtro_tipo_hist = st.selectbox("Momento do Alerta:", tipos_hist, key="filtro_hist_tipo")
    
    if filtro_casa_hist != "Todas as Casas": df_hist = df_hist[df_hist['Casa'] == filtro_casa_hist]
    if filtro_esp_hist != "Todos os Esportes": df_hist = df_hist[df_hist['Esporte'] == filtro_esp_hist]
    if filtro_liga_hist != "Todas as Ligas": df_hist = df_hist[df_hist['Liga'] == filtro_liga_hist]
    if filtro_tipo_hist != "Todos os Momentos": df_hist = df_hist[df_hist['Momento_Alerta'] == filtro_tipo_hist]
    
    df_hist['Payout'] = df_hist['Payout'].apply(lambda x: f"R$ {x:.2f}")
    
    df_hist.rename(columns={'Achado_em': 'Horário Alerta', 'Momento_Alerta': 'Tipo'}, inplace=True)
    
    cols_display = ['Data/Hora', 'Horário Alerta', 'Tipo', 'Esporte', 'Liga', 'Jogo', 'Casa', 'Seleção', 'Odd Justa', 'Odd Casa', 'Edge', 'ROI', 'Stake', 'Payout', 'Status_Aposta', 'Vencedor_Partida']
    st.dataframe(df_hist[cols_display], use_container_width=True)

# ==========================================
# ABA 6: ESTUDOS ESTATÍSTICOS
# ==========================================
with tab_estudos:
    st.subheader("🔬 Estudos Estatísticos: Edge vs Rentabilidade Relativa (ROI)")
    st.write("Análise da eficiência das odds.")
    
    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
    with col_e1:
        casas_estudos = ["Todas as Casas"] + sorted(df_calc['Casa'].dropna().unique().tolist())
        filtro_casa_estudos = st.selectbox("Casa de Aposta:", casas_estudos, key="filtro_estudos_casa")
    with col_e2:
        esportes_estudos = ["Todos os Esportes"] + sorted(df_calc['Esporte'].dropna().unique().tolist())
        filtro_esp_estudos = st.selectbox("Esporte:", esportes_estudos, key="filtro_estudos_esporte")
    with col_e3:
        if filtro_esp_estudos != "Todos os Esportes":
            ligas_estudos = ["Todas as Ligas"] + sorted(df_calc[df_calc['Esporte'] == filtro_esp_estudos]['Liga'].dropna().unique().tolist())
        else:
            ligas_estudos = ["Todas as Ligas"] + sorted(df_calc['Liga'].dropna().unique().tolist())
        filtro_liga_estudos = st.selectbox("Liga:", ligas_estudos, key="filtro_estudos_liga")
    with col_e4:
        tipos_estudos = ["Todos os Momentos", "Pré-live", "Ao Vivo"]
        filtro_tipo_estudos = st.selectbox("Momento do Alerta:", tipos_estudos, key="filtro_estudos_tipo")
    
    df_estudos = df_calc[df_calc['Status_Aposta'].isin(['Green ✅', 'Red ❌'])].copy()
    
    if filtro_casa_estudos != "Todas as Casas": df_estudos = df_estudos[df_estudos['Casa'] == filtro_casa_estudos]
    if filtro_esp_estudos != "Todos os Esportes": df_estudos = df_estudos[df_estudos['Esporte'] == filtro_esp_estudos]
    if filtro_liga_estudos != "Todas as Ligas": df_estudos = df_estudos[df_estudos['Liga'] == filtro_liga_estudos]
    if filtro_tipo_estudos != "Todos os Momentos": df_estudos = df_estudos[df_estudos['Momento_Alerta'] == filtro_tipo_estudos]
        
    if df_estudos.empty:
        st.info("Ainda não há dados suficientes de apostas finalizadas para gerar este gráfico com estes filtros.")
    else:
        fig_scatter = px.scatter(
            df_estudos,
            x='ROI_Realizado',
            y='Edge_Num',
            color='Status_Aposta',
            color_discrete_map={'Green ✅': '#00CC96', 'Red ❌': '#EF553B'},
            hover_data={
                'Jogo': True,
                'Esporte': True,
                'Casa': True,
                'Odd_Final': ':.2f',
                'Edge': True,      
                'Edge_Num': False, 
                'ROI_Realizado': False, 
                'Payout': ':.2f'
            },
            labels={'ROI_Realizado': 'ROI da Aposta (%)', 'Edge_Num': 'Edge'},
        )
        
        fig_scatter.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")
        fig_scatter.layout.yaxis.tickformat = ',.1%'
        fig_scatter.layout.xaxis.tickformat = ',.0%'
        
        st.plotly_chart(fig_scatter, use_container_width=True)
