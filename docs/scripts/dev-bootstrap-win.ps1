
# TODO: remember repo in a file, in case you restart the script

# Copyright 2024 Sam Darwin
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at http://boost.org/LICENSE_1_0.txt)

[System.Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingInvokeExpression', '')]

#Requires -RunAsAdministrator

param (
   [Parameter(Mandatory=$false)][alias("repo")][string]$repooption = "",
   [switch]$help = $false,
   [switch]${launch} = $false,
   [switch]${all} = $false
)

# set defaults:
${prereqsoption}="yes"
$scriptname="dev-bootstrap-win.ps1"
# Skip 1.1.12, has a bug. Go to 1.1.13 or later.
$nvm_install_version="1.1.11"
$node_version="20.17.0"
# docker_mode either "native" or "desktop" (Docker Desktop). win only support "desktop" currently.
$docker_mode="desktop"
${sleep_longer}=60
${sleep_shorter}=30
${cached_url_file}="tmp-dev-bootstrap-url.cfg"
${git_branch}="develop"

if (${docker_mode} -eq "native")
{
    # Not supported on win currently, or ever.
    ${repo_path_base}="\opt\github"
    ${completion_message_1}="When doing development work, switch to the root user 'sudo su -', Set-Location to that directory location, and run 'docker compose up -d'"
}
if (${docker_mode} -eq "desktop")
{
    ${repo_path_base}="${HOME}\github"
    ${completion_message_1}="When doing development work, Set-Location to that directory location, and run 'docker compose up -d'"
}

# Set-PSDebug -Trace 1

if ($help)
{

$helpmessage="
usage: $scriptname [-help] [-repo REPO] [-launch] [-all]

Builds library documentation.

optional arguments:
  -help                 Show this help message and exit
  -repo REPO            Name of repository to set up. Example: https://github.com/boostorg/website-v2. You should specify your own fork.
  -launch               Run docker-compose. No packages. (In development.)
  -all                  Both packages and launch.
"

Write-Output $helpmessage
exit 0
}

if ($launch)
{
    ${launchoption} = "yes"
    ${prereqsoption}="no"
}

if ($all)
{
    ${launchoption} = "yes"
    ${prereqsoption}="yes"
}

function refenv
{

    # Make `refreshenv` available right away, by defining the $env:ChocolateyInstall
    # variable and importing the Chocolatey profile module.
    # Note: Using `. $PROFILE` instead *may* work, but isn't guaranteed to.
    $env:ChocolateyInstall = Convert-Path "$((Get-Command choco).Path)\..\.."
    Import-Module "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"

    # refreshenv (Update-SessionEnvironment) might delete path entries. Return those to the path.
    $originalpath=$env:PATH
    Update-SessionEnvironment
    $joinedpath="${originalpath};$env:PATH"
    $joinedpath=$joinedpath.replace(';;',';')
    $env:PATH = ($joinedpath -split ';' | Select-Object -Unique) -join ';'
}

# git is required. In the unlikely case it's not yet installed, moving that part of the package install process
# here to an earlier part of the script:


if ( -Not (Get-Command choco -errorAction SilentlyContinue) )
{
    Write-Output "Install chocolatey"
    Invoke-Expression ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))
    refenv
}

if ( -Not (Get-Command git -errorAction SilentlyContinue) )
{
    Write-Output "Install git"
    choco install -y --no-progress git
    refenv
}

Write-Output "Chosen options: pre: ${prereqsoption} launch: ${launchoption} repo: ${repooption}"

# Determine git repo

$originurl=git config --get remote.origin.url 2>$null
if ($LASTEXITCODE -eq 0)
{
    ${detected_repo_url}=[io.path]::ChangeExtension($originurl, [NullString]::Value)
}
else
{
    ${detected_repo_url}="empty"
}

## detected_repo_org=$(basename $(dirname "${detected_repo_url}"))

