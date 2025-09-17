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

base_folder=$HOME/github-automation
github_organization="boostorg"
list_of_repos="${github_organization}/boostlook ${github_organization}/website-v2-docs ${github_organization}/website-v2"

mkdir -p ${base_folder}/${github_organization}
cd ${base_folder}/${github_organization}
echo "It's recommended to not modify anything in this directory." > README.md
echo "It will be reserved for automation scripts." >> README.md
echo "During day to day work use any other directories such as $HOME/github, /opt/, $HOME/opt/ etc." >> README.md

for repo in ${list_of_repos}; do
    echo ""
    echo "====================================="
    echo "REPOSITORY: ${repo}"
    echo "====================================="
    echo ""
    cd ${base_folder}/${github_organization}
    repo_dir="${base_folder}/${repo}"
    if [ ! -d "${repo_dir}" ]; then
        git clone -b develop https://github.com/$repo
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

    if [ "$repo" = "${github_organization}/boostlook" ]; then
        echo "Deployed boostlook. Waiting 5 minutes before proceeding, since that triggers github actions on other repos."
        echo "This step may be adjusted later."
        sleep 300
    fi

done

echo "Completed successfully."
