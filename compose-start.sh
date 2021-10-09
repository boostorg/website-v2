#!/usr/bin/env bash
#
# This script is used to start our Django WSGI process (gunicorn in this case)
# for use with docker-compose.  In deployed or production scenarios you would
# not necessarily use this exact setup.
#
./docker/wait-for-it.sh -h db -p 5432 -t 20 -- python manage.py migrate --noinput

python manage.py collectstatic --noinput

gunicorn -c gunicorn.conf.py --log-level INFO --reload -b 0.0.0.0:8000 config.wsgi
