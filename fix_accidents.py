import pandas as pd

df = pd.read_csv('data/traffic_analysis_final.csv')

# Converti TUTTI i valori a interi (moltiplicati per 100)
df['ACCIDENTS_PER_CAPITA'] = (df['ACCIDENTS_PER_CAPITA'] * 100).round(0).astype(int)

df.to_csv('data/traffic_analysis_final.csv', index=False)

print('✅ CONVERTITO A INTERI')
print(df[df['Comune'].isin(['Ponte Gardena/Waidbruck', 'Castel Condino', 'Bard', 'Priero'])][['Comune', 'ACCIDENTS_PER_CAPITA']])