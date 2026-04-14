#!/usr/bin/env bash
# sync-large-static-images.sh — Upload local images to S3 buckets

set -euo pipefail

DEFAULT_BUCKET="stage.boost.org.v2"
S3_BUCKETS="boost.org.v2 boost.org-cppal-dev-v2 ${DEFAULT_BUCKET}"
AWS_PROFILE='sync-boost-images'
DEFAULT_DEST="/static/"
DEST_PATH=${DEFAULT_DEST}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")/static/static-large/"

# ─────────────────────────────────────────────
# PARSE COMMAND-LINE OPTIONS
# ─────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $0 [OPTION]

Upload or download image files and other static assets to/from the website S3 buckets.

Options:
  --up-sync        Upload files from the default source dir (${SOURCE_DIR}) to S3 buckets.
  --down-sync      Download files from S3 stage bucket to local static directory (${SOURCE_DIR}).
  --all-buckets    When used with --up-sync, upload to all buckets instead of the default bucket.
  --help           Display this help and exit.

Configuration:
  The default destination for upload is ${DEFAULT_DEST}.
  In your .aws/credentials file, add a set of credentials:

  [${AWS_PROFILE}]
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
  local all_buckets="${1:-false}"
  # ─────────────────────────────────────────────
  # CHECK FOR AWS CLI
  # ─────────────────────────────────────────────
  validate_dependencies

  echo ""
  echo "Source files found in $SOURCE_DIR:"
  ls -1 "$SOURCE_DIR"

  echo "Destination path: $DEST_PATH"

  # ─────────────────────────────────────────────
  # UPLOAD TO BUCKETS
  # ─────────────────────────────────────────────
  UPLOAD_FAILED=0

  BUCKETS_TO_UPLOAD="$DEFAULT_BUCKET"
  if [[ "$all_buckets" == "true" ]]; then
    BUCKETS_TO_UPLOAD="$S3_BUCKETS"
  fi

  for bucket in $BUCKETS_TO_UPLOAD; do
    S3_DEST="s3://${bucket}${DEST_PATH}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Uploading to: $S3_DEST"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Capture exit code; show stdout+stderr live via tee to /dev/null trick
    set +e
    aws s3 sync --profile "${AWS_PROFILE}" "$SOURCE_DIR" "$S3_DEST" 2>&1
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
  # POST-UPLOAD SUMMARY
  # ─────────────────────────────────────────────
  echo ""
  if [[ $UPLOAD_FAILED -ne 0 ]]; then
    echo "One or more uploads failed. Please review the output above for details."
    echo "  Source folder:   $SOURCE_DIR"
    echo "  Destination:     $DEST_PATH"
    echo "  Buckets:         $S3_BUCKETS"
    exit 1
  fi

  echo ""
  echo "Done."
}

download_images() {
  validate_dependencies

  if echo "${S3_BUCKETS}" | grep -q -w "${DEFAULT_BUCKET}"; then
      aws s3 sync "s3://${DEFAULT_BUCKET}/static/"  "${SOURCE_DIR}" --profile "${AWS_PROFILE}";
      echo "All missing or outdated static items synced.";
  else
      echo "Bucket name invalid: ${DEFAULT_BUCKET}";
      exit 1;
  fi
}



ALL_BUCKETS=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      usage
      exit 0
      ;;
    --all-buckets)
      ALL_BUCKETS=true
      ;;
    --up-sync)
      upload_images "$ALL_BUCKETS"
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
