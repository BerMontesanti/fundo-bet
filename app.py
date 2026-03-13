import streamlit as st
import pandas as pd
import os

# Configuração da página do site
st.set_page_config(page_title="Painel Quant Bet", page_icon="📊", layout="wide")

st.title("📊 Painel de Resultados - Quant Bet EV")
st.markdown("Alimente o resultado da partida uma única vez. O sistema calculará automaticamente os Greens e Reds para todas as casas de apostas!")

ARQUIVO = 'historico_apostas.csv'

# Verifica se o banco de dados existe
if not os.path.exists(ARQUIVO):
    st.warning(f"Nenhum histórico encontrado. O arquivo {ARQUIVO} ainda não foi criado pelo robô.")
    st.stop()

# Carrega os dados
df = pd.read_csv(ARQUIVO)

# Cria as colunas de controle se elas ainda não existirem no seu CSV
if 'Vencedor_Partida' not in df.columns:
    df['Vencedor_Partida'] = "Pendente"
if 'Status_Aposta' not in df.columns:
    df['Status_Aposta'] = "Pendente"

# ==========================================
# 1. ISOLAR UMA LINHA POR PARTIDA
# ==========================================
# Removemos as duplicatas usando Data e Jogo como referência
jogos_unicos = df[['Data/Hora', 'Liga', 'Jogo', 'Vencedor_Partida']].drop_duplicates(subset=['Data/Hora', 'Jogo']).copy()

st.subheader("📝 Inserir Resultados")
st.info("💡 **Como preencher:** Digite o nome exato do time que venceu (igual aparece no nome do jogo) ou digite **Draw** para empate.")

# Exibe a tabela editável no site
jogos_editados = st.data_editor(
    jogos_unicos,
    disabled=["Data/Hora", "Liga", "Jogo"], # Impede edição destas colunas
    hide_index=True,
    use_container_width=True
)

# ==========================================
# 2. BOTÃO DE SALVAR E CALCULAR GREENS/REDS
# ==========================================
if st.button("💾 Salvar Resultados e Calcular Histórico", type="primary"):
    
    # Percorre cada jogo que você editou no painel
    for index, row in jogos_editados.iterrows():
        jogo_id = row['Jogo']
        data_id = row['Data/Hora']
        vencedor = row['Vencedor_Partida']
        
        # Encontra todas as apostas no DF principal que pertencem a este jogo
        mask = (df['Jogo'] == jogo_id) & (df['Data/Hora'] == data_id)
        df.loc[mask, 'Vencedor_Partida'] = vencedor
        
        # Calcula o Green ou Red para CADA casa de aposta automaticamente
        for idx in df[mask].index:
            selecao_apostada = df.at[idx, 'Seleção']
            
            if vencedor == "Pendente" or vencedor == "":
                df.at[idx, 'Status_Aposta'] = "Pendente"
            elif selecao_apostada == vencedor:
                df.at[idx, 'Status_Aposta'] = "Green ✅"
            else:
                df.at[idx, 'Status_Aposta'] = "Red ❌"

    # Salva as alterações definitivamente no CSV
    df.to_csv(ARQUIVO, index=False)
    st.success("Resultados salvos com sucesso! O histórico foi atualizado e os Greens/Reds foram calculados.")
    st.balloons() # Uma pequena animação de comemoração na tela 🎉

st.divider()

# ==========================================
# 3. EXIBIR O HISTÓRICO COMPLETO
# ==========================================
st.subheader("🗄️ Histórico Completo Específico (Automático)")
st.write("Veja como as suas apostas ficaram divididas pelas casas:")
# Mostra o arquivo completo com as novas marcações de Green/Red
st.dataframe(df, use_container_width=True)
