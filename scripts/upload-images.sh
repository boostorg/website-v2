#!/usr/bin/env bash
# upload-images.sh — Upload local images to S3 buckets

set -euo pipefail

# ─────────────────────────────────────────────
# 0. PARSE COMMAND-LINE OPTIONS
# ─────────────────────────────────────────────
usage() {
  cat <<'EOF'
This script is used to upload image files and other static assets to the website S3 buckets.
The source folder is /tmp/upload-images and the destination folder may be selected during the
process (default is /static/img/v3). In your .aws/credentials file, add a set of credentials
[upload-images]
aws_access_key_id =
aws_secret_access_key =
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--help]"
      exit 1
      ;;
  esac
  shift
done

# ─────────────────────────────────────────────
# 1. CHECK FOR AWS CLI
# ─────────────────────────────────────────────
if ! command -v aws &>/dev/null; then
  echo "awscli is required. Please install it from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  exit 1
fi

# ─────────────────────────────────────────────
# 2. CONFIGURATION
# ─────────────────────────────────────────────
S3_BUCKETS="boost.org.v2 stage.boost.org.v2 boost.org-cppal-dev-v2"
SOURCE_DIR="/tmp/upload-images"
DEFAULT_DEST="/static/img/v3"

# ─────────────────────────────────────────────
# 3. ENSURE SOURCE FOLDER EXISTS
# ─────────────────────────────────────────────
if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source folder $SOURCE_DIR does not exist. Creating it..."
  mkdir -p "$SOURCE_DIR"
fi

# ─────────────────────────────────────────────
# 4. WAIT FOR FILES IN SOURCE FOLDER
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
# 5. PROMPT FOR DESTINATION PATH
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
# 6. UPLOAD TO EACH BUCKET
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
  aws s3 cp --recursive --profile upload-images "$SOURCE_DIR" "$S3_DEST" 2>&1
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
# 7. POST-UPLOAD SUMMARY
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
# 8. OFFER TO DELETE LOCAL TMP FILES
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
exit 0
