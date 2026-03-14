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

# Garante que as novas colunas existem sem quebrar o CSV antigo
colunas_padrao = {
    'Vencedor_Partida': 'Pendente',
    'Status_Aposta': 'Pendente',
    'Aposta_Realizada': False,
    'Odd_Real': 0.0,
    'Stake_Real': 0.0,
    'Data_Resolucao': ""
}
for col, val in colunas_padrao.items():
    if col not in df.columns:
        df[col] = val

# Função Global para Salvar no GitHub
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
# PREPARAÇÃO MATEMÁTICA BASE
# ==========================================
df_calc = df.copy()
df_calc['Stake_Num'] = df_calc['Stake'].astype(str).str.replace('R$', '', regex=False).str.strip().astype(float)
df_calc['ROI_Num'] = df_calc['ROI'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Edge_Num'] = df_calc['Edge'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Odd_Num'] = df_calc['Odd Casa'].astype(float)

# ==========================================
# ESTRUTURA DE ABAS
# ==========================================
tab_dash, tab_apostas, tab_resultados, tab_hist = st.tabs([
    "📊 Dashboard", "🎯 Minhas Apostas", "📝 Alimentar Resultados", "🗄️ Histórico (Arquivo)"
])

# ==========================================
# ABA 1: DASHBOARD
# ==========================================
with tab_dash:
    filtro_visao = st.radio("Filtro de Análise:", ["Geral (Todas as Oportunidades)", "Apenas Apostadas", "Não Apostadas"], horizontal=True)
    
    # Aplica o filtro selecionado
    if filtro_visao == "Apenas Apostadas":
        df_dash = df_calc[df_calc['Aposta_Realizada'] == True].copy()
    elif filtro_visao == "Não Apostadas":
        df_dash = df_calc[df_calc['Aposta_Realizada'] == False].copy()
    else:
        df_dash = df_calc.copy()

    # Define Stake e Odd Finais (Se apostou, usa o Real; senão, usa o Teórico do robô)
    df_dash['Stake_Final'] = df_dash.apply(lambda x: x['Stake_Real'] if (x['Aposta_Realizada'] and pd.notnull(x['Stake_Real']) and float(x['Stake_Real']) > 0) else x['Stake_Num'], axis=1)
    df_dash['Odd_Final'] = df_dash.apply(lambda x: x['Odd_Real'] if (x['Aposta_Realizada'] and pd.notnull(x['Odd_Real']) and float(x['Odd_Real']) > 0) else x['Odd_Num'], axis=1)

    # Cálculo dinâmico do Payout
    def calc_payout(row):
        if row['Status_Aposta'] == 'Green ✅':
            return row['Stake_Final'] * (row['Odd_Final'] - 1)
        elif row['Status_Aposta'] == 'Red ❌':
            return -row['Stake_Final']
        return 0.0

    df_dash['Payout_Real'] = df_dash.apply(calc_payout, axis=1)
    df_resolvidas = df_dash[df_dash['Status_Aposta'].isin(['Green ✅', 'Red ❌'])]

    # Métricas Globais
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Oportunidades", f"{len(df_dash)}")
    col2.metric("Edge Médio Global", f"{(df_dash['Edge_Num'].mean() * 100):.2f}%" if not df_dash.empty else "0%")
    col3.metric("Payout Total", f"R$ {df_dash['Payout_Real'].sum():.2f}")
    taxa_acerto = (len(df_resolvidas[df_resolvidas['Status_Aposta'] == 'Green ✅']) / len(df_resolvidas) * 100) if not df_resolvidas.empty else 0.0
    col4.metric("Win Rate", f"{taxa_acerto:.1f}%")

    # Gráfico Temporal
    if not df_resolvidas.empty:
        st.markdown("### 📈 Evolução do Payout")
        # Extrai o dia/mês para o gráfico
        df_resolvidas['Data_Curta'] = df_resolvidas['Data/Hora'].str[:5] 
        grafico_dados = df_resolvidas.groupby('Data_Curta')['Payout_Real'].sum().reset_index()
        grafico_dados['Lucro_Acumulado'] = grafico_dados['Payout_Real'].cumsum()
        
        fig = px.line(grafico_dados, x='Data_Curta', y='Lucro_Acumulado', markers=True, text='Lucro_Acumulado')
        fig.add_bar(x=grafico_dados['Data_Curta'], y=grafico_dados['Payout_Real'], name="Lucro Diário", opacity=0.5)
        fig.update_traces(textposition="bottom right", selector=dict(type='scatter'))
        st.plotly_chart(fig, use_container_width=True)

    # Performance por Casa
    st.markdown("### 🏦 Performance Individual por Casa")
    analise_casas = df_dash.groupby('Casa').agg(
        Oportunidades=('Casa', 'count'),
        Edge_Medio=('Edge_Num', 'mean'), # Média Real solicitada
        EV_Medio=('ROI_Num', 'mean'),    # Média Real solicitada
        Stake_Total=('Stake_Final', 'sum'),
        Payout_Total=('Payout_Real', 'sum')
    ).reset_index().sort_values(by=['Payout_Total', 'Oportunidades'], ascending=[False, False])

    tabela_exibicao = analise_casas.copy()
    tabela_exibicao['Edge_Medio'] = (tabela_exibicao['Edge_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    tabela_exibicao['EV_Medio'] = (tabela_exibicao['EV_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    tabela_exibicao['Stake_Total'] = tabela_exibicao['Stake_Total'].apply(lambda x: f"R$ {x:.2f}")
    tabela_exibicao['Payout_Total'] = tabela_exibicao['Payout_Total'].apply(lambda x: f"R$ {x:.2f}")
    st.dataframe(tabela_exibicao, hide_index=True, use_container_width=True)

# ==========================================
# ABA 2: MINHAS APOSTAS (CHECK DE APOSTAS FEITAS)
# ==========================================
with tab_apostas:
    st.info("💡 **Dica:** Marque as oportunidades que você realmente apostou. Insira a Odd e Stake finais para maior precisão analítica.")
    
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
            hide_index=True,
            use_container_width=True,
            key="editor_apostas"
        )
        
        if st.button("💾 Salvar Registros de Apostas", type="primary"):
            with st.spinner('A enviar...'):
                df.update(editado[['Aposta_Realizada', 'Odd_Real', 'Stake_Real']])
                if salvar_no_github(df, "🤖 Atualizando apostas realizadas"):
                    st.rerun()

# ==========================================
# ABA 3: ALIMENTAR RESULTADOS (COM FILTRO >24H)
# ==========================================
with tab_resultados:
    st.info("Apenas jogos pendentes ou finalizados nas últimas 24h são exibidos aqui.")
    
    def eh_recente(d_str):
        if pd.isna(d_str) or d_str == "": return False
        try:
            dt = datetime.strptime(str(d_str), "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - dt).total_seconds() < 86400 # 24 horas
        except: return False

    df['Recente'] = df['Data_Resolucao'].apply(eh_recente)
    mostrar_antigos = st.checkbox("Forçar exibição de jogos antigos (Caso precise corrigir algum)")
    
    mask_exibicao = (df['Vencedor_Partida'] == 'Pendente') | (df['Recente'] == True)
    if mostrar_antigos:
        df_mostrar = df.copy()
    else:
        df_mostrar = df[mask_exibicao].copy()

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
            with col_txt: st.write(f"⚽ **{row['Jogo']}**")
            with col_sel:
                escolha = st.selectbox("Vencedor", options=opcoes, index=idx_padrao, key=f"sel_{row['Jogo']}_{row['Data/Hora']}", label_visibility="collapsed")
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
                        if venc == "Pendente" or venc == "": df.at[idx, 'Status_Aposta'] = "Pendente"
                        elif sel == venc: df.at[idx, 'Status_Aposta'] = "Green ✅"
                        else: df.at[idx, 'Status_Aposta'] = "Red ❌"

                # Drop colunas temporárias
                df = df.drop(columns=['Recente'], errors='ignore')
                if salvar_no_github(df, "🤖 Resultados das partidas alimentados"):
                    st.rerun()

# ==========================================
# ABA 4: ARQUIVO / HISTÓRICO COMPLETO
# ==========================================
with tab_hist:
    st.subheader("🗄️ Repositório Completo (Incluindo Payout Real)")
    # Aplica o cálculo de Payout no histórico visual também
    df_hist = df.copy()
    
    # Repete a logica basica para ter o Payout visual no historico
    df_hist['Stake_Temp'] = df_hist.apply(lambda x: x['Stake_Real'] if (x['Aposta_Realizada'] and float(x['Stake_Real']) > 0) else float(str(x['Stake']).replace('R$', '').strip()), axis=1)
    df_hist['Odd_Temp'] = df_hist.apply(lambda x: x['Odd_Real'] if (x['Aposta_Realizada'] and float(x['Odd_Real']) > 0) else float(x['Odd Casa']), axis=1)
    df_hist['Payout'] = df_hist.apply(lambda x: x['Stake_Temp'] * (x['Odd_Temp'] - 1) if x['Status_Aposta'] == 'Green ✅' else (-x['Stake_Temp'] if x['Status_Aposta'] == 'Red ❌' else 0.0), axis=1)
    
    # Formata a coluna Payout
    df_hist['Payout'] = df_hist['Payout'].apply(lambda x: f"R$ {x:.2f}")
    
    # Reordena colunas para colocar Stake, Payout e Status juntos
    cols_display = ['Data/Hora', 'Liga', 'Jogo', 'Casa', 'Seleção', 'Odd Casa', 'Stake', 'Payout', 'Status_Aposta', 'Aposta_Realizada', 'Vencedor_Partida']
    st.dataframe(df_hist[cols_display], use_container_width=True)
