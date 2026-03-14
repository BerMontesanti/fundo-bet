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

# Conversão de textos para números para cálculos
df_calc['Stake_Num'] = df_calc['Stake'].astype(str).str.replace('R$', '', regex=False).str.strip().astype(float)
df_calc['ROI_Num'] = df_calc['ROI'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Edge_Num'] = df_calc['Edge'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Odd_Num'] = df_calc['Odd Casa'].astype(float)

# Definição Global de Stake e Odd Finais (Se apostou usa a real, se não usa a teórica do robô)
df_calc['Stake_Final'] = df_calc.apply(lambda x: x['Stake_Real'] if (x['Aposta_Realizada'] and pd.notnull(x['Stake_Real']) and float(x['Stake_Real']) > 0) else x['Stake_Num'], axis=1)
df_calc['Odd_Final'] = df_calc.apply(lambda x: x['Odd_Real'] if (x['Aposta_Realizada'] and pd.notnull(x['Odd_Real']) and float(x['Odd_Real']) > 0) else x['Odd_Num'], axis=1)

# Cálculo Global do Lucro para ser usado em todas as abas
def calc_lucro_global(row):
    if row['Status_Aposta'] == 'Green ✅':
        return row['Stake_Final'] * (row['Odd_Final'] - 1)
    elif row['Status_Aposta'] == 'Red ❌':
        return -row['Stake_Final']
    return 0.0

df_calc['Lucro'] = df_calc.apply(calc_lucro_global, axis=1)

# ==========================================
# ESTRUTURA DE ABAS (AGORA SÃO 5)
# ==========================================
tab_dash, tab_apostas, tab_resultados, tab_hist, tab_estudos = st.tabs([
    "📊 Dashboard", "🎯 Minhas Apostas", "📝 Alimentar Resultados", "🗄️ Histórico", "🔬 Estudos Estatísticos"
])

