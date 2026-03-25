#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Configuration — adjust these variables as needed
# =============================================================================
MAIN_ORG="boostorg"
MAIN_REPO="website-v2"
MY_ORG="cppalliance"
MY_REPO="website-v2-qa"
TARGET_BRANCH="cppal-dev"            # the important branch we merge/reset into

MAIN_REMOTE_NAME="upstream"   # name given to the mainorg/mainrepo remote locally
MY_REMOTE_URL="https://github.com/${MY_ORG}/${MY_REPO}.git"
MAIN_REMOTE_URL="https://github.com/${MAIN_ORG}/${MAIN_REPO}.git"

QA_ROOT="${HOME}/qa-automation"
WORK_DIR="${QA_ROOT}/${MY_ORG}/${MY_REPO}"
# =============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <PR_NUMBER>

Check out a pull request from ${MAIN_ORG}/${MAIN_REPO} and apply it to the
local '${TARGET_BRANCH}' branch in ${MY_ORG}/${MY_REPO}.

Arguments:
  PR_NUMBER          The pull request number from ${MAIN_ORG}/${MAIN_REPO}

Options:
  --merge            Perform a standard merge and regular git push.
                     Without this flag the script hard-resets '${TARGET_BRANCH}'
                     to the PR's commit SHA and performs a force push instead.
  --force            Skip the confirmation prompt before pushing.
  --help             Show this help message and exit.

Workflow:
  1. Ensures \$HOME/qa-automation directory structure exists and the repo is cloned.
  2. Fetches the PR from ${MAIN_ORG}/${MAIN_REPO} into a local tracking branch.
  3. Switches to '${TARGET_BRANCH}'.
  4. Without --merge: hard-resets '${TARGET_BRANCH}' to the PR commit SHA,
     then force-pushes to origin.
     With    --merge: merges the PR branch into '${TARGET_BRANCH}',
     then pushes normally to origin.
  5. Prompts before any push so you stay in control.

Examples:
  $(basename "$0") 42              # Hard-reset + force-push PR #42
  $(basename "$0") --merge 42      # Merge + push PR #42
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
DO_MERGE=false
FORCE_PUSH_AUTO=false
PR_NUMBER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --merge)
            DO_MERGE=true
            shift
            ;;
        --force)
            FORCE_PUSH_AUTO=true
            shift
            ;;
        -*)
            echo "Error: Unknown option '$1'" >&2
            echo "Run '$(basename "$0") --help' for usage." >&2
            exit 1
            ;;
        *)
            if [[ -n "$PR_NUMBER" ]]; then
                echo "Error: Unexpected extra argument '$1'" >&2
                echo "Run '$(basename "$0") --help' for usage." >&2
                exit 1
            fi
            PR_NUMBER="$1"
            shift
            ;;
    esac
done

if [[ -z "$PR_NUMBER" ]]; then
    echo "Error: PR_NUMBER is required." >&2
    echo "Run '$(basename "$0") --help' for usage." >&2
    exit 1
fi

if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "Error: PR_NUMBER must be a positive integer (got '${PR_NUMBER}')." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Helper: ensure the working repo exists
# ---------------------------------------------------------------------------
ensure_repo() {
    mkdir -p "${QA_ROOT}"

    if [[ ! -d "${WORK_DIR}/.git" ]]; then
        echo "==> Cloning ${MY_ORG}/${MY_REPO} into ${WORK_DIR} …"
        mkdir -p "$(dirname "${WORK_DIR}")"
        git clone "${MY_REMOTE_URL}" "${WORK_DIR}" 2>/dev/null
    fi

    cd "${WORK_DIR}"

    # Make sure the upstream remote exists
    if ! git remote get-url "${MAIN_REMOTE_NAME}" &>/dev/null; then
        echo "==> Adding remote '${MAIN_REMOTE_NAME}' → ${MAIN_REMOTE_URL}"
        git remote add "${MAIN_REMOTE_NAME}" "${MAIN_REMOTE_URL}" 2>/dev/null
    fi
}

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
ensure_repo
cd "${WORK_DIR}"

PR_REF="refs/pull/${PR_NUMBER}/head"
LOCAL_PR_BRANCH="pr/${PR_NUMBER}"

echo "==> Switching to '${TARGET_BRANCH}' before fetching …"
if git show-ref --quiet "refs/heads/${TARGET_BRANCH}"; then
    git checkout "${TARGET_BRANCH}" 2>/dev/null
else
    if git ls-remote --exit-code origin "refs/heads/${TARGET_BRANCH}" &>/dev/null; then
        git checkout -b "${TARGET_BRANCH}" "origin/${TARGET_BRANCH}" 2>/dev/null
    else
        git checkout -b "${TARGET_BRANCH}" 2>/dev/null
    fi
fi

echo "==> Fetching PR #${PR_NUMBER} from ${MAIN_REMOTE_NAME} …"
git fetch "${MAIN_REMOTE_NAME}" "${PR_REF}:${LOCAL_PR_BRANCH}" 2>/dev/null

PR_SHA=$(git rev-parse "${LOCAL_PR_BRANCH}")
echo "    PR commit SHA: ${PR_SHA}"

if [[ "$DO_MERGE" == true ]]; then
    # -----------------------------------------------------------------------
    # MERGE mode: standard merge then normal push
    # -----------------------------------------------------------------------
    echo "==> Merging '${LOCAL_PR_BRANCH}' into '${TARGET_BRANCH}' …"
    git merge "${LOCAL_PR_BRANCH}" --no-edit 2>/dev/null

    SHOULD_PUSH=false
    if [[ "$FORCE_PUSH_AUTO" == true ]]; then
        SHOULD_PUSH=true
    else
        printf "\nPush the PR to the branch '%s'? (y/n) " "${TARGET_BRANCH}"
        read -r ANSWER
        if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
            SHOULD_PUSH=true
        fi
    fi

    if [[ "$SHOULD_PUSH" == true ]]; then
        echo "==> Pushing to origin/${TARGET_BRANCH} …"
        git push origin "${TARGET_BRANCH}" 2>/dev/null
        echo "Done."
    else
        echo "Push skipped."
    fi
else
    # -----------------------------------------------------------------------
    # FORCE-PUSH mode: hard-reset TARGET_BRANCH to the PR SHA, then force-push
    # -----------------------------------------------------------------------
    echo "==> Hard-resetting '${TARGET_BRANCH}' to PR commit ${PR_SHA} …"
    git reset --hard "${PR_SHA}" 2>/dev/null

    SHOULD_PUSH=false
    if [[ "$FORCE_PUSH_AUTO" == true ]]; then
        SHOULD_PUSH=true
    else
        printf "\nForce push the PR to the branch '%s'? (y/n) " "${TARGET_BRANCH}"
        read -r ANSWER
        if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
            SHOULD_PUSH=true
        fi
    fi

    if [[ "$SHOULD_PUSH" == true ]]; then
        echo "==> Force-pushing to origin/${TARGET_BRANCH} …"
        git push --force origin "${TARGET_BRANCH}" 2>/dev/null
        echo "Done."
    else
        echo "Force push skipped."
    fi
fi
