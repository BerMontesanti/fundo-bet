import streamlit as st
import pandas as pd
import os
import json
import re
from github import Github
from datetime import datetime
import plotly.express as px
import requests

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

# ==========================================
# GESTÃO DO POTE (BANCA)
# ==========================================
ARQUIVO_BANCA = 'config_banca.json'

def carregar_banca():
    if os.path.exists(ARQUIVO_BANCA):
        try:
            with open(ARQUIVO_BANCA, 'r') as f:
                return float(json.load(f).get('banca', 250.0))
        except:
            return 250.0
    return 250.0

def salvar_banca_github(valor):
    data = {"banca": float(valor)}
    json_str = json.dumps(data, indent=4)
    with open(ARQUIVO_BANCA, 'w') as f:
        f.write(json_str)
        
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["REPO_NAME"])
        try:
            contents = repo.get_contents(ARQUIVO_BANCA)
            repo.update_file(contents.path, "🤖 Atualizando valor do pote", json_str, contents.sha)
        except:
            repo.create_file(ARQUIVO_BANCA, "🤖 Criando arquivo de banca", json_str)
        return True
    except Exception as e:
        st.error(f"❌ Erro ao guardar o Pote no GitHub: {e}")
        return False

# ==========================================
# 🎛️ CENTRO DE COMANDO (SIDEBAR)
# ==========================================
def disparar_workflow_github(nome_ficheiro_yml, nome_amigavel):
    url = f"https://api.github.com/repos/{st.secrets['REPO_NAME']}/actions/workflows/{nome_ficheiro_yml}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {"ref": "main"} 
    
    with st.spinner(f'A ligar o motor do {nome_amigavel}...'):
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 204:
            st.sidebar.success(f"✅ Ordem enviada! O {nome_amigavel} começou a trabalhar.")
        else:
            st.sidebar.error(f"❌ Erro ao ligar robô: {response.text}")

def atualizar_cron_workflow(nome_ficheiro_yml, novo_cron):
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["REPO_NAME"])
        path = f".github/workflows/{nome_ficheiro_yml}"
        contents = repo.get_contents(path)
        conteudo_atual = contents.decoded_content.decode("utf-8")
        conteudo_novo = re.sub(r"cron:\s*'.*'", f"cron: '{novo_cron}'", conteudo_atual)
        
        if conteudo_novo != conteudo_atual:
            repo.update_file(contents.path, f"🤖 Atualizando horários de {nome_ficheiro_yml}", conteudo_novo, contents.sha)
            st.sidebar.success(f"✅ Horário de {nome_ficheiro_yml} alterado com sucesso!")
        else:
            st.sidebar.info(f"O horário de {nome_ficheiro_yml} já está configurado assim.")
    except Exception as e:
        st.sidebar.error(f"❌ Erro (Verifique se o token tem permissão 'workflow'): {e}")

st.sidebar.markdown("### 🤖 Centro de Comando")
st.sidebar.write("Dispare operações manuais na nuvem:")

if st.sidebar.button("🔍 Varrer Odds Agora", use_container_width=True):
    disparar_workflow_github("bot_quant.yml", "Robô de Varredura")

if st.sidebar.button("📅 Gerar Agenda Agora", use_container_width=True):
    disparar_workflow_github("agenda_diaria.yml", "Jornaleiro da Agenda")

st.sidebar.divider()

st.sidebar.markdown("### ⏱️ Agendamento do Robô")
st.sidebar.caption("Formato Cron (Horário UTC). Ex: `0 */2 * * *`")

cron_varredura = st.sidebar.text_input("Frequência da Varredura:", value="0 */2 * * *")

if st.sidebar.button("💾 Salvar Novo Horário", use_container_width=True):
    with st.spinner("A alterar o workflow no GitHub..."):
        atualizar_cron_workflow("bot_quant.yml", cron_varredura)

# ==========================================
# LEITURA DA BASE DE DADOS PRINCIPAL
# ==========================================
ARQUIVO = 'historico_apostas.csv'

if not os.path.exists(ARQUIVO):
    st.warning("Nenhum histórico de apostas encontrado ainda.")
    df = pd.DataFrame()
