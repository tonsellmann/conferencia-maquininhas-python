#!/bin/sh
# Antes de abrir as portas: o banco atualizado e os arquivos estáticos onde o proxy os serve.
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
exec gunicorn painel_site.wsgi --bind 0.0.0.0:8000 --workers 2 --access-logfile - --forwarded-allow-ips '*'
