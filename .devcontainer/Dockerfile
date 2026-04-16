# Sostituisci "3.10" con la versione esatta che sta usando Domenico
FROM python:3.10-slim

# Evita che Python crei file .pyc spazzatura e forza i log sul terminale
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Imposta la cartella di lavoro dentro il container
WORKDIR /workspace

# Updates system and installs git
RUN apt-get update && apt-get install -y git

# Copia SOLO il file dei requisiti all'inizio (sfrutta la cache di Docker)
COPY requirements.txt .

# Aggiorna pip e installa le dipendenze
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# (Opzionale) Installa strumenti utili per il debug che potrebbero non essere nel txt
RUN pip install pytest

# NON copiamo il resto del codice qui (COPY . .) perché per lo sviluppo 
# lo monteremo "in diretta" dal tuo Mac per non dover ricostruire l'immagine ogni volta.

# Avvia una shell di default
CMD ["bash"]
