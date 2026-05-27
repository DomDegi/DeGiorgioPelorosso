# 🚀 AstraLog-HPC: Guida Operativa Completa

Questa guida contiene tutti i comandi necessari per gestire una sessione di calcolo sul cluster Galileo100 (CINECA), dalla preparazione dei file alla pulizia finale.

---

## 📂 1. Preparazione Ambiente (da Git a HOME)
Esegui questi comandi per aggiornare i file operativi partendo dal repository locale aggiornato.

```bash
# Entra nella cartella del repository Git
cd ~/DegiorgioPelorosso

# Assicurati che le directory di lavoro esistano nella HOME
mkdir -p ~/inputs ~/results

# Copia i file di configurazione (Sensori e Regole)
cp config/Current_sensors_sat_alpha.yaml ~/inputs/
cp config/Current_rules_sat_alpha.json ~/inputs/

# Copia il dataset di telemetria (CSV)
cp csv_input/export_sat_alpha_custom_no_corruption.csv ~/inputs/

# Copia gli script di sottomissione (job.sh e submit.sh) nella HOME
cp job.sh submit.sh ~/

# Torna nella HOME per gestire l'esecuzione
cd ~/

# Rendi lo script di sottomissione eseguibile (se non già fatto)
chmod +x submit.sh

# Avvia il processo (scarica l'immagine SIF e lancia sbatch)
./submit.sh

# Controlla lo stato dei tuoi job in coda
squeue -u $USER

# Leggi il log dell'ultimo job (sostituisci l'ID o usa l'asterisco)
cat astralog_run_*.log

# Elenca i file prodotti nella cartella dei risultati
ls -la ~/astralog_results_*/

# Rimuove tutti i log di esecuzione e le cartelle dei risultati generate
rm -rf ~/astralog_*

# Svuota le cartelle temporanee di input e results
rm -rf ~/inputs/*
rm -rf ~/results/*

# (Opzionale) Rimuove l'immagine del container Singularity
# rm ~/astralog-hpc.sif
```