else:
    df = pd.read_csv(ARQUIVO)

    colunas_padrao = {
        'Vencedor_Partida': 'Pendente',
        'Status_Aposta': 'Pendente',
        'Aposta_Realizada': False,
        'Odd_Real': 0.0,
        'Stake_Real': 0.0,
        'Data_Resolucao': "",
        'Achado_em': "",
        'Gap_Segundos': pd.NA 
    }
    for col, val in colunas_padrao.items():
        if col not in df.columns:
            df[col] = val

    df['Aposta_Realizada'] = df['Aposta_Realizada'].astype(str).str.strip().str.lower().map({'true': True, '1': True, '1.0': True}).fillna(False).astype(bool)

    def curar_vencedor_corrompido(row):
        venc = str(row.get('Vencedor_Partida', 'Pendente')).strip()
        if venc.lower() in ["nan", "", "none", "<na>", "nat"]: return "Pendente"
        if venc in ["Pendente", "Draw"]: return venc
        jogo = str(row.get('Jogo', ''))
        if ' x ' in jogo:
            try:
                casa, fora = jogo.split(' x ')
                if venc == casa.strip() or venc == fora.strip(): return venc
            except: pass
        return "Pendente"

    df['Vencedor_Partida'] = df.apply(curar_vencedor_corrompido, axis=1)

    def auto_corrigir_status(row):
        venc = str(row['Vencedor_Partida']).strip()
        sel = str(row['Seleção']).strip()
        if venc == "Pendente": return "Pendente"
        elif sel == venc: return "Green ✅"
        else: return "Red ❌"

    df['Status_Aposta'] = df.apply(auto_corrigir_status, axis=1)

def salvar_no_github(dataframe, mensagem):
    dataframe.to_csv(ARQUIVO, index=False)
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["REPO_NAME"])
        contents = repo.get_contents(ARQUIVO)
        novo_csv = dataframe.to_csv(index=False)
        repo.update_file(contents.path, mensagem, novo_csv, contents.sha)
        st.sidebar.success(f"✅ {mensagem} com sucesso na Nuvem!")
        return True
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao sincronizar: {e}")
        return False

# ==========================================
# PREPARAÇÃO MATEMÁTICA GLOBAL
# ==========================================
if not df.empty:
    def eh_recente(d_str):
        if pd.isna(d_str) or d_str == "": return False
        try: return (datetime.now() - datetime.strptime(str(d_str), "%Y-%m-%d %H:%M:%S")).total_seconds() < 86400 
        except: return False

    df['Recente'] = df['Data_Resolucao'].apply(eh_recente)
    df_calc = df.copy()
    df_calc = df_calc.drop_duplicates(subset=['Data/Hora', 'Jogo', 'Casa', 'Seleção'], keep='last')

    def classificar_momento(row):
        try:
            str_achado = str(row.get('Achado_em', ''))
            str_jogo = str(row.get('Data/Hora', ''))
            if str_achado.lower() in ['nan', 'nat', '', 'none']: return "Pré-live"
            dt_achado = datetime.strptime(str_achado, "%d/%m/%Y %H:%M:%S")
            ano = dt_achado.year
            dt_jogo = datetime.strptime(f"{str_jogo}/{ano}", "%d/%m %H:%M/%Y")
            if dt_achado < dt_jogo: return "Pré-live"
            else: return "Ao Vivo"
        except: return "Pré-live"

    df_calc['Momento_Alerta'] = df_calc.apply(classificar_momento, axis=1)
    df_calc['Esporte'] = df_calc['Liga'].apply(lambda x: str(x).split(' - ')[0].strip() if ' - ' in str(x) else 'Outro')

    df_calc['Stake_Num'] = pd.to_numeric(df_calc['Stake'].astype(str).str.replace('R$', '', regex=False).str.strip(), errors='coerce').fillna(0.0)
    df_calc['ROI_Num'] = pd.to_numeric(df_calc['ROI'].astype(str).str.replace('%', '', regex=False).str.strip(), errors='coerce').fillna(0.0) / 100
    df_calc['Edge_Num'] = pd.to_numeric(df_calc['Edge'].astype(str).str.replace('%', '', regex=False).str.strip(), errors='coerce').fillna(0.0) / 100
    df_calc['Odd_Num'] = pd.to_numeric(df_calc['Odd Casa'], errors='coerce').fillna(0.0)
    df_calc['Gap_Segundos'] = pd.to_numeric(df_calc['Gap_Segundos'], errors='coerce') 

    df_calc['Stake_Real_Num'] = pd.to_numeric(df_calc['Stake_Real'], errors='coerce').fillna(0.0)
    df_calc['Odd_Real_Num'] = pd.to_numeric(df_calc['Odd_Real'], errors='coerce').fillna(0.0)

    df_calc['Stake_Final'] = df_calc.apply(lambda x: float(x['Stake_Real_Num']) if (x['Aposta_Realizada'] and float(x['Stake_Real_Num']) > 0) else float(x['Stake_Num']), axis=1)
    df_calc['Odd_Final'] = df_calc.apply(lambda x: float(x['Odd_Real_Num']) if (x['Aposta_Realizada'] and float(x['Odd_Real_Num']) > 0) else float(x['Odd_Num']), axis=1)

    df_calc['EV_Esperado_R$'] = df_calc['Stake_Final'] * df_calc['ROI_Num']

    def calc_payout_global(row):
        if row['Status_Aposta'] == 'Green ✅': return float(row['Stake_Final']) * (float(row['Odd_Final']) - 1.0)
        elif row['Status_Aposta'] == 'Red ❌': return -float(row['Stake_Final'])
        return 0.0

    df_calc['Payout'] = df_calc.apply(calc_payout_global, axis=1)

    def calc_roi_realizado(row):
        if row['Status_Aposta'] in ['Green ✅', 'Red ❌'] and row['Stake_Final'] > 0:
            return row['Payout'] / row['Stake_Final']
        return 0.0

    df_calc['ROI_Realizado'] = df_calc.apply(calc_roi_realizado, axis=1)