# ==========================================
# ABA 1: DASHBOARD
# ==========================================
with tab_dash:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filtro_visao = st.radio("Filtro de Oportunidades:", ["Geral", "Apenas Apostadas", "Não Apostadas"], horizontal=True)
    with col_f2:
        casas_disponiveis = ["Todas as Casas"] + sorted(df_calc['Casa'].dropna().unique().tolist())
        casa_selecionada = st.selectbox("Filtrar por Casa de Aposta:", casas_disponiveis, key="filtro_dash_casa")

    df_dash = df_calc.copy()
    
    if filtro_visao == "Apenas Apostadas":
        df_dash = df_dash[df_dash['Aposta_Realizada'] == True]
    elif filtro_visao == "Não Apostadas":
        df_dash = df_dash[df_dash['Aposta_Realizada'] == False]
        
    if casa_selecionada != "Todas as Casas":
        df_dash = df_dash[df_dash['Casa'] == casa_selecionada]

    df_resolvidas = df_dash[df_dash['Status_Aposta'].isin(['Green ✅', 'Red ❌'])].copy()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Oportunidades", f"{len(df_dash)}")
    col2.metric("Edge Médio", f"{(df_dash['Edge_Num'].mean() * 100):.2f}%" if not df_dash.empty else "0%")
    col3.metric("Stake Total", f"R$ {df_dash['Stake_Final'].sum():.2f}")
    
    lucro_total_formatado = f"R$ {df_dash['Lucro'].sum():.2f}"
    col4.metric("Lucro Total", lucro_total_formatado, delta=lucro_total_formatado)
    
    taxa_acerto = (len(df_resolvidas[df_resolvidas['Status_Aposta'] == 'Green ✅']) / len(df_resolvidas) * 100) if not df_resolvidas.empty else 0.0
    col5.metric("Win Rate", f"{taxa_acerto:.1f}%")

    if not df_resolvidas.empty:
        st.markdown(f"### 📈 Evolução: Stake Total e Lucro ({casa_selecionada})")
        df_resolvidas['Data_Curta'] = df_resolvidas['Data/Hora'].str[:5] 
        grafico_dados = df_resolvidas.groupby('Data_Curta').agg(
            Lucro_Diario=('Lucro', 'sum'),
            Stake_Diaria=('Stake_Final', 'sum')
        ).reset_index()
        
        grafico_dados['Lucro Acumulado'] = grafico_dados['Lucro_Diario'].cumsum()
        grafico_dados['Stake Acumulada'] = grafico_dados['Stake_Diaria'].cumsum()
        
        fig = px.line(
            grafico_dados, 
            x='Data_Curta', 
            y=['Stake Acumulada', 'Lucro Acumulado'], 
            markers=True, 
            labels={'value': 'Valor (R$)', 'variable': 'Métrica', 'Data_Curta': 'Data'}
        )
        
        novos_nomes = {'Stake Acumulada': 'Stake Total', 'Lucro Acumulado': 'Lucro'}
        fig.for_each_trace(lambda t: t.update(name = novos_nomes.get(t.name, t.name)))
        
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🏦 Performance Individual por Casa")
    analise_casas = df_dash.groupby('Casa').agg(
        Oportunidades=('Casa', 'count'),
        Edge_Medio=('Edge_Num', 'mean'),
        EV_Medio=('ROI_Num', 'mean'),
        Stake_Total=('Stake_Final', 'sum'),
        Lucro_Total=('Lucro', 'sum')
    ).reset_index().sort_values(by=['Lucro_Total', 'Oportunidades'], ascending=[False, False])

    tabela_exibicao = analise_casas.copy()
    tabela_exibicao['Edge_Medio'] = (tabela_exibicao['Edge_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    tabela_exibicao['EV_Medio'] = (tabela_exibicao['EV_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    tabela_exibicao['Stake_Total'] = tabela_exibicao['Stake_Total'].apply(lambda x: f"R$ {x:.2f}")
    tabela_exibicao['Lucro_Total'] = tabela_exibicao['Lucro_Total'].apply(lambda x: f"R$ {x:.2f}")
    st.dataframe(tabela_exibicao, hide_index=True, use_container_width=True)

# ==========================================
# ABA 2: MINHAS APOSTAS
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
# ABA 3: RESULTADOS
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

                df = df.drop(columns=['Recente'], errors='ignore')
                if salvar_no_github(df, "🤖 Resultados das partidas alimentados"):
                    st.rerun()

# ==========================================
# ABA 4: ARQUIVO / HISTÓRICO COMPLETO
# ==========================================
with tab_hist:
    st.subheader("🗄️ Histórico Completo de Apostas")
    
    # Usa o df já calculado globalmente!
    df_hist = df_calc.copy()
    
    casas_hist = ["Todas as Casas"] + sorted(df_hist['Casa'].dropna().unique().tolist())
    filtro_casa_hist = st.selectbox("Filtrar Histórico por Casa de Aposta:", casas_hist, key="filtro_hist_casa")
    
    if filtro_casa_hist != "Todas as Casas":
        df_hist = df_hist[df_hist['Casa'] == filtro_casa_hist]
    
    # Formata a coluna de Lucro para exibição em texto
    df_hist['Lucro'] = df_hist['Lucro'].apply(lambda x: f"R$ {x:.2f}")
    
    cols_display = [
        'Data/Hora', 'Liga', 'Jogo', 'Casa', 'Seleção', 
        'Odd Justa', 'Odd Casa', 'Edge', 'ROI', 
        'Stake', 'Lucro', 'Status_Aposta', 'Aposta_Realizada', 'Vencedor_Partida'
    ]
    
    st.dataframe(df_hist[cols_display], use_container_width=True)

# ==========================================
# ABA 5: ESTUDOS ESTATÍSTICOS
# ==========================================
with tab_estudos:
    st.subheader("🔬 Estudos Estatísticos: Edge vs Lucro")
    st.write("Análise de dispersão para validar se o Edge matemático está a refletir-se no lucro prático.")
    
    casas_estudos = ["Todas as Casas"] + sorted(df_calc['Casa'].dropna().unique().tolist())
    filtro_casa_estudos = st.selectbox("Filtrar por Casa de Aposta:", casas_estudos, key="filtro_estudos_casa")
    
    # Filtra apenas apostas que já tiveram desfecho (Green ou Red)
    df_estudos = df_calc[df_calc['Status_Aposta'].isin(['Green ✅', 'Red ❌'])].copy()
    
    if filtro_casa_estudos != "Todas as Casas":
        df_estudos = df_estudos[df_estudos['Casa'] == filtro_casa_estudos]
        
    if df_estudos.empty:
        st.info("Ainda não há dados suficientes de apostas finalizadas para gerar este gráfico.")
    else:
        # Gráfico de Dispersão (Scatter Plot)
        fig_scatter = px.scatter(
            df_estudos,
            x='Lucro',
            y='Edge_Num',
            color='Status_Aposta',
            color_discrete_map={'Green ✅': '#00CC96', 'Red ❌': '#EF553B'},
            hover_data={
                'Jogo': True,
                'Casa': True,
                'Odd_Final': ':.2f',
                'Edge': True,      # Mostra o Edge original formatado com %
                'Edge_Num': False, # Esconde a versão decimal crua
                'Lucro': ':.2f'
            },
            labels={'Lucro': 'Lucro Realizado (R$)', 'Edge_Num': 'Edge'},
        )
        
        # Adiciona uma linha a tracejado no marco zero (R$ 0.00) para separar perdas e ganhos
        fig_scatter.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")
        
        # Formata o eixo Y para mostrar Percentagens
        fig_scatter.layout.yaxis.tickformat = ',.1%'
        
        st.plotly_chart(fig_scatter, use_container_width=True)
