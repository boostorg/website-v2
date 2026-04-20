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