# ==========================================
# CRIAÇÃO DAS ABAS
# ==========================================
tab_dash, tab_agenda, tab_calc, tab_apostas, tab_resultados, tab_hist, tab_estudos = st.tabs([
    "📊 Dashboard", "📅 Agenda do Dia", "🧮 Calculadora EV", "🎯 Minhas Apostas", "📝 Alimentar Resultados", "🗄️ Histórico", "🔬 Estudos Estatísticos"
])

# ==========================================
# ABA 1: DASHBOARD
# ==========================================
with tab_dash:
    if not df.empty:
        banca_atual = carregar_banca()
        col_pote1, col_pote2, col_pote3 = st.columns([1, 2, 2])
        with col_pote1:
            novo_valor_pote = st.number_input("💰 Valor do Pote (Banca):", min_value=0.0, value=banca_atual, step=10.0, format="%.2f")
            if novo_valor_pote != banca_atual:
                if st.button("💾 Guardar Novo Pote", type="primary"):
                    with st.spinner("Atualizando configurações..."):
                        if salvar_banca_github(novo_valor_pote):
                            st.rerun()
        st.divider()

        st.markdown("### 🎛️ Filtros de Análise")
        filtro_visao = st.radio("Filtro de Oportunidades:", ["Geral", "Apenas Apostadas", "Não Apostadas"], horizontal=True)
        
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            casas_disponiveis = ["Todas as Casas", "⭐ MINHAS APOSTAS"] + sorted(df_calc['Casa'].dropna().unique().tolist())
            casa_selecionada = st.selectbox("Casa de Aposta:", casas_disponiveis, key="filtro_dash_casa")
        with col_f2:
            esportes_disp = ["Todos os Esportes"] + sorted(df_calc['Esporte'].dropna().unique().tolist())
            esporte_selecionado = st.selectbox("Esporte:", esportes_disp, key="filtro_dash_esporte")
        with col_f3:
            if esporte_selecionado != "Todos os Esportes": ligas_disp = ["Todas as Ligas"] + sorted(df_calc[df_calc['Esporte'] == esporte_selecionado]['Liga'].dropna().unique().tolist())
            else: ligas_disp = ["Todas as Ligas"] + sorted(df_calc['Liga'].dropna().unique().tolist())
            liga_selecionada = st.selectbox("Liga:", ligas_disp, key="filtro_dash_liga")
        with col_f4:
            tipos_disp = ["Todos os Momentos", "Pré-live", "Ao Vivo"]
            tipo_selecionado = st.selectbox("Momento do Alerta:", tipos_disp, key="filtro_dash_tipo")

        df_dash = df_calc.copy()
        
        if filtro_visao == "Apenas Apostadas": df_dash = df_dash[df_dash['Aposta_Realizada'] == True]
        elif filtro_visao == "Não Apostadas": df_dash = df_dash[df_dash['Aposta_Realizada'] == False]
            
        if casa_selecionada == "⭐ MINHAS APOSTAS": df_dash = df_dash[df_dash['Aposta_Realizada'] == True]
        elif casa_selecionada != "Todas as Casas": df_dash = df_dash[df_dash['Casa'] == casa_selecionada]
        
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
            grafico_dados = df_resolvidas.groupby('Data_Curta').agg(Payout_Diario=('Payout', 'sum'), Stake_Diaria=('Stake_Final', 'sum')).reset_index()
            grafico_dados['Payout Acumulado'] = grafico_dados['Payout_Diario'].cumsum()
            grafico_dados['Stake Acumulada'] = grafico_dados['Stake_Diaria'].cumsum()
            grafico_dados['Yield Acumulado (%)'] = (grafico_dados['Payout Acumulado'] / grafico_dados['Stake Acumulada']) * 100
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown(f"### 📈 Evolução Financeira (R$)")
                fig_fin = px.line(grafico_dados, x='Data_Curta', y=['Stake Acumulada', 'Payout Acumulado'], markers=True, labels={'value': 'Valor (R$)', 'variable': 'Métrica', 'Data_Curta': 'Data'})
                fig_fin.for_each_trace(lambda t: t.update(name={'Stake Acumulada': 'Stake Total', 'Payout Acumulado': 'Payout'}.get(t.name, t.name)))
                st.plotly_chart(fig_fin, use_container_width=True)
            with col_g2:
                st.markdown(f"### 🚀 Evolução do Yield (%)")
                fig_yield = px.line(grafico_dados, x='Data_Curta', y='Yield Acumulado (%)', markers=True, labels={'Yield Acumulado (%)': 'Yield (%)', 'Data_Curta': 'Data'})
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
        
        if col_grupo == "Casa" and casa_selecionada == "Todas as Casas":
            df_minhas = df_resolvidas[df_resolvidas['Aposta_Realizada'] == True]
            if not df_minhas.empty:
                linha_minhas = {
                    'Casa': '⭐ MINHAS APOSTAS (Sua Carteira)',
                    'Oportunidades': len(df_minhas),
                    'Greens': (df_minhas['Status_Aposta'] == 'Green ✅').sum(),
                    'Edge_Medio': df_minhas['Edge_Num'].mean(),
                    'EV_Medio': df_minhas['ROI_Num'].mean(),
                    'Stake_Total': df_minhas['Stake_Final'].sum(),
                    'EV_Esperado': df_minhas['EV_Esperado_R$'].sum(),
                    'Payout': df_minhas['Payout'].sum()
                }
                analise_tabela = pd.concat([analise_tabela, pd.DataFrame([linha_minhas])], ignore_index=True)

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
# ABA 2: AGENDA DO DIA
# ==========================================
with tab_agenda:
    st.markdown("### 📅 Agenda de Jogos do Dia")
    st.info("Esta lista exibe os jogos de hoje (Fuso: Brasília) para todas as ligas monitorizadas. O relatório é gerado automaticamente pelo robô 'Jornaleiro' na nuvem às 08h00 da manhã.")

    ARQUIVO_AGENDA = 'agenda_hoje.csv'
    if os.path.exists(ARQUIVO_AGENDA):
        df_agenda = pd.read_csv(ARQUIVO_AGENDA)
        
        if df_agenda.empty:
            st.success("⚽ Não há nenhum jogo agendado para hoje nas suas ligas ativas!")
        else:
            modo_visao = st.radio("Selecione o formato de visualização:", ["⏰ Ordem Cronológica Geral", "🏆 Agrupado por Ligas"], horizontal=True)
            
            if modo_visao == "⏰ Ordem Cronológica Geral":
                st.dataframe(df_agenda, hide_index=True, use_container_width=True)
            else:
                ligas_hoje = sorted(df_agenda['Liga'].unique())
                for liga in ligas_hoje:
                    st.markdown(f"#### {liga}")
                    df_liga = df_agenda[df_agenda['Liga'] == liga].drop(columns=['Liga', 'Esporte'])
                    st.dataframe(df_liga, hide_index=True, use_container_width=True)
    else:
        st.warning("⚠️ O relatório de hoje ainda não foi gerado. Pode dispará-lo manualmente usando o botão 'Gerar Agenda Agora' no Centro de Comando lateral.")

