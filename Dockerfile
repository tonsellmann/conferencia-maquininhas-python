# O painel de conferência num contêiner: Python 3.14, pandas, Django e gunicorn.
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBUG=0 \
    BANCO=/dados/painel.sqlite3 ESTATICOS=/estaticos
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY conferencia ./conferencia
COPY painel ./painel
COPY painel_site ./painel_site
COPY exemplos ./exemplos
COPY manage.py docker-entrypoint.sh ./
RUN useradd --uid 10001 --no-create-home painel && mkdir -p /dados /estaticos && chown painel:painel /dados /estaticos
USER painel
EXPOSE 8000
VOLUME ["/dados", "/estaticos"]
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=2).status == 200 else 1)"
ENTRYPOINT ["sh", "docker-entrypoint.sh"]
