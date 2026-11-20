#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn electronic_components.wsgi \
    --workers 2 \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -
