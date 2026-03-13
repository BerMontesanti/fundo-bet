import streamlit as st
import pandas as pd
import os

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Dashboard Quant Bet", page_icon="📈", layout="wide")
st.title("📈 Dashboard Analítico - Quant Bet EV")

ARQUIVO = 'historico_apostas.csv'

if not os.path.exists(ARQUIVO):
    st.warning(f"Nenhum histórico encontrado. O arquivo {ARQUIVO} ainda não foi criado pelo robô.")
    st.stop()

# Carrega os dados
df = pd.read_csv(ARQUIVO)

# Garante que as colunas de controle existem
if 'Vencedor_Partida' not in df.columns:
    df['Vencedor_Partida'] = "Pendente"
if 'Status_Aposta' not in df.columns:
    df['Status_Aposta'] = "Pendente"

# ==========================================
# 1. INSERÇÃO DE RESULTADOS (UMA LINHA POR JOGO)
# ==========================================
st.subheader("📝 Alimentar Resultados")
st.info("Digite o nome exato do time vencedor ou 'Draw' para empate. O sistema calculará os Greens/Reds de todas as casas.")

jogos_unicos = df[['Data/Hora', 'Liga', 'Jogo', 'Vencedor_Partida']].drop_duplicates(subset=['Data/Hora', 'Jogo']).copy()

jogos_editados = st.data_editor(
    jogos_unicos,
    disabled=["Data/Hora", "Liga", "Jogo"], 
    hide_index=True,
    use_container_width=True,
    key="editor_resultados"
)

if st.button("💾 Salvar Resultados", type="primary"):
    for index, row in jogos_editados.iterrows():
        jogo_id = row['Jogo']
        data_id = row['Data/Hora']
        vencedor = row['Vencedor_Partida']
        
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
    st.success("Resultados e Payouts atualizados com sucesso!")
    st.rerun() # Atualiza a página para refletir os novos dados nos gráficos

st.divider()

# ==========================================
# 2. PREPARAÇÃO DOS DADOS (LIMPEZA MATEMÁTICA)
# ==========================================
# Criamos uma cópia para não alterar a exibição visual do dataframe original
df_calc = df.copy()

# Converte strings para números
df_calc['Stake_Num'] = df_calc['Stake'].astype(str).str.replace('R$', '', regex=False).str.strip().astype(float)
df_calc['ROI_Num'] = df_calc['ROI'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Edge_Num'] = df_calc['Edge'].astype(str).str.replace('%', '', regex=False).str.strip().astype(float) / 100
df_calc['Odd_Num'] = df_calc['Odd Casa'].astype(float)

# Calcula o EV Teórico (Stake * ROI)
df_calc['Lucro_Teorico'] = df_calc['Stake_Num'] * df_calc['ROI_Num']

# Calcula o Payout Real (Lucro/Prejuízo)
def calcular_payout(row):
    if row['Status_Aposta'] == 'Green ✅':
        return row['Stake_Num'] * (row['Odd_Num'] - 1)
    elif row['Status_Aposta'] == 'Red ❌':
        return -row['Stake_Num']
    else:
        return 0.0

df_calc['Payout_Real'] = df_calc.apply(calcular_payout, axis=1)

# Filtra apenas apostas já resolvidas para as métricas de Payout
df_resolvidas = df_calc[df_calc['Status_Aposta'].isin(['Green ✅', 'Red ❌'])]

# ==========================================
# 3. PAINEL GLOBAL DE PERFORMANCE
# ==========================================
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

# ==========================================
# 4. ESTRATIFICAÇÃO POR CASA DE APOSTA
# ==========================================
st.subheader("🏦 Performance Individual por Casa de Aposta")
st.write("Análise detalhada do valor esperado (EV) e do dinheiro real no bolso (Payout) em cada casa.")

# Agrupamento e cálculos
analise_casas = df_calc.groupby('Casa').agg(
    Oportunidades=('Casa', 'count'),
    Edge_Medio=('Edge_Num', 'mean'),
    EV_Medio=('ROI_Num', 'mean'),
    EV_Absoluto=('Lucro_Teorico', 'sum'),
    Apostas_Resolvidas=('Status_Aposta', lambda x: x.isin(['Green ✅', 'Red ❌']).sum()),
    Payout_Real=('Payout_Real', 'sum')
).reset_index()

# Ordena pelo maior Payout Real e depois pelo EV
analise_casas = analise_casas.sort_values(by=['Payout_Real', 'EV_Absoluto'], ascending=[False, False])

# Formatação visual da tabela para exibição
tabela_exibicao = analise_casas.copy()
tabela_exibicao['Edge_Medio'] = (tabela_exibicao['Edge_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
tabela_exibicao['EV_Medio'] = (tabela_exibicao['EV_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
tabela_exibicao['EV_Absoluto'] = tabela_exibicao['EV_Absoluto'].apply(lambda x: f"R$ {x:.2f}")
tabela_exibicao['Payout_Real'] = tabela_exibicao['Payout_Real'].apply(lambda x: f"R$ {x:.2f}")

st.dataframe(tabela_exibicao, hide_index=True, use_container_width=True)

st.divider()

# ==========================================
# 5. HISTÓRICO COMPLETO DETALHADO
# ==========================================
with st.expander("🔍 Ver Histórico de Apostas Completo"):
    # Organiza para mostrar as resolvidas primeiro, ou as mais recentes
    st.dataframe(df, use_container_width=True)