$repopath=git rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -eq 0)
{
    ${detected_repo_path}=$repopath | ForEach-Object {$_ -replace '/','\'}
}
else
{
    ${detected_repo_path}="nofolder"
}

${detected_repo_path_base}=[io.path]::GetDirectoryName($detected_repo_path)

if (Test-Path ${cached_url_file})
{
    $detected_cached_url = Get-Content ${cached_url_file} -Raw
    $detected_cached_url = $detected_cached_url.Trim()
}

if ( ${detected_repo_url} -and -not (${detected_repo_url} -eq "empty") -and ${repooption} )
{
    Write-Output "You have specified a repo on the command line, but you are also running this script from within a repo."
    Write-Output "This is indeterminate. Choose one or the other. Exiting."
    exit 1
}
elseif ( ${detected_repo_url} -and -not (${detected_repo_url} -eq "empty") )
{
    Write-Output "You are running the script from an existing repository. That will be used."
    ${repo_url}=${detected_repo_url}
    ${repo_name}=${detected_repo_name}
    ${repo_path}=${detected_repo_path}
    ${repo_path_base}=${detected_repo_path_base}
    Write-Output "The repo path is ${repo_path}"
    Set-Location "${repo_path}"
    if ( !(Test-Path .env ) )
    {
        Copy-Item env.template .env
    }
}
else
{
    if (${repooption})
    {
        Write-Output "You have specified a repository on the command line. That will be preferred. ${repooption}"
        ${repo_url}=${repooption}
        Write-Output "${repo_url}" | Out-File ${cached_url_file}
    }
    else
    {
        if (${detected_cached_url})
        {
            $extra_text="[Hit enter to accept default value ${detected_cached_url}]"
            $default_value=${detected_cached_url}
        }
        else
        {
            $extra_text=""
            $default_value=""
        }

        $repo_url = Read-Host "Please enter a full git repository url with a format such as https:://github.com/_your_name_/website-v2 ${extra_text}"

        if (!$repo_url)
        {
            $repo_url=$default_value
        }

        if (!$repo_url)
        {
	        Write-Output "You did not provide a git url. Exiting"
	        exit 1
        }
        else
        {
            Write-Output "repo url is now $repo_url"
            Write-Output "${repo_url}" | Out-File ${cached_url_file}
        }
    }

    if ($repo_url)
    {
        ${repo_name}=[io.path]::GetFileNameWithoutExtension($repo_url)
    }
    else
    {
        ${repo_name}="empty"
    }

    ${repo_org_part_1}=[io.path]::GetDirectoryName($repo_url)
    ${repo_org}=[io.path]::GetFileNameWithoutExtension($repo_org_part_1)
    ${repo_path_base}="${repo_path_base}\${repo_org}"
    ${repo_path}="${repo_path_base}\${repo_name}"
    Write-Output "The path will be ${repo_path}"
    mkdir -Force "${repo_path_base}"
    Set-Location "${repo_path_base}"
    if ( !(Test-Path -Path ${repo_path}))
    {
        git clone -b ${git_branch} "${repo_url}"
    }
    Set-Location "${repo_name}"
    if ( !(Test-Path .env))
    {
        Copy-Item env.template .env
    }
}

# On windows, the docker/ folder needs to have EOL=lf.

$a_docker_filename=".\docker\compose-start.sh"
if ((Get-Content $a_docker_filename -Raw) -match "\r\n$")
{
    Write-Output "${a_docker_filename} has windows line endings. The docker/ folder needs to have unix line endings."
    Write-Output "The .gitattributes file should already fix this. Check out a new copy of the repository "
    Write-Output "and then re-run this script."
    exit 1
}

# Check .env file

$searchresults = Select-String -pattern "STATIC_CONTENT_AWS_ACCESS_KEY_ID" .env | Select-String -pattern "changeme"
if ($null -eq $searchresults)
{
    # "No matches found"
    ForEach-Object 'foo'
}
else
{
    $unsetawskey="yes"
}

$searchresults = Select-String -pattern "STATIC_CONTENT_AWS_SECRET_ACCESS_KEY" .env | Select-String -pattern "changeme"
if ($null -eq $searchresults)
{
    # "No matches found"
    ForEach-Object 'foo'
}
else
{
    $unsetawskey="yes"
}

if ($unsetawskey)
{
    Write-Output "There appears to be aws keys in your .env file that says 'changeme'. Please set them before proceeding."
    Write-Output "Talk to an administrator or other developer to get the keys."
    $REPLY = Read-Host "Do you want to continue? y/n"
    if (($REPLY -eq "y") -or ($REPLY -eq "Y"))
    {
        Write-Output "Continuing"
    }
    else
    {
        Write-Output "did not receive a Yy. Exiting."
        exit 1
    }
}

if ($prereqsoption -eq "yes")
{

    if ( -Not (Get-Command just -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress just
    }

    if ( -Not (Get-Command python -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress python
    }

    if ( -Not (Get-Command nvm -errorAction SilentlyContinue) )
    {
        # 1.1.12 doesn't allow reading stdout. Will be fixed in 1.1.13 supposedly.
        choco install -y --no-progress nvm.install --version ${nvm_install_version}
        Write-Output "NVM was just installed. Close this terminal window, and then restart the script."
        Write-Output "The process has not finished. Please open a new terminal window. And restart the script."
        exit 0
    }

    if (nvm list | Select-String "${node_version}")
    {
        # Node already installed
        ForEach-Object 'foo'
    }
    else
    {
        nvm install 20
        nvm use 20
    }

    if ( -Not (Get-Command yarn -errorAction SilentlyContinue) )
    {
        npm install -g yarn
    }

    refenv

    # Check if wsl is installed
    $console = ([console]::OutputEncoding)
    [console]::OutputEncoding = New-Object System.Text.UnicodeEncoding
    if (wsl --status | oss | select-string -pattern "Ubuntu")
    {
        $wslinstalled="yes"
    }
    else
    {
        $wslinstalled="no"
    }
    [console]::OutputEncoding = $console

    if ($wslinstalled -eq "no")
    {
        wsl --install
        Write-Output "WSL was just installed. Rebooting in ${sleep_shorter} seconds. Then complete the WSL steps if they appear, and re-run this script."
        Start-Sleep ${sleep_shorter}
        Restart-Computer
    }
    else
    {
        wsl --update
    }

    if ( -Not (Get-Command docker -errorAction SilentlyContinue) )
    {
        Write-Output "Installing Docker Desktop"
        choco install -y --no-progress docker-desktop -ia --quiet --accept-license
        refenv

        Write-Output "Docker-Desktop was just installed. Rebooting in ${sleep_shorter} seconds. Then launch Docker Desktop to complete the installation."
        Write-Output "After that, you may choose to either re-run this script with -launch,"
        Write-Output "or run the necessary 'docker compose' steps directly to launch a local environment."
        Write-Output ""
        Write-Output "When the system comes back up, click the Docker Desktop icon to accept the license and complete the installation."
        Start-Sleep ${sleep_shorter}
        Restart-Computer
    }

    Write-Output "The 'installation' section of this script is complete."
    Write-Output "The location of your docker compose installation is ${repo_path}."
    Write-Output ""
    if ( ! ( "launchption" -eq "yes"))
    {
        Write-Output "You may run this script again with the -launch option, to launch docker compose and run db migrations".
        Write-Output ""
    }
    Write-Output ${completion_message_1}
}

if ("$launchoption" -eq "yes")
{
    # is something like this needed on windows? how does it work?
    # if ! command -v nvm &> /dev/null
    # then
    #     . ~/.zprofile
    # fi

    Set-Location "${repo_path}"

    Write-Output "Starting the docker compose steps"
    Write-Output "running docker compose pull"
    docker compose pull
    Write-Output "docker compose up -d"
    Write-Output "Let's wait for that to run. Sleeping ${sleep_longer} seconds."
    docker compose up -d
    Start-Sleep ${sleep_longer}
    Write-Output "running makemigrations"
    docker compose run --rm web python manage.py makemigrations
    Write-Output "running database migrations"
    docker compose run --rm web python manage.py migrate
    Write-Output "Creating superuser"
    docker compose run --rm web python manage.py createsuperuser
    # collectstatic already done, by celery
    # Write-Output "running collectstatic"
    # docker compose run --rm web python manage.py collectstatic
    Write-Output "Running yarn"
    yarn
    yarn dev-windows
    Copy-Item static/css/styles.css static_deploy/css/styles.css
    Write-Output "In your browser, visit http://localhost:8000"
    Write-Output "Later, to shut down: docker compose down"
}
