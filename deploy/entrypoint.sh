#!/bin/sh
set -eu
python manage.py migrate --noinput
exec waitress-serve --listen=0.0.0.0:8000 --threads=8 --channel-timeout=30 --max-request-body-size=16384 config.wsgi:application
