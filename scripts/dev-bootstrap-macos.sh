#!/bin/bash

# Copyright 2024 Sam Darwin
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at http://boost.org/LICENSE_1_0.txt)

set -e
# set -x

scriptname="dev-bootstrap-macos.sh"
if [[ "$(uname -p)" =~ "arm" ]]; then
    echo "Running on arm processor"
    homebrew_base_path="/opt/homebrew"
else
    echo "Not running on arm processor"
    homebrew_base_path="/usr/local"
fi

# set defaults:
prereqsoption="yes"
# docker_mode either "native" or "desktop" (Docker Desktop). macos only support "desktop" currently.
docker_mode="desktop"

if [[ ${docker_mode} == "native" ]]; then
    # Not supported on macos currently, or ever.
    repo_path_base="/opt/github"
    completion_message_1="When doing development work, switch to the root user 'sudo su -', cd to that directory location, and run 'docker compose up -d'"
    shell_initialization_file=/Users/root/.zprofile
fi
if [[ ${docker_mode} == "desktop" ]]; then
    repo_path_base="${HOME}/github"
    completion_message_1="When doing development work, cd to that directory location, and run 'docker compose up -d'"
    shell_initialization_file=~/.zprofile
fi

# git and getopt are required. If they are not installed, moving that part of the installation process
# to an earlier part of the script:
# Install brew
export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH
if ! command -v brew &> /dev/null
then
    echo "Installing brew. Check the instructions that are shown."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Brew initialization
shell_initialization_file=~/.zprofile
if grep "brew" ${shell_initialization_file}; then
    echo "brew already in startup"
else
    echo "adding brew to startup"
    # shellcheck disable=SC2016
    (echo; echo 'eval "$(/opt/homebrew/bin/brew shellenv)"') >> ${shell_initialization_file}
fi

eval "$(/opt/homebrew/bin/brew shellenv)"


if ! command -v git &> /dev/null
then
    echo "Installing git"
    brew install git
fi

# check apple silicon.
if ! command -v ${homebrew_base_path}/opt/gnu-getopt/bin/getopt &> /dev/null
then
    echo "Installing gnu-getopt"
    brew install gnu-getopt
fi
export PATH="${homebrew_base_path}/opt/gnu-getopt/bin:$PATH"

# READ IN COMMAND-LINE OPTIONS

TEMP=$(getopt -o h:: --long repo:,help::,launch::,prereqs::,all:: -- "$@")
eval set -- "$TEMP"

# extract options and their arguments into variables.
while true ; do
    case "$1" in
        -h|--help)
            helpmessage="""
usage: $scriptname [-h] [--repo REPO] [--launch] [--all]

Install all required packages (this is the default action), launch docker-compose, or both.

optional arguments:
  -h, --help            Show this help message and exit
  --repo REPO           Name of repository to set up. Example: https://github.com/boostorg/website-v2. You should specify your own fork.
  --launch              Run docker-compose. No packages. (In development.)
  --all			Both packages and launch.
"""

            echo ""
	    echo "$helpmessage" ;
	    echo ""
            exit 0
            ;;
        --repo)
            case "$2" in
                "") repooption="" ; shift 2 ;;
                 *) repooption=$2 ; shift 2 ;;
            esac ;;
	--launch)
	    launchoption="yes" ; prereqsoption="no" ; shift 2 ;;
	--all)
	    prereqsoption="yes" ; launchoption="yes" ; shift 2 ;;
        --) shift ; break ;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done

echo "Chosen options: pre: $prereqsoption launch: $launchoption repo: $repooption"

# Determine git repo

detected_repo_url=$(git config --get remote.origin.url 2> /dev/null || echo "empty")
detected_repo_name=$(basename -s .git "$(git config --get remote.origin.url)" 2> /dev/null || echo "empty")
# Currently unused. Could be uncommented if needed:
# detected_repo_org=$(basename $(dirname "${detected_repo_url}"))
detected_repo_path=$(git rev-parse --show-toplevel 2> /dev/null || echo "nofolder")
detected_repo_path_base=$(dirname "${detected_repo_path}")

if [[ -n "${detected_repo_url}" && "${detected_repo_url}" != "empty" && -n "${repooption}" ]]; then
    echo "You have specified a repo on the command line, but you are also running this script from within a repo."
    echo "This is indeterminate. Choose one or the other. Exiting."
    exit 1
elif [[ -n "${detected_repo_url}" && "${detected_repo_url}" != "empty" ]]; then
    echo "You are running the script from an existing repository. That will be used."
    repo_url=${detected_repo_url}
    repo_name=${detected_repo_name}
    repo_path=${detected_repo_path}
    repo_path_base=${detected_repo_path_base}
    echo "The repo path is ${repo_path}"
    cd "${repo_path}"
    if [ ! -f .env ]; then
        cp env.template .env
    fi
