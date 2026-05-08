import polars as pl

print("Lettura dei file in corso...")

# I file log non hanno intestazione, quindi assegniamo i nomi manualmente
col_names = ["timestamp", "rule_id", "priority", "sensor_id", "value"]

df_pd = pl.read_csv("alarms_custom_pd.log", separator=";", has_header=False, new_columns=col_names)
df_pl = pl.read_csv("alarms_custom_pl.log", separator=";", has_header=False, new_columns=col_names)

# 2. Rimuoviamo eventuali duplicati identici
df_pd_unique = df_pd.unique(subset=['timestamp', 'rule_id', 'sensor_id'])

print(f"Allarmi originali Pandas: {df_pd.height}")
print(f"Allarmi Pandas de-duplicati: {df_pd_unique.height}")
print(f"Allarmi Polars: {df_pl.height}")

# 3. Troviamo gli allarmi che sono in Pandas ma NON in Polars (Anti-Join)
diff = df_pd_unique.join(df_pl, on=['timestamp', 'rule_id', 'sensor_id'], how='anti')

print(f"\nAllarmi presenti in Pandas ma ASSENTI in Polars: {diff.height}")
if diff.height > 0:
    print("\nEcco i primi 5 allarmi anomali:")
    print(diff.head(5))