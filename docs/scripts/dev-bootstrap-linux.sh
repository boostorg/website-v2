#!/bin/bash

# Copyright 2024 Sam Darwin
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at http://boost.org/LICENSE_1_0.txt)

set -e
# set -x

scriptname="dev-bootstrap-linux.sh"

# set defaults:
prereqsoption="yes"
# docker_mode either "native" or "desktop" (Docker Desktop). Only support "native" currently.
docker_mode="native"
docker_explanation="On Linux, there are two ways to run Docker. Either the standard native docker installation, or Docker Desktop, which runs inside a virtual machine. The most common installation is standard docker, so that is what is supported by this script currently. In the future, Docker Desktop support could be added.  Each method has pros and cons.  It's important that the user inside the Django containers is the same as the user on the host machine outside the containers, so that file ownership matches up.  Since the user is 'root' inside the containers, it should be 'root' on the host machine.  Therefore, after getting set up with this script, any development work should be done as 'root'.  That means, run 'sudo su -' before using docker-compose.  Docker Desktop would be an alternative to that requirement, and allow running as a regular user account. But with some downside, that it is not a typical Docker installation, as found on a server."

if [[ ${docker_mode} == "native" ]]; then
    repo_path_base="/opt/github"
    completion_message_1="When doing development work, switch to the root user 'sudo su -', cd to that directory location, and run 'docker compose up -d'. While this script works as a normal user, you should be 'root' when running docker compose."
    possible_sudo="sudo"
    shell_initialization_file=/root/.bashrc
fi
if [[ ${docker_mode} == "desktop" ]]; then
    repo_path_base="${HOME}/github"
    completion_message_1="When doing development work, cd to that directory location, and run 'docker compose up -d'"
    possible_sudo=""
    shell_initialization_file=~/.bashrc
fi

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
  --launch              Run docker-compose. No packages.
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

if [[ -n "${detected_repo_path}" && "${detected_repo_path}" != "nofolder" ]]; then
    detected_repo_user=$(stat -c "%U" "${detected_repo_path}")
fi

if [[ -n "${detected_repo_url}" && "${detected_repo_url}" != "empty" && -n "${repooption}" ]]; then
    echo "You have specified a repo, but you are also running this script from within a repo."
    echo "This is indeterminate. Choose one or the other. Exiting."
    exit 1
elif [[ -n "${detected_repo_url}" && "${detected_repo_url}" != "empty" ]]; then
    # existing repo
    if [[ "${docker_mode}" == "native" && "${detected_repo_user}" != "root" ]]; then
        echo ""
        echo "${docker_explanation}"
        echo ""
        echo "The script is currently running in 'native' mode, however a non-root user owns the repository folder."
        echo "The choices are:"
        echo "1. cd outside the current repo folder, and re-run the script, so that it can set things up as 'root'"
        echo "2. Install 'Docker Desktop', and switch the mode of this script to 'Docker Desktop' mode. (Not yet supported)."
        echo ""
        echo "Exiting"
        exit 1
    fi
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
    ${possible_sudo} mkdir -p "${repo_path_base}"
    cd "${repo_path_base}"
    if [ ! -d "${repo_name}" ]; then
        ${possible_sudo} git clone "${repo_url}"
    fi
    cd "${repo_name}"
    if [ ! -f .env ]; then
        ${possible_sudo} cp env.template .env
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
    read -r -p "Do you want to continue? " -n 1 -r
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

    # sudo apt-get update
    x="\$nrconf{restart} = 'a';"
    echo "$x" | sudo tee /etc/needrestart/conf.d/90-autorestart.conf 1>/dev/null

    if ! command -v makedeb &> /dev/null
    then
        echo "Installing makdeb"
        MAKEDEB_RELEASE=makedeb bash -ci "$(wget -qO - 'https://shlink.makedeb.org/install')"
    fi
    if ! command -v git &> /dev/null
    then
        echo "Installing git"
        sudo apt-get install -y git
    fi

    if ! command -v python3 &> /dev/null
    then
        echo "Installing python3"
        sudo apt-get install -y python3
    fi
    if ! command -v just &> /dev/null
    then
        echo "Installing just"
        startdir=$(pwd)
        sudo mkdir -p /opt/justinstall
        CURRENTUSER=$(whoami)
        sudo chown "$CURRENTUSER" /opt/justinstall
        chmod 777 /opt/justinstall
        cd /opt/justinstall
        git clone 'https://mpr.makedeb.org/just'
        cd just
        makedeb -si
        cd "$startdir"
    fi

    if [[ ${docker_mode} == "native" ]]; then
        if ! sudo bash -i -c 'command -v nvm &> /dev/null'
        then
            sudo curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | sudo bash
            # shellcheck source=/dev/null
            sudo bash -i -c 'nvm install 20; nvm use 20'
            echo "Run . ${shell_initialization_file} to enable nvm"
        fi
    else
        if ! command -v nvm &> /dev/null
        then
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
            # shellcheck source=/dev/null
            . ${shell_initialization_file}
            nvm install 20
            nvm use 20
            echo "Run . ${shell_initialization_file} to enable nvm"
        fi
    fi

    if [[ ${docker_mode} == "native" ]]; then
        if ! sudo bash -i -c 'command -v yarn &> /dev/null'
        then
            sudo bash -i -c 'npm install -g yarn'
        fi
    else
        if ! command -v yarn &> /dev/null
        then
            npm install -g yarn
        fi
    fi

    if ! docker compose &> /dev/null ; then
        echo "Installing docker-compose"
        sudo apt-get install -y ca-certificates curl gnupg
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        # shellcheck disable=SC1091
        echo \
          deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable | \
          sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    fi

    # "Add current user to docker group"
    sudo usermod -aG docker "$USER"

    if [[ ${docker_mode} == "desktop" ]]; then
        if ! id | grep docker 1>/dev/null
        then
            echo "Your user account has just been added to the 'docker' group. Please log out and log in again. Check groups with the id command."
            echo "The installation section of this script is complete. After logging in again, you may proceed to manually running docker compose."
            echo "Or run this script again with --launch to start containers."
        fi
    fi

    echo "The 'installation' section of this script is complete."
    echo "The location of your docker compose installation is ${repo_path}."
    echo ""
    if [[ "$launchoption" != "yes" ]]; then
        echo "You may run this script again with the --launch option, to launch docker compose and run db migrations".
        echo ""
    fi
    echo "${completion_message_1}"
fi

if [[ "$launchoption" == "yes" ]]; then
    if [[ "${docker_mode}" == "desktop" ]]; then
        if ! command -v nvm &> /dev/null
        then
            # shellcheck source=/dev/null
            . ${shell_initialization_file}
        fi
    fi

    cd "${repo_path}"
    echo "Launching docker compose"
    echo "Let's wait for that to run. Sleeping 60 seconds."
    ${possible_sudo} docker compose up -d
    sleep 60
    echo "Creating superuser"
    ${possible_sudo} docker compose run --rm web python manage.py makemigrations
    echo "running database migrations"
    ${possible_sudo} docker compose run --rm web python manage.py migrate
    echo "Creating superuser"
    ${possible_sudo} docker compose run --rm web python manage.py createsuperuser
    echo "Running yarn"
    if [[ "${possible_sudo}" == "sudo" ]]; then
        sudo bash -i -c 'yarn; yarn build; cp static/css/styles.css static_deploy/css/styles.css'
    else
        yarn
        yarn build
        cp static/css/styles.css static_deploy/css/styles.css
    fi
    echo "In your browser, visit http://localhost:8000"
    echo "Later, to shut down: docker compose down"
fi
