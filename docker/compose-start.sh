#!/usr/bin/env bash
#
# This script is used to start our Django WSGI process (gunicorn in this case)
# for use with docker-compose.  In deployed or production scenarios you would
# not necessarily use this exact setup.
#
$DOCKER_DIR/wait-for-it.sh -h db -p $PGPORT -t 20 -- $PYTHON manage.py migrate --noinput

$PYTHON manage.py collectstatic --noinput

# gunicorn -c gunicorn.conf.py --log-level INFO --reload -b 0.0.0.0:$WEB_PORT config.wsgi
$PYTHON manage.py runserver 0.0.0.0:$WEB_PORT
