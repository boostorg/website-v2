#!/bin/bash

#
# A script to check-in code to the master branch of the boost website.
#
# Instructions:
#
# Make sure the script is executable. chmod 755 deploy-website.sh
#
# Locally, don't modify the results of the script. Use another
# directory for your own copies of repositories.
#
# Run the script -
#
#   ./deploy-website.sh          # deploys 'develop' (default)
#   ./deploy-website.sh r123     # deploys tag 'r123' where available
#
# If a tag argument is provided, it will be used as the merge source for
# repos where that tag exists. Repos that do not contain the tag will
# fall back to 'develop'.
#

set -e

deploy_tag="${1:-develop}"

base_folder=$HOME/github-automation
github_organization="boostorg"
list_of_repos="${github_organization}/boostlook ${github_organization}/website-v2-docs ${github_organization}/website-v2"
list_of_repos_verify_tag="${github_organization}/website-v2"

mkdir -p "${base_folder}/${github_organization}"
cd "${base_folder}/${github_organization}"
echo "It's recommended to not modify anything in this directory." > README.md
echo "It will be reserved for automation scripts." >> README.md
echo "During day to day work use any other directories such as $HOME/github, /opt/, $HOME/opt/ etc." >> README.md

#
# Preflight check: verify required executables are available.
#

executables="git gh"
for executable in ${executables}; do
    if ! which "${executable}" > /dev/null 2>&1 ; then
        echo "This script requires ${executable} to run, however it's missing. Please install that, and then re-run this script. Exiting."
        exit 1
    fi
done

#
# Preflight check: verify the latest 'develop' CI is green, and that no
# workflows are currently in-progress on 'develop' or 'master'.
#

echo ""
echo "Preflight check: verifying CI status"
for repo in ${list_of_repos}; do
    echo ""
    echo "-------------------------------------"
    echo "PREFLIGHT: ${repo}"
    echo "-------------------------------------"
    echo ""

    # Wait for any in-progress workflows on 'develop' or 'master' to finish.
    # Every 5 minutes (then 10, then 20, ...) offer to skip the wait.
    for branch in develop master; do
        elapsed=0
        next_prompt=300
        backoff=300
        while [ "$(gh run list -R "${repo}" -b "${branch}" --status in_progress --json databaseId -q length)" != "0" ]; do
            echo "Workflow in progress on ${repo} ${branch}; waiting..."
            sleep 30
            elapsed=$((elapsed + 30))
            if [ "${elapsed}" -ge "${next_prompt}" ]; then
                echo "Workflow in progress on ${repo} ${branch}; it has been running for $((elapsed / 60)) minutes."
                echo "Type \"continue anyway\" to proceed anyway. Type yes (or no, or anything at all) to continue waiting (recommended)."
                read -r -p "Response: " response
                if [[ "${response,,}" = "continue anyway" ]]; then
                    echo "Proceeding anyway."
                    break
                fi
                backoff=$((backoff * 2))
                next_prompt=$((elapsed + backoff))
            fi
        done
    done

    # Verify the most recent 'develop' workflow concluded successfully.
    conclusion=$(gh run list -R "${repo}" -b develop -L 1 --json conclusion -q '.[0].conclusion')
    if [ "${conclusion}" != "success" ]; then
        echo "Latest develop CI on ${repo} concluded '${conclusion}'. It is very much recommended to investigate and fix that before proceeding."
        echo "Type yes (or no, or anything at all) to exit this script. Type \"continue anyway\" to proceed with publishing."
        read -r -p "Response: " response
        if [[ "${response,,}" != "continue anyway" ]]; then
            echo "Not proceeding. Exiting."
            exit 1
        fi
        echo "Proceeding anyway."
    fi
done

for repo in ${list_of_repos}; do
    echo ""
    echo "====================================="
    echo "REPOSITORY: ${repo}"
    echo "====================================="
    echo ""
    cd "${base_folder}/${github_organization}"
    repo_dir="${base_folder}/${repo}"
    if [ ! -d "${repo_dir}" ]; then
        git clone -b develop "https://github.com/$repo"
    fi
    cd "${repo_dir}"

    echo "checking 'git diff'"
    if git diff --exit-code > /dev/null && git diff --cached --exit-code > /dev/null ; then
        true
    else
        echo "Files have been modified in the local repo. That is not expected."
        echo "'git diff' showed a result."
        echo "Possibly run a form of 'git reset' such as 'git reset --hard'".
        echo "Be sure the local repo matches with github."
        echo "Not proceeding. Exiting."
        exit 1
    fi

    echo "Running 'git fetch'"
    git fetch

    echo "Running 'git checkout develop'"
    git checkout develop

    echo "Running 'git pull'"
    git pull

    echo "Running 'git diff --exit-code origin/develop'"
    if git diff --exit-code origin/develop > /dev/null ; then
        true
    else
        echo "The local 'develop' branch differs from the github 'develop' branch."
        echo "Investigate why that has happened."
        echo "Not proceeding. Exiting."
        exit 1
    fi

    echo "Running 'git checkout master'"
    git checkout master

    echo "Running 'git pull'"
    git pull

    echo "Running 'git diff --exit-code origin/master'"
    if git diff --exit-code origin/master > /dev/null ; then
        true
    else
        echo "The local 'master' branch differs from the github 'master' branch."
        echo "Investigate why that has happened."
        echo "Not proceeding. Exiting."
        exit 1
    fi

    # Determine the merge source: use the deploy tag if it exists in this repo,
    # otherwise fall back to 'develop'.
    merge_source="refs/heads/develop"
    if [ "${deploy_tag}" != "develop" ]; then
        if git rev-parse "${deploy_tag}" > /dev/null 2>&1 ; then
            merge_source="refs/tags/${deploy_tag}"
            echo "Tag '${deploy_tag}' found in this repo. Using it as the merge source."
        else
            if echo "${list_of_repos_verify_tag}" | grep -qw "${repo}"; then
                echo ""
                echo "WARNING: Tag '${deploy_tag}' not found in this repo. Falling back to 'develop'."
                echo ""
                echo "This is very likely a problem since you specified a tag, but we do not see it in the repo."
                echo ""
                read -r -p "Proceed? [yN] " response
                response="${response:-N}"
                if [[ ! "${response}" =~ ^[Yy]$ ]]; then
                    echo "Not proceeding. Exiting."
                    exit 1
                fi
            else
                echo "Tag '${deploy_tag}' not found in this repo. Falling back to 'develop'."
            fi
        fi
    fi

    echo "Running 'git merge --ff-only ${merge_source}'"
    git merge --ff-only "${merge_source}"

    echo "Running 'git push' from the master branch"
    git push


done

echo "Completed successfully."
