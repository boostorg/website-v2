#!/bin/bash
set -eu
[ -f ".env" ] || { echo "Error: .env file not found"; exit 1; }
source .env

download_media_file() {
    # download all files from the PROD_MEDIA_CONTENT bucket and copy to Docker container
    [ -z "$PROD_MEDIA_CONTENT_AWS_ACCESS_KEY_ID" ] && {
      echo "Error: PROD_MEDIA_CONTENT_AWS_ACCESS_KEY_ID not set in .env";
      return 1;
    }
    [ -z "$PROD_MEDIA_CONTENT_AWS_SECRET_ACCESS_KEY" ] && {
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

    local media_temp_dir=$(mktemp -d)
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
    # download the latest database dump and restore it to the db
    [ -z "$PROD_DB_DUMP_URL" ] && {
      echo "Error: PROD_DB_DUMP_URL not set in .env";
      return 1;
    }
    [ -z "$PROD_DB_DUMP_FILE_WILDCARD" ] && {
      echo "Error: PROD_DB_DUMP_FILE_WILDCARD not set in .env";
      return 1;
    }

    local db_temp_dir=$(mktemp -d)
    trap 'rm -rf "$db_temp_dir"' RETURN
    local dump_file_path=""

    echo "Finding latest database dump..."
    # Get a list of all dump files
    gcloud storage ls "$PROD_DB_DUMP_URL$PROD_DB_DUMP_FILE_WILDCARD" > "$db_temp_dir/all_files.txt" || {
        echo "Failed to list files at $PROD_DB_DUMP_URL";
        return 1;
    }

    [ -s "$db_temp_dir/all_files.txt" ] || {
        echo "No files found at $PROD_DB_DUMP_URL";
        return 1;
    }

    grep "\.dump$" "$db_temp_dir/all_files.txt" | sort -r > "$db_temp_dir/dump_files.txt"
    [ -s "$db_temp_dir/dump_files.txt" ] || {
        echo "No .dump files found at $PROD_DB_DUMP_URL";
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
    DB_NAME=$(grep PGDATABASE .env | cut -d= -f2)
    DB_USER=$(grep PGUSER .env | cut -d= -f2)
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
    docker compose exec db bash -c "pg_restore -U $DB_USER -d $DB_NAME -v --no-owner --no-privileges /tmp/$DUMP_FILENAME" || true
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

download_latest_db_dump || {
    echo "Failed to download and restore latest database dump";
    exit 1;
}

download_media_file || {
    echo "Failed to download media files from bucket"
    exit 1
}
npm install
npm run build
echo "Run: 'docker compose up -d' to restart your services"
echo "If you get an error related to profile images when loading the site, clear all cookies and try again"
echo "You should now able to log into the admin interface with username: 'superadmin' and password: 'foobarone'"