# ==========================================
# ABA 3: CALCULADORA EV
# ==========================================
with tab_calc:
    st.markdown("### 🧮 Calculadora Rápida de EV")
    st.write("Introduza as odds para descobrir se há valor matemático na aposta e qual a stake ideal.")

    with st.form("form_calculadora_ev"):
        col_calc_1, col_calc_2 = st.columns(2)
        with col_calc_1:
            st.markdown("#### 1. Odd da Casa de Apostas (Soft)")
            odd_casa_input = st.number_input("Odd que você quer apostar (ex: BetMGM):", min_value=1.01, value=2.10, step=0.05, format="%.2f")
            banca_input = st.number_input("Banca Total (R$):", min_value=10.0, value=carregar_banca(), step=10.0)
        with col_calc_2:
            st.markdown("#### 2. Odds da Pinnacle (Sharp)")
            odd_pin_sel = st.number_input("Odd Pinnacle para a sua seleção:", min_value=1.01, value=1.95, step=0.05, format="%.2f")
            odd_pin_opp = st.number_input("Odd Pinnacle para o oponente (Lay/Dupla Chance):", min_value=1.01, value=1.85, step=0.05, format="%.2f")
            st.caption("*(Dica: Num mercado 1X2, some a probabilidade do Empate e do Visitante e converta para Odd, ou use um mercado Asiático 2-way)*")

        btn_calcular = st.form_submit_button("🎯 Calcular EV", type="primary", use_container_width=True)

    if btn_calcular:
        if odd_pin_sel > 1.0 and odd_pin_opp > 1.0 and odd_casa_input > 1.0:
            imp_sel = 1 / odd_pin_sel
            imp_opp = 1 / odd_pin_opp
            margem_total = imp_sel + imp_opp
            
            prob_real = imp_sel / margem_total
            odd_justa = 1 / prob_real
            
            roi_calc = (prob_real * odd_casa_input) - 1
            edge_calc = prob_real - (1 / odd_casa_input)
            
            b_kelly = odd_casa_input - 1
            f_kelly = (prob_real * b_kelly - (1 - prob_real)) / b_kelly
            
            stake_calc = banca_input * (f_kelly * 0.25) if f_kelly > 0 else 0.0

            st.markdown("### 🎯 Resultados da Análise")
            res_c1, res_c2, res_c3, res_c4 = st.columns(4)
            res_c1.metric("Probabilidade Real", f"{(prob_real * 100):.1f}%")
            res_c2.metric("Odd Justa (Fair Odd)", f"{odd_justa:.2f}")
            
            if edge_calc > 0:
                res_c3.metric("Edge (Vantagem)", f"{(edge_calc * 100):.2f}%", "Aposta de Valor +EV")
                res_c4.metric("Stake Recomendada", f"R$ {stake_calc:.2f}", f"ROI Esperado: {(roi_calc * 100):.1f}%")
                st.success("✅ **SINAL VERDE!** A casa está a oferecer um prémio superior ao risco real.")
            else:
                res_c3.metric("Edge (Vantagem)", f"{(edge_calc * 100):.2f}%", "-EV (Não Apostar)")
                res_c4.metric("Stake Recomendada", "R$ 0.00", "Aposta com Prejuízo")
                st.error("❌ **SINAL VERMELHO!** A odd da casa não compensa o risco.")

