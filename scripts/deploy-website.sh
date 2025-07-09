#!/bin/bash

#
# A script to check-in code to the master branch of the boost website.
#
# Instructions:
#
# Adjust the variable base_folder to match your local machine's folder layout.
#
# Make sure the script is executable. chmod 755 deploy-website.sh
#
# Run the script -
#
# ./deploy-website.sh
#

set -e

# Set this:
base_folder=/opt/github

list_of_repos="boostorg/boostlook boostorg/website-v2-docs boostorg/website-v2"

for repo in ${list_of_repos}; do
    repo_dir="${base_folder}/${repo}"
    if [ ! -d "${repo_dir}" ]; then
        echo "The directory of ${repo} does not exist at ${repo_dir}."
        echo "This script assumes you have already checked out the codebase locally."
        echo "Check if you have configured the variable base_folder correctly."
        echo "Exiting."
        exit 1
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

    echo "Running 'git merge --ff-only develop'"
    git merge --ff-only develop

    echo "Running 'git push' from the master branch"
    git push

    if [ "$repo" = "boostorg/boostlook" ]; then
        echo "Deployed boostlook. Waiting 5 minutes before proceeding, since that triggers github actions on other repos."
        echo "This step may be adjusted later."
        sleep 300
    fi

done

echo "Completed successfully."
