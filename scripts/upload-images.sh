#!/usr/bin/env bash
# upload-images.sh — Upload local images to S3 buckets

set -euo pipefail

S3_BUCKETS="boost.org.v2 stage.boost.org.v2 boost.org-cppal-dev-v2"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")/static/static-large/"

DEFAULT_DEST="/static/img/v3"
# ─────────────────────────────────────────────
# 0. PARSE COMMAND-LINE OPTIONS
# ─────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $0 [OPTION]

Upload or download image files and other static assets to/from the website S3 buckets.

Options:
  --up-sync      Upload files from /tmp/upload-images to S3 buckets.
  --down-sync    Download files from S3 stage bucket to local static directory.
  --help         Display this help and exit.

Configuration:
  The source folder for upload is /tmp/upload-images.
  The default destination for upload is /static/img/v3.
  In your .aws/credentials file, add a set of credentials:

  [upload-images]
  aws_access_key_id = <your_key_id>
  aws_secret_access_key = <your_secret_key>
EOF
}

validate_dependencies() {
  if ! command -v aws &>/dev/null; then
    echo "awscli is required. Please install it from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
  fi
}

upload_images() {
  # ─────────────────────────────────────────────
  # 1. CHECK FOR AWS CLI
  # ─────────────────────────────────────────────
  validate_dependencies

  # ─────────────────────────────────────────────
  # 2. ENSURE SOURCE FOLDER EXISTS
  # ─────────────────────────────────────────────
  if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Source folder $SOURCE_DIR does not exist. Creating it..."
    mkdir -p "$SOURCE_DIR"
  fi

  # ─────────────────────────────────────────────
  # 3. WAIT FOR FILES IN SOURCE FOLDER
  # ─────────────────────────────────────────────
  check_source_files() {
    # Returns 0 if files exist, 1 if empty
    if [[ -n "$(find "$SOURCE_DIR" -maxdepth 1 -mindepth 1 -type f 2>/dev/null)" ]]; then
      return 0
    else
      return 1
    fi
  }

  while ! check_source_files; do
    echo ""
    echo "The source folder $SOURCE_DIR is empty.  Please place files there."
    printf "Press y to continue, n to cancel: "
    read -r choice
    case "$choice" in
      [yY])
        # Re-check happens at the top of the while loop
        ;;
      [nN])
        echo "Cancelled."
        exit 0
        ;;
      *)
        echo "Please enter y or n."
        ;;
    esac
  done

  echo ""
  echo "Source files found in $SOURCE_DIR:"
  ls -1 "$SOURCE_DIR"

  # ─────────────────────────────────────────────
  # 4. PROMPT FOR DESTINATION PATH
  # ─────────────────────────────────────────────
  is_valid_dest() {
    local dest="$1"
    # Must be exactly /static/ or start with /static/ followed by more path
    if [[ "$dest" == "/static/" ]] || [[ "$dest" == /static/* ]]; then
      return 0
    else
      return 1
    fi
  }

  DEST_PATH=""
  while true; do
    echo ""
    printf "Enter the S3 destination path [default: %s]: " "$DEFAULT_DEST"
    read -r user_dest

    # Use default if user just pressed ENTER
    if [[ -z "$user_dest" ]]; then
      DEST_PATH="$DEFAULT_DEST"
    else
      DEST_PATH="$user_dest"
    fi

    if is_valid_dest "$DEST_PATH"; then
      break
    else
      echo "The upload destination should be a subfolder of /static/ (e.g. /static/img/v3).  Please try again."
    fi
  done

  echo "Destination path: $DEST_PATH"

  # ─────────────────────────────────────────────
  # 5. UPLOAD TO EACH BUCKET
  # ─────────────────────────────────────────────
  UPLOAD_FAILED=0

  for bucket in $S3_BUCKETS; do
    S3_DEST="s3://${bucket}${DEST_PATH}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Uploading to: $S3_DEST"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Capture exit code; show stdout+stderr live via tee to /dev/null trick
    set +e
    aws s3 sync --profile upload-images "$SOURCE_DIR" "$S3_DEST" 2>&1
    EXIT_CODE=$?
    set -e

    if [[ $EXIT_CODE -ne 0 ]]; then
      echo ""
      echo "The upload failed for bucket: $bucket (exit code $EXIT_CODE)"
      echo "  Source:      $SOURCE_DIR"
      echo "  Destination: $S3_DEST"
      UPLOAD_FAILED=1
    else
      echo ""
      echo "✓ Upload succeeded for bucket: $bucket"
    fi
  done

  # ─────────────────────────────────────────────
  # 6. POST-UPLOAD SUMMARY
  # ─────────────────────────────────────────────
  echo ""
  if [[ $UPLOAD_FAILED -ne 0 ]]; then
    echo "One or more uploads failed. Please review the output above for details."
    echo "  Source folder:   $SOURCE_DIR"
    echo "  Destination:     $DEST_PATH"
    echo "  Buckets:         $S3_BUCKETS"
    exit 1
  fi

  # ─────────────────────────────────────────────
  # 7. OFFER TO DELETE LOCAL TMP FILES
  # ─────────────────────────────────────────────
  echo "The files uploaded successfully."
  echo ""
  printf "We recommend deleting the local files in %s to clear them out for next time.  Delete local tmp files? [Y/n]: " "$SOURCE_DIR"
  read -r del_choice

  case "${del_choice:-Y}" in
    [nN])
      echo "Skipping deletion. Local files remain in $SOURCE_DIR."
      ;;
    *)
      echo "Deleting files in $SOURCE_DIR..."
      find "$SOURCE_DIR" -maxdepth 1 -mindepth 1 -type f -delete
      echo "Local files deleted."
      ;;
  esac

  echo ""
  echo "Done."
}

download_images() {
  BUCKET='stage.boost.org.v2'

  validate_dependencies

  if echo "${S3_BUCKETS}" | grep -q -w "${BUCKET}"; then
      aws s3 sync "s3://${BUCKET}/static/"  "${SOURCE_DIR}" --profile 'upload-images';
      echo "All missing or outdated static items synced.";
  else
      echo "Bucket name invalid.";
      exit 1;
  fi
}



while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      usage
      exit 0
      ;;
    --up-sync)
      upload_images
      exit $?
      ;;
    --down-sync)
      download_images
      exit $?
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done