else
    if [ -n "${repooption}" ]; then
        echo "You have specified a repository on the command line. That will be preferred. ${repooption}"
        repo_url=${repooption}
    else
        echo "Please enter a full git repository url with a format such as https:://github.com/_your_name_/website-v2"
        read -r repo_url
    fi
    repo_name=$(basename -s .git "$repo_url" 2> /dev/null || echo "empty")
    repo_org_part_1=$(dirname "${repo_url}")
    repo_org=$(basename "$repo_org_part_1")
    repo_path_base="${repo_path_base}/${repo_org}"
    repo_path="${repo_path_base}/${repo_name}"
    echo "The path will be ${repo_path}"
    mkdir -p "${repo_path_base}"
    cd "${repo_path_base}"
    if [ ! -d "${repo_name}" ]; then
        git clone "${repo_url}"
    fi
    cd "${repo_name}"
    if [ ! -f .env ]; then
        cp env.template .env
    fi
fi

# Check .env file

if grep STATIC_CONTENT_AWS_ACCESS_KEY_ID .env | grep changeme; then
    unsetawskey="yes"
fi
if grep STATIC_CONTENT_AWS_SECRET_ACCESS_KEY .env | grep changeme; then
    unsetawskey="yes"
fi

if [[ $unsetawskey == "yes" ]]; then
    echo "There appears to be aws keys in your .env file that says 'changeme'. Please set them before proceeding."
    echo "Talk to an administrator or other developer to get the keys."
    read -r -p "Do you want to continue? y/n" -n 1 -r
    echo    # (optional) move to a new line
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        echo "we are continuing"
    else
        echo "did not receive a Yy. Exiting."
        exit 1
    fi
fi

if [[ "$prereqsoption" == "yes" ]]; then
    # Install rosetta
    if ! pgrep oahd; then
        echo "Installing rosetta"
        sudo softwareupdate --install-rosetta --agree-to-license
    fi

    if ! command -v curl &> /dev/null
    then
        echo "Installing curl"
        brew install curl
    fi

    if ! command -v just &> /dev/null
    then
        echo "Installing just"
        brew install just
    fi

    if ! command -v python3 &> /dev/null
    then
        echo "Installing python3"
        brew install python3
    fi

    if ! command -v nvm &> /dev/null
    then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
        # shellcheck source=/dev/null
        . ~/.zprofile
        nvm install 20
        nvm use 20
        echo "Run . ~/.zprofile to enable nvm"
    fi

    if ! command -v yarn &> /dev/null
    then
        npm install -g yarn
    fi

    if ! docker compose &> /dev/null ; then
        echo "Installing Docker Desktop"
        curl -o /tmp/Docker.dmg https://desktop.docker.com/mac/main/arm64/160616/Docker.dmg
        sudo hdiutil attach /tmp/Docker.dmg
        sudo /Volumes/Docker/Docker.app/Contents/MacOS/install
        sudo hdiutil detach /Volumes/Docker
        echo "The Docker Desktop dmg package has been installed."
        echo "The next step is to go to a desktop GUI window on the Mac, run Docker Desktop, and complete the installation."
        echo "Then return here."
        read -r -p "Do you want to continue? y/n" -n 1 -r
        echo    # (optional) move to a new line
        if [[ $REPLY =~ ^[Yy]$ ]]
        then
            echo "we are continuing"
        else
            echo "did not receive a Yy. Exiting. You may re-run the script."
            exit 1
        fi
    fi

    echo "The installation section of this script is complete."
    echo "The location of your docker compose installation is ${repo_path}."
    echo ""
    if [[ "$launchoption" != "yes" ]]; then
        echo "You may run this script again with the --launch option, to launch docker compose and run db migrations".
        echo ""
    fi
    echo "${completion_message_1}"
fi

if [[ "$launchoption" == "yes" ]]; then
    if ! command -v nvm &> /dev/null
    then
        # shellcheck source=/dev/null
        . ~/.zprofile
    fi

    cd "${repo_path}"
    echo "Launching docker compose"
    echo "Let's wait for that to run. Sleeping 60 seconds."
    docker compose up -d
    sleep 60
    echo "Creating database migrations"
    docker compose run --rm web python manage.py makemigrations
    echo "running database migrations"
    docker compose run --rm web python manage.py migrate
    echo "Creating superuser"
    docker compose run --rm web python manage.py createsuperuser
    echo "Running yarn"
    yarn
    yarn build
    cp static/css/styles.css static_deploy/css/styles.css
    echo "In your browser, visit http://localhost:8000"
    echo "Later, to shut down: docker compose down"
fi
