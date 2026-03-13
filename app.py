import streamlit as st
import pandas as pd
import os
from github import Github

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E LOGIN
# ==========================================
st.set_page_config(page_title="Dashboard Quant Bet", page_icon="📈", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acesso Restrito - Quant Bet EV")
    senha_digitada = st.text_input("Digite a senha para acessar o painel:", type="password")
    if st.button("Entrar"):
        if senha_digitada == st.secrets["SENHA_SITE"]:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("❌ Senha incorreta!")
    st.stop() 

st.title("📈 Dashboard Analítico - Quant Bet EV")

ARQUIVO = 'historico_apostas.csv'

if not os.path.exists(ARQUIVO):
    st.warning(f"Nenhum histórico encontrado. O arquivo {ARQUIVO} ainda não foi criado pelo robô.")
    st.stop()

df = pd.read_csv(ARQUIVO)

if 'Vencedor_Partida' not in df.columns:
    df['Vencedor_Partida'] = "Pendente"
if 'Status_Aposta' not in df.columns:
    df['Status_Aposta'] = "Pendente"

# ==========================================
# 1. INSERÇÃO DE RESULTADOS (DROPDOWNS EXCLUSIVOS)
# ==========================================
st.subheader("📝 Alimentar Resultados")
st.info("Selecione o vencedor no menu. As opções estão limitadas apenas aos times que jogaram.")

jogos_unicos = df[['Data/Hora', 'Liga', 'Jogo', 'Vencedor_Partida']].drop_duplicates(subset=['Data/Hora', 'Jogo']).copy()

# Ordena para colocar os jogos "Pendentes" no topo da lista visual
jogos_unicos['Ordem'] = jogos_unicos['Vencedor_Partida'].apply(lambda x: 0 if x == 'Pendente' else 1)
jogos_unicos = jogos_unicos.sort_values(by=['Ordem', 'Data/Hora'], ascending=[True, False])

with st.form("form_resultados"):
    novos_resultados = []
    
    for index, row in jogos_unicos.iterrows():
        # Lógica para extrair os times do nome do jogo
        if ' x ' in row['Jogo']:
            time_casa, time_fora = row['Jogo'].split(' x ')
            opcoes = ["Pendente", time_casa, time_fora, "Draw"]
        else:
            opcoes = ["Pendente", "Draw"]
            
        valor_atual = str(row['Vencedor_Partida']).strip()
        if valor_atual not in opcoes:
            opcoes.append(valor_atual)
            
        idx_padrao = opcoes.index(valor_atual) if valor_atual in opcoes else 0
        
        # Desenha a linha da partida com duas colunas
        col_txt, col_sel = st.columns([3, 2])
        with col_txt:
            st.write(f"⚽ **{row['Jogo']}**")
            st.caption(f"🏆 {row['Liga']} | ⏰ {row['Data/Hora']}")
        with col_sel:
            escolha = st.selectbox(
                "Vencedor",
                options=opcoes,
                index=idx_padrao,
                key=f"sel_{row['Jogo']}_{row['Data/Hora']}",
                label_visibility="collapsed"
            )
            
        novos_resultados.append({
            'Jogo': row['Jogo'],
            'Data/Hora': row['Data/Hora'],
            'Vencedor_Partida': escolha
        })
        st.markdown("---")
        
    salvar_btn = st.form_submit_button("💾 Salvar Resultados na Nuvem", type="primary")

# ==========================================
# 2. SALVAR NO GITHUB
# ==========================================
if salvar_btn:
    with st.spinner('A calcular e a enviar para o GitHub...'):
        for item in novos_resultados:
            jogo_id = item['Jogo']
            data_id = item['Data/Hora']
            vencedor = item['Vencedor_Partida']
            
            mask = (df['Jogo'] == jogo_id) & (df['Data/Hora'] == data_id)
            df.loc[mask, 'Vencedor_Partida'] = vencedor
            
            for idx in df[mask].index:
                selecao_apostada = str(df.at[idx, 'Seleção']).strip()
                vencedor_limpo = str(vencedor).strip()
                
                if vencedor_limpo == "Pendente" or vencedor_limpo == "" or vencedor_limpo == "nan":
                    df.at[idx, 'Status_Aposta'] = "Pendente"
                elif selecao_apostada == vencedor_limpo:
                    df.at[idx, 'Status_Aposta'] = "Green ✅"
                else:
                    df.at[idx, 'Status_Aposta'] = "Red ❌"

        df.to_csv(ARQUIVO, index=False)
        
        try:
            g = Github(st.secrets["GITHUB_TOKEN"])
            repo = g.get_repo(st.secrets["REPO_NAME"])
            contents = repo.get_contents(ARQUIVO)
            novo_csv = df.to_csv(index=False)
            
            repo.update_file(
                contents.path, 
                "🤖 Atualizando resultados via Painel Web", 
                novo_csv, 
                contents.sha
            )
            st.success("Resultados salvos com sucesso e sincronizados com o robô!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao sincronizar com o GitHub: {e}")

st.divider()

# ==========================================
# 3. PREPARAÇÃO DOS DADOS E DASHBOARD
# ==========================================
df_calc = df.copy()
df_calc['Stake_Num'] = df_calc['Stake'].astype(str).str.replace('R$', '', regex=False).str.strip().astype(float)
df_calc['ROI_Num'] = df_calc['ROI'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Edge_Num'] = df_calc['Edge'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Odd_Num'] = df_calc['Odd Casa'].astype(float)
df_calc['Lucro_Teorico'] = df_calc['Stake_Num'] * df_calc['ROI_Num']

def calcular_payout(row):
    if row['Status_Aposta'] == 'Green ✅':
        return row['Stake_Num'] * (row['Odd_Num'] - 1)
    elif row['Status_Aposta'] == 'Red ❌':
        return -row['Stake_Num']
    else:
        return 0.0

df_calc['Payout_Real'] = df_calc.apply(calcular_payout, axis=1)
df_resolvidas = df_calc[df_calc['Status_Aposta'].isin(['Green ✅', 'Red ❌'])]

# PAINEL GLOBAL
st.subheader("🌍 Visão Global da Estratégia")
col1, col2, col3, col4 = st.columns(4)
total_apostas = len(df_calc)
ev_total = df_calc['Lucro_Teorico'].sum()
payout_total = df_calc['Payout_Real'].sum()
taxa_acerto = (len(df_resolvidas[df_resolvidas['Status_Aposta'] == 'Green ✅']) / len(df_resolvidas) * 100) if len(df_resolvidas) > 0 else 0.0

col1.metric("Total de Oportunidades", f"{total_apostas}")
col2.metric("EV Acumulado (Teórico)", f"R$ {ev_total:.2f}")
col3.metric("Payout Global (Real)", f"R$ {payout_total:.2f}", delta=f"R$ {payout_total:.2f}")
col4.metric("Taxa de Acerto (Win Rate)", f"{taxa_acerto:.1f}%")

st.divider()

# ESTRATIFICAÇÃO POR CASA
st.subheader("🏦 Performance Individual por Casa de Aposta")
analise_casas = df_calc.groupby('Casa').agg(
    Oportunidades=('Casa', 'count'),
    Edge_Medio=('Edge_Num', 'mean'),
    EV_Medio=('ROI_Num', 'mean'),
    EV_Absoluto=('Lucro_Teorico', 'sum'),
    Apostas_Resolvidas=('Status_Aposta', lambda x: x.isin(['Green ✅', 'Red ❌']).sum()),
    Payout_Real=('Payout_Real', 'sum')
).reset_index()

analise_casas = analise_casas.sort_values(by=['Payout_Real', 'EV_Absoluto'], ascending=[False, False])

tabela_exibicao = analise_casas.copy()
tabela_exibicao['Edge_Medio'] = (tabela_exibicao['Edge_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
tabela_exibicao['EV_Medio'] = (tabela_exibicao['EV_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
tabela_exibicao['EV_Absoluto'] = tabela_exibicao['EV_Absoluto'].apply(lambda x: f"R$ {x:.2f}")
tabela_exibicao['Payout_Real'] = tabela_exibicao['Payout_Real'].apply(lambda x: f"R$ {x:.2f}")

st.dataframe(tabela_exibicao, hide_index=True, use_container_width=True)

st.divider()

with st.expander("🔍 Ver Histórico de Apostas Completo"):
    st.dataframe(df, use_container_width=True)
