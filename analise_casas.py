import pandas as pd

def analisar_historico():
    try:
        # Carrega o banco de dados salvo pelo seu bot principal
        df = pd.read_csv('historico_apostas.csv')
    except FileNotFoundError:
        print("❌ Arquivo 'historico_apostas.csv' não encontrado. Certifique-se de que o bot já rodou e salvou apostas.")
        return

    print(f"📊 Analisando um total de {len(df)} apostas registradas no Forward Testing...\n")

    # 1. Limpar e converter os textos ("R$", "%") para números reais (float)
    df['Stake_Valor'] = df['Stake'].str.replace('R$', '', regex=False).str.strip().astype(float)
    df['ROI_Valor'] = df['ROI'].str.replace('%', '', regex=False).str.strip().astype(float) / 100
    df['Edge_Valor'] = df['Edge'].str.replace('%', '', regex=False).str.strip().astype(float) / 100
    
    # 2. Calcular o Lucro Teórico (EV) de cada aposta (Stake * ROI)
    df['Lucro_Teorico_EV'] = df['Stake_Valor'] * df['ROI_Valor']

    # 3. Agrupar os dados ESTRATIFICADOS POR CASA DE APOSTA
    analise = df.groupby('Casa').agg(
        Total_Apostas=('Casa', 'count'),
        Volume_Investido=('Stake_Valor', 'sum'),
        Edge_Medio=('Edge_Valor', 'mean'),
        ROI_Medio=('ROI_Valor', 'mean'),
        Lucro_Teorico_EV=('Lucro_Teorico_EV', 'sum')
    ).reset_index()

    # 4. Ordenar das casas mais lucrativas para as menos lucrativas
    analise = analise.sort_values(by='Lucro_Teorico_EV', ascending=False)

    # 5. Formatar a tabela para ficar bonita na hora de ler
    analise_formatada = analise.copy()
    analise_formatada['Volume_Investido'] = analise['Volume_Investido'].apply(lambda x: f"R$ {x:.2f}")
    analise_formatada['Edge_Medio'] = (analise['Edge_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    analise_formatada['ROI_Medio'] = (analise['ROI_Medio'] * 100).apply(lambda x: f"{x:.2f}%")
    analise_formatada['Lucro_Teorico_EV'] = analise['Lucro_Teorico_EV'].apply(lambda x: f"R$ {x:.2f}")

    # Exibir o resultado no terminal/console
    print(analise_formatada.to_string(index=False))
    
    # Salvar a análise em um novo CSV para você poder abrir no Excel/Google Sheets
    analise_formatada.to_csv('relatorio_por_casa.csv', index=False)
    print("\n✅ Relatório salvo com sucesso como 'relatorio_por_casa.csv'!")

if __name__ == "__main__":
    analisar_historico()