# ==========================================
# ABA 4: MINHAS APOSTAS
# ==========================================
with tab_apostas:
    if not df.empty:
        st.markdown("### 🎯 Detalhamento das Suas Apostas")
        st.info("Insira a Odd e a Stake exatas que operou na sua carteira.")
        
        mostrar_antigas_apostas = st.checkbox("Forçar exibição de apostas antigas já finalizadas", key="chk_antigas_ap")
        
        if mostrar_antigas_apostas: mask_minhas = (df['Aposta_Realizada'] == True)
        else: mask_minhas = (df['Aposta_Realizada'] == True) & ((df['Status_Aposta'] == 'Pendente') | (df['Recente'] == True))
            
        df_minhas_pendentes = df[mask_minhas].copy()
        df_minhas_pendentes['Sort_Date'] = pd.to_datetime(df_minhas_pendentes['Data/Hora'], format='%d/%m %H:%M', errors='coerce').fillna(pd.Timestamp('1900-01-01'))
        df_minhas_pendentes = df_minhas_pendentes.sort_values(by='Sort_Date', ascending=False).drop(columns=['Sort_Date'])
        
        if df_minhas_pendentes.empty:
            st.success("Nenhuma aposta pendente ou recente. Vá à aba 'Alimentar Resultados' para marcar novas oportunidades operadas!")
        else:
            colunas_edicao = ['Data/Hora', 'Jogo', 'Seleção', 'Odd_Real', 'Stake_Real']
            df_minhas_pendentes['Odd_Real'] = pd.to_numeric(df_minhas_pendentes['Odd_Real'], errors='coerce').fillna(0.0)
            df_minhas_pendentes['Stake_Real'] = pd.to_numeric(df_minhas_pendentes['Stake_Real'], errors='coerce').fillna(0.0)

            editado_minhas = st.data_editor(
                df_minhas_pendentes[colunas_edicao],
                column_config={
                    "Odd_Real": st.column_config.NumberColumn("Odd Real Pega", format="%.2f", min_value=0.0),
                    "Stake_Real": st.column_config.NumberColumn("Stake Colocada (R$)", format="%.2f", min_value=0.0),
                },
                disabled=["Data/Hora", "Jogo", "Seleção"],
                hide_index=True, use_container_width=True, key="editor_apostas_reais"
            )
            if st.button("💾 Salvar Valores Executados", type="primary", key="btn_salvar_valores"):
                with st.spinner('A salvar na nuvem...'):
                    df.update(editado_minhas[['Odd_Real', 'Stake_Real']])
                    df = df.drop(columns=['Recente'], errors='ignore')
                    if salvar_no_github(df, "🤖 Atualizando stake e odd real"): st.rerun()

