# ISMaiLa — image de l'application
#
# Python 3.12 : la 3.14 ne compile pas plusieurs dependances du projet.
# L'image "slim" suffit, aucune carte graphique n'est utilisee.

FROM python:3.12-slim

# Variables d'execution
#   PYTHONUNBUFFERED : les journaux sortent immediatement, sans tampon,
#                      sinon "docker compose logs" affiche avec du retard.
#   HF_HOME          : le modele de vectorisation (450 Mo) se telecharge ici.
#                      Monte en volume, il n'est pas retelecharge a chaque
#                      reconstruction de l'image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/app/.cache/huggingface

WORKDIR /app

# Dependances systeme minimales. curl sert au controle de sante.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Les dependances d'abord, le code ensuite : Docker met en cache cette
# couche, et une modification du code ne relance pas l'installation.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Compte sans privileges : un conteneur ne doit pas tourner en root.
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /home/app/.cache/huggingface \
 && chown -R app:app /app /home/app

COPY --chown=app:app . .

USER app

EXPOSE 8501

# Streamlit doit ecouter sur 0.0.0.0, pas sur localhost : sinon il n'est
# joignable que depuis l'interieur du conteneur.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
