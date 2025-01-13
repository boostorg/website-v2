#!/bin/bash
set -eu

# Import Production Data Locally

# Instructions
#
# 1. Install prerequisites (Docker, Just, etc), either manually or using ./scripts/dev-bootstrap-macos.sh
# 2. Run this script with --help to see options. ./scripts/load_production_data.sh --help
#
#

# READ IN COMMAND-LINE OPTIONS
TEMP=$(getopt -o h:: --long help::,lists::,only-lists:: -- "$@")
eval set -- "$TEMP"

# extract options and their arguments into variables.
while true ; do
    case "$1" in
        -h|--help)
            helpmessage="""
usage: load_production_data.sh [-h] [--lists] [--only-lists]

Load production data. By default this will import the main website database.

optional arguments:
  -h, --help            Show this help message and exit
  --lists               Import mailing list dbs also.
  --only-lists		Import mailing list database and not the main web database.
"""

            echo ""
            echo "$helpmessage" ;
            echo ""
            exit 0
            ;;
        --lists)
            lists_option="yes" ; shift 2 ;;
        --only-lists)
            lists_option="yes" ; skip_web_option="yes" ; shift 2 ;;
        --) shift ; break ;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done

[ -f ".env" ] || { echo "Error: .env file not found"; exit 1; }
# shellcheck disable=SC1091
source .env

download_media_file() {
    # download all files from the PROD_MEDIA_CONTENT bucket and copy to Docker container
    # todo: remove the changeme check and remove 'changeme' as the default, use nothing instead
    [[ -z "$PROD_MEDIA_CONTENT_AWS_ACCESS_KEY_ID" || "$PROD_MEDIA_CONTENT_AWS_ACCESS_KEY_ID" == "changeme" ]] && {
      echo "Error: PROD_MEDIA_CONTENT_AWS_ACCESS_KEY_ID not set in .env";
      return 1;
    }
    [[ -z "$PROD_MEDIA_CONTENT_AWS_SECRET_ACCESS_KEY" || "$PROD_MEDIA_CONTENT_AWS_SECRET_ACCESS_KEY" = "changeme" ]] && {
      echo "Error: PROD_MEDIA_CONTENT_AWS_SECRET_ACCESS_KEY not set in .env";
      return 1;
    }
    [ -z "$PROD_MEDIA_CONTENT_BUCKET_NAME" ] && {
      echo "Error: PROD_MEDIA_CONTENT_BUCKET_NAME not set in .env";
      return 1;
    }
    [ -z "$PROD_MEDIA_CONTENT_REGION" ] && {
      echo "Error: PROD_MEDIA_CONTENT_REGION not set in .env";
      return 1;
    }

    local -r media_temp_dir=$(mktemp -d)
    trap 'rm -rf "$media_temp_dir"' RETURN

    echo "Downloading all media files from bucket: $PROD_MEDIA_CONTENT_BUCKET_NAME to: $media_temp_dir"

    AWS_ACCESS_KEY_ID="$PROD_MEDIA_CONTENT_AWS_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$PROD_MEDIA_CONTENT_AWS_SECRET_ACCESS_KEY" \
    aws s3 sync "s3://$PROD_MEDIA_CONTENT_BUCKET_NAME/" "$media_temp_dir" \
        --region "$PROD_MEDIA_CONTENT_REGION" || {
            echo "Failed to download media files from bucket: $PROD_MEDIA_CONTENT_BUCKET_NAME";
            return 1;
        }

    echo "Successfully downloaded all media files to: $media_temp_dir"

    if ! docker compose ps | grep -q "web.*running"; then
        echo "Starting web container..."
        docker compose up -d web
        echo "Waiting for web container to be ready..."
        sleep 5
    fi

    echo "Copying media files to Docker container..."
    docker compose exec -T web mkdir -p /code/media
    docker compose cp "$media_temp_dir/." web:/code/media/

    echo "Media files successfully copied to Docker container"
    return 0
}