# ==========================================
# ABA 5: ALIMENTAR RESULTADOS
# ==========================================
with tab_resultados:
    if not df.empty:
        st.markdown("### 📝 Gestão de Entradas e Placares")
        col_busca, col_check = st.columns([3, 1])
        with col_busca: termo_busca = st.text_input("🔍 Buscar por Equipa, Liga ou Seleção:", "", placeholder="Ex: Arsenal, Premier League...")
        with col_check:
            st.write("") 
            st.write("")
            mostrar_antigos = st.checkbox("Forçar jogos antigos", key="chk_antigos_res")
        
        mask_exibicao = (df['Status_Aposta'] == 'Pendente') | (df['Recente'] == True)
        if mostrar_antigos: df_mostrar = df.copy()
        else: df_mostrar = df[mask_exibicao].copy()

        if termo_busca:
            termo_lower = termo_busca.lower()
            mask_busca = (df_mostrar['Jogo'].astype(str).str.lower().str.contains(termo_lower) | df_mostrar['Liga'].astype(str).str.lower().str.contains(termo_lower) | df_mostrar['Seleção'].astype(str).str.lower().str.contains(termo_lower))
            df_mostrar = df_mostrar[mask_busca]

        df_mostrar['Ordem_Status'] = df_mostrar['Status_Aposta'].apply(lambda x: 0 if x == 'Pendente' else 1)
        df_mostrar['Sort_Date'] = pd.to_datetime(df_mostrar['Data/Hora'], format='%d/%m %H:%M', errors='coerce').fillna(pd.Timestamp('1900-01-01'))
        df_unicos = df_mostrar.drop_duplicates(subset=['Data/Hora', 'Jogo', 'Seleção']).sort_values(by=['Ordem_Status', 'Sort_Date'], ascending=[True, False])

        if df_unicos.empty:
            if termo_busca: st.warning(f"Nenhum jogo encontrado para '{termo_busca}'.")
            else: st.success("Nenhuma oportunidade pendente ou recente.")
        else:
            with st.form("form_resultados_unificado"):
                novos_resultados = []
                for index, row in df_unicos.iterrows():
                    opcoes = ["Pendente", "Draw"]
                    if ' x ' in str(row['Jogo']):
                        try:
                            c, f = str(row['Jogo']).split(' x ')
                            opcoes = ["Pendente", c, f, "Draw"]
                        except: pass
                        
                    valor_atual = str(row['Vencedor_Partida']).strip()
                    if valor_atual not in opcoes: opcoes.append(valor_atual)
                    idx_padrao = opcoes.index(valor_atual) if valor_atual in opcoes else 0
                    apostado_atual = bool(row.get('Aposta_Realizada', False))
                    
                    col_txt, col_chk, col_sel = st.columns([4, 1, 2])
                    with col_txt: st.markdown(f"⚽ **{row['Jogo']}**<br><span style='font-size:0.85em; color:gray;'>🎯 Seleção: **{row['Seleção']}** | ⏰ {row['Data/Hora']}</span>", unsafe_allow_html=True)
                    with col_chk: escolha_aposta = st.checkbox("Apostei?", value=apostado_atual, key=f"chk_{index}")
                    with col_sel: escolha_venc = st.selectbox("Vencedor", options=opcoes, index=idx_padrao, key=f"sel_{index}", label_visibility="collapsed")
                    
                    novos_resultados.append({'index': index, 'Jogo': row['Jogo'], 'Data/Hora': row['Data/Hora'], 'Aposta_Realizada': escolha_aposta, 'Vencedor_Partida': escolha_venc})
                    st.markdown("---")
                    
                if st.form_submit_button("💾 Salvar Alterações", type="primary"):
                    with st.spinner('A atualizar base de dados...'):
                        for item in novos_resultados:
                            idx_unico = item['index']
                            novo_venc = item['Vencedor_Partida']
                            nova_aposta = item['Aposta_Realizada']
                            mask_jogo = (df['Jogo'] == item['Jogo']) & (df['Data/Hora'] == item['Data/Hora'])
                            
                            if novo_venc != "Pendente" and df.loc[mask_jogo, 'Vencedor_Partida'].iloc[0] == "Pendente": df.loc[mask_jogo, 'Data_Resolucao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df.loc[mask_jogo, 'Vencedor_Partida'] = novo_venc
                            df.at[idx_unico, 'Aposta_Realizada'] = nova_aposta
                            
                            for idx_calc in df[mask_jogo].index:
                                sel = str(df.at[idx_calc, 'Seleção']).strip()
                                venc_str = str(novo_venc).strip()
                                if venc_str == "Pendente" or venc_str == "" or venc_str == "nan": df.at[idx_calc, 'Status_Aposta'] = "Pendente"
                                elif sel == venc_str: df.at[idx_calc, 'Status_Aposta'] = "Green ✅"
                                else: df.at[idx_calc, 'Status_Aposta'] = "Red ❌"
                                
                        df = df.drop(columns=['Recente', 'Ordem_Status', 'Sort_Date'], errors='ignore')
                        if salvar_no_github(df, "🤖 Resultados e entradas atualizados"): st.rerun()

# ==========================================
# ABA 6: HISTÓRICO COMPLETO
# ==========================================
with tab_hist:
    if not df.empty:
        st.subheader("🗄️ Histórico Completo de Apostas")
        df_hist = df_calc.copy()
        df_hist['Sort_Date'] = pd.to_datetime(df_hist['Data/Hora'], format='%d/%m %H:%M', errors='coerce').fillna(pd.Timestamp('1900-01-01'))
        df_hist = df_hist.sort_values(by='Sort_Date', ascending=False)
        
        col_h1, col_h2, col_h3, col_h4 = st.columns(4)
        with col_h1:
            casas_hist = ["Todas as Casas", "⭐ MINHAS APOSTAS"] + sorted(df_hist['Casa'].dropna().unique().tolist())
            filtro_casa_hist = st.selectbox("Casa de Aposta:", casas_hist, key="filtro_hist_casa")
        with col_h2:
            esportes_hist = ["Todos os Esportes"] + sorted(df_hist['Esporte'].dropna().unique().tolist())
            filtro_esp_hist = st.selectbox("Esporte:", esportes_hist, key="filtro_hist_esporte")
        with col_h3:
            if filtro_esp_hist != "Todos os Esportes": ligas_hist = ["Todas as Ligas"] + sorted(df_hist[df_hist['Esporte'] == filtro_esp_hist]['Liga'].dropna().unique().tolist())
            else: ligas_hist = ["Todas as Ligas"] + sorted(df_hist['Liga'].dropna().unique().tolist())
            filtro_liga_hist = st.selectbox("Liga:", ligas_hist, key="filtro_hist_liga")
        with col_h4:
            tipos_hist = ["Todos os Momentos", "Pré-live", "Ao Vivo"]
            filtro_tipo_hist = st.selectbox("Momento do Alerta:", tipos_hist, key="filtro_hist_tipo")
        
        if filtro_casa_hist == "⭐ MINHAS APOSTAS": df_hist = df_hist[df_hist['Aposta_Realizada'] == True]
        elif filtro_casa_hist != "Todas as Casas": df_hist = df_hist[df_hist['Casa'] == filtro_casa_hist]
        
        if filtro_esp_hist != "Todos os Esportes": df_hist = df_hist[df_hist['Esporte'] == filtro_esp_hist]
        if filtro_liga_hist != "Todas as Ligas": df_hist = df_hist[df_hist['Liga'] == filtro_liga_hist]
        if filtro_tipo_hist != "Todos os Momentos": df_hist = df_hist[df_hist['Momento_Alerta'] == filtro_tipo_hist]
        
        df_hist['Payout'] = df_hist['Payout'].apply(lambda x: f"R$ {x:.2f}")
        df_hist.rename(columns={'Achado_em': 'Horário Alerta', 'Momento_Alerta': 'Tipo'}, inplace=True)
        
        cols_display = ['Data/Hora', 'Tipo', 'Esporte', 'Jogo', 'Casa', 'Seleção', 'Odd Casa', 'Edge', 'Stake', 'Payout', 'Status_Aposta', 'Gap_Segundos']
        cols_display = [c for c in cols_display if c in df_hist.columns]
        st.dataframe(df_hist[cols_display], use_container_width=True)

# ==========================================
# ABA 7: ESTUDOS ESTATÍSTICOS
# ==========================================
with tab_estudos:
    if not df.empty:
        st.subheader("🔬 Estudos Estatísticos: Eficiência do Modelo")
        
        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        with col_e1:
            casas_estudos = ["Todas as Casas", "⭐ MINHAS APOSTAS"] + sorted(df_calc['Casa'].dropna().unique().tolist())
            filtro_casa_estudos = st.selectbox("Casa de Aposta:", casas_estudos, key="filtro_estudos_casa")
        with col_e2:
            esportes_estudos = ["Todos os Esportes"] + sorted(df_calc['Esporte'].dropna().unique().tolist())
            filtro_esp_estudos = st.selectbox("Esporte:", esportes_estudos, key="filtro_estudos_esporte")
        with col_e3:
            if filtro_esp_estudos != "Todos os Esportes": ligas_estudos = ["Todas as Ligas"] + sorted(df_calc[df_calc['Esporte'] == filtro_esp_estudos]['Liga'].dropna().unique().tolist())
            else: ligas_estudos = ["Todas as Ligas"] + sorted(df_calc['Liga'].dropna().unique().tolist())
            filtro_liga_estudos = st.selectbox("Liga:", ligas_estudos, key="filtro_estudos_liga")
        with col_e4:
            tipos_estudos = ["Todos os Momentos", "Pré-live", "Ao Vivo"]
            filtro_tipo_estudos = st.selectbox("Momento do Alerta:", tipos_estudos, key="filtro_estudos_tipo")
        
        df_estudos = df_calc[df_calc['Status_Aposta'].isin(['Green ✅', 'Red ❌'])].copy()
        
        if filtro_casa_estudos == "⭐ MINHAS APOSTAS": df_estudos = df_estudos[df_estudos['Aposta_Realizada'] == True]
        elif filtro_casa_estudos != "Todas as Casas": df_estudos = df_estudos[df_estudos['Casa'] == filtro_casa_estudos]
        if filtro_esp_estudos != "Todos os Esportes": df_estudos = df_estudos[df_estudos['Esporte'] == filtro_esp_estudos]
        if filtro_liga_estudos != "Todas as Ligas": df_estudos = df_estudos[df_estudos['Liga'] == filtro_liga_estudos]
        if filtro_tipo_estudos != "Todos os Momentos": df_estudos = df_estudos[df_estudos['Momento_Alerta'] == filtro_tipo_estudos]
            
        if df_estudos.empty:
            st.info("Ainda não há dados suficientes de apostas finalizadas para gerar análises com estes filtros.")
        else:
            st.markdown("#### 1. Edge vs Rentabilidade Relativa (ROI)")
            fig_scatter = px.scatter(df_estudos, x='ROI_Realizado', y='Edge_Num', color='Status_Aposta', color_discrete_map={'Green ✅': '#00CC96', 'Red ❌': '#EF553B'}, hover_data={'Jogo': True, 'Esporte': True, 'Casa': True, 'Odd_Final': ':.2f', 'Edge': True, 'Edge_Num': False, 'ROI_Realizado': False, 'Payout': ':.2f'}, labels={'ROI_Realizado': 'ROI da Aposta (%)', 'Edge_Num': 'Edge'})
            fig_scatter.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")
            fig_scatter.layout.yaxis.tickformat = ',.1%'
            fig_scatter.layout.xaxis.tickformat = ',.0%'
            st.plotly_chart(fig_scatter, use_container_width=True)

            st.divider()
            st.markdown("#### 👻 2. Laboratório de Sincronismo: Performance Teórica Absoluta")
            
            col_lab1, col_lab2 = st.columns([1, 2])
            with col_lab1:
                casas_lab_disp = ["Todas as Casas"] + sorted(df_calc['Casa'].dropna().unique().tolist())
                casa_lab = st.selectbox("Filtro de Casa (Laboratório):", casas_lab_disp, key="lab_casa")
            with col_lab2:
                limite_ghost = st.slider("Definir limite aceitável para considerar a Odd como 'Real' (Segundos):", min_value=1, max_value=120, value=10, step=1)
            
            df_lab = df_calc[df_calc['Status_Aposta'].isin(['Green ✅', 'Red ❌'])].copy()
            if casa_lab != "Todas as Casas": df_lab = df_lab[df_lab['Casa'] == casa_lab]
            
            df_lab = df_lab.dropna(subset=['Gap_Segundos'])
            df_lab = df_lab[df_lab['Gap_Segundos'] != 999] 
            
            if df_lab.empty:
                st.info("Aguardando acumulação de dados novos para o laboratório de sincronismo...")
            else:
                def classificar_ghost(gap):
                    if gap <= limite_ghost: return "⚡ Odd Real"
                    else: return "👻 Ghost Odd"
                    
                df_lab['Categoria_Odd'] = df_lab['Gap_Segundos'].apply(classificar_ghost)
                analise_ghost = df_lab.groupby('Categoria_Odd').agg(Volume_Resolvido=('Categoria_Odd', 'count'), Greens=('Status_Aposta', lambda x: (x == 'Green ✅').sum()), Edge_Medio=('Edge_Num', 'mean'), Stake_Total=('Stake_Final', 'sum'), Payout=('Payout', 'sum')).reset_index()
                
                analise_ghost['Taxa_Acerto'] = (analise_ghost['Greens'] / analise_ghost['Volume_Resolvido'] * 100).fillna(0)
                analise_ghost['Yield'] = (analise_ghost['Payout'] / analise_ghost['Stake_Total'] * 100).fillna(0)
                
                exibicao_ghost = analise_ghost.copy()
                exibicao_ghost['Taxa_Acerto'] = exibicao_ghost['Taxa_Acerto'].apply(lambda x: f"{x:.1f}%")
                exibicao_ghost['Edge_Medio'] = (exibicao_ghost['Edge_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
                exibicao_ghost['Stake_Total'] = exibicao_ghost['Stake_Total'].apply(lambda x: f"R$ {x:.2f}")
                exibicao_ghost['Payout'] = exibicao_ghost['Payout'].apply(lambda x: f"R$ {x:.2f}")
                exibicao_ghost['Yield'] = exibicao_ghost['Yield'].apply(lambda x: f"{x:.2f}%")
                
                st.dataframe(exibicao_ghost, hide_index=True, use_container_width=True)
                
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    fig_bar_yield = px.bar(analise_ghost, x='Categoria_Odd', y='Yield', color='Categoria_Odd', text_auto='.2f', title=f"Yield Teórico Médio (<{limite_ghost}s)", color_discrete_map={"⚡ Odd Real": "#00CC96", "👻 Ghost Odd": "#EF553B"})
                    st.plotly_chart(fig_bar_yield, use_container_width=True)
                with col_chart2:
                    fig_bar_vol = px.bar(analise_ghost, x='Categoria_Odd', y='Volume_Resolvido', color='Categoria_Odd', text_auto=True, title="Volume Total Identificado pelo Algoritmo", color_discrete_map={"⚡ Odd Real": "#1f77b4", "👻 Ghost Odd": "#7f7f7f"})
                    st.plotly_chart(fig_bar_vol, use_container_width=True)