download_latest_db_dump() {
    if [ "$1" = "web_db" ]; then
        DB_URL="PROD_DB_DUMP_URL"
        DB_WILDCARD="PROD_DB_DUMP_FILE_WILDCARD"
        DB_NAME=$(grep PGDATABASE .env | cut -d= -f2)
        DB_USER=$(grep PGUSER .env | cut -d= -f2)
    elif [ "$1" = "lists_core_db" ]; then
        DB_URL="PROD_LISTS_CORE_DB_DUMP_URL"
        DB_WILDCARD="PROD_LISTS_CORE_DB_DUMP_FILE_WILDCARD"
        DB_NAME="lists_production_core"
        DB_USER=$(grep PGUSER .env | cut -d= -f2)
    elif [ "$1" = "lists_web_db" ]; then
        DB_URL="PROD_LISTS_WEB_DB_DUMP_URL"
        DB_WILDCARD="PROD_LISTS_WEB_DB_DUMP_FILE_WILDCARD"
        DB_NAME="lists_production_web"
        DB_USER=$(grep PGUSER .env | cut -d= -f2)
    else
        echo "Type of db dump not specified. Exiting"
        exit 1
    fi

    # download the latest database dump and restore it to the db
    [ -z "${!DB_URL}" ] && {
      echo "Error: ${!DB_URL} not set in .env";
      return 1;
    }
    [ -z "${!DB_WILDCARD}" ] && {
      echo "Error: ${!DB_WILDCARD} not set in .env";
      return 1;
    }

    local -r db_temp_dir=$(mktemp -d)
    echo "db_temp_dir is $db_temp_dir"
    trap 'rm -rf "$db_temp_dir"' RETURN
    # not used: local dump_file_path=""

    echo "Finding latest database dump..."
    # Get a list of all dump files
    gcloud storage ls "${!DB_URL}${!DB_WILDCARD}" > "$db_temp_dir/all_files.txt" || {
        echo "Failed to list files at ${!DB_URL}";
        return 1;
    }

    [ -s "$db_temp_dir/all_files.txt" ] || {
        echo "No files found at ${!DB_URL}";
        return 1;
    }

    grep "\.dump$" "$db_temp_dir/all_files.txt" | sort -r > "$db_temp_dir/dump_files.txt"
    [ -s "$db_temp_dir/dump_files.txt" ] || {
        echo "No .dump files found at ${!DB_URL}";
        return 1;
    }

    LATEST_DUMP=$(head -n 1 "$db_temp_dir/dump_files.txt")
    echo "Latest dump file: $LATEST_DUMP"
    DUMP_FILENAME=$(basename "$LATEST_DUMP")
    echo "Downloading $DUMP_FILENAME..."

    gcloud storage cp --project=boostorg-project1 "$LATEST_DUMP" "$db_temp_dir/$DUMP_FILENAME" || {
        echo "Failed to download $LATEST_DUMP";
        return 1;
    }

    echo "Successfully downloaded database dump: $DUMP_FILENAME"

    echo "Restoring database..."
    echo "Using database: $DB_NAME and user: $DB_USER"

    echo "Stopping all services..."
    docker compose down
    echo "Starting database service..."
    docker compose up -d db web
    echo "Waiting for database to be ready..."
    sleep 5

    echo "Recreating database..."
    # kill connections to the database
    docker compose exec db bash -c "psql -U $DB_USER -d template1 -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';\""
    sleep 2
    docker compose exec db bash -c "psql -U $DB_USER -d template1 -c \"DROP DATABASE IF EXISTS $DB_NAME;\""
    docker compose exec db bash -c "psql -U $DB_USER -d template1 -c \"CREATE DATABASE $DB_NAME;\""
    echo "Restoring database from dump..."
    docker compose cp "$db_temp_dir/$DUMP_FILENAME" "db:/tmp/$DUMP_FILENAME"
    docker compose exec db bash -c "pg_restore -U $DB_USER -d $DB_NAME -v --no-owner --no-privileges /tmp/$DUMP_FILENAME"
    # apply any migrations newer than our dumped database
    docker compose exec web bash -c "./manage.py migrate"
    # update the database to delete all rows from socialaccount_social app, which need to be configured differently locally
    echo "Deleting all rows from socialaccount_socialapp table and setting fake passwords..."
    docker compose exec web bash -c "./manage.py shell -c 'from allauth.socialaccount.models import SocialApp; SocialApp.objects.all().delete()'"
    just manage "set_fake_passwords --password=test"
    docker compose exec web bash -c "DJANGO_SUPERUSER_USERNAME=superadmin DJANGO_SUPERUSER_EMAIL=superadmin@boost.org DJANGO_SUPERUSER_PASSWORD=foobarone ./manage.py createsuperuser --noinput" || true
    echo "Database restored successfully from $DUMP_FILENAME"

    return 0
}

if [ "${skip_web_option:-}" != "yes" ]; then
    download_latest_db_dump web_db || {
        echo "Failed to download and restore latest database dump";
        exit 1;
    }
fi

if [ "${lists_option:-}" = "yes" ]; then
    download_latest_db_dump lists_web_db || {
        echo "Failed to download and restore latest lists_web_db dump";
        exit 1;
    }
    download_latest_db_dump lists_core_db || {
        echo "Failed to download and restore latest lists_core_db dump";
        exit 1;
    }
fi

download_media_file || {
    echo "Failed to download media files from bucket"
    exit 1
}
npm install
npm run build
echo "Run: 'docker compose up -d' to restart your services"
echo "If you get an error related to profile images when loading the site, clear all cookies and try again"
echo "You should now able to log into the admin interface with username: 'superadmin@boost.org' and password: 'foobarone'"
