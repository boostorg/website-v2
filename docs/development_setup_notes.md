## Development Setup Notes

The procedure to configure a development environment is mainly covered in the top-level README.md. This document will contain more details about installing prerequisites: Just, Python, Docker, and Docker Compose.

- [Development Setup Notes](#development-setup-notes)
- [Windows](#windows)
- [Ubuntu 22.04](#ubuntu-2204)
- [macOS](#macOS)
- [Local Development](#local-development)
  - [Social Login with django-allauth](#social-login-with-django-allauth)


## Windows

There are multiple alternatives to choose from.

Method 1:

The script dev-bootstrap-win.ps1 will automatically install prerequisites, and with the -all or -launch flag will also run docker-compose.

Open a Powershell terminal (Admin mode).

Enable Powershell scripts with `Set-ExecutionPolicy Bypass`.

Clone your fork of the repo, and run the script `.\docs\scripts\dev-bootstrap-win.ps1`, or just download a copy of the script by itself, and run it.

```
curl -o dev-bootstrap-win.ps1 https://raw.githubusercontent.com/boostorg/website-v2/develop/docs/scripts/dev-bootstrap-win.ps1
.\dev-bootstrap-win.ps1
```

Method 2:

Or, instead of running the script, manually install the necessary packages as discussed below. It's only necessary to run each command if that package is missing.

Install choco
```
iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))
# refresh environment
$env:ChocolateyInstall = Convert-Path "$((Get-Command choco).Path)\..\.."
Import-Module "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"
refreshenv
```

Install git
```
choco install -y --no-progress git
```

Install python
```
choco install -y --no-progress python
```

Install just
```
choco install -y --no-progress just
```

Install nvm, npm, and yarn
```
choco install -y --no-progress nvm
# close and open the powershell terminal (admin)
nvm install 20
nvm use 20
npm install -g yarn
```

Install Docker Desktop
```
choco install -y --no-progress docker-desktop
```

In a desktop GUI window, run Docker Desktop, and complete the installation.

Clone the repository and switch to that directory.
```
mkdir -p $HOME\github\_your_user_name_
cd $HOME\github\_your_user_name_
git clone https://github.com/_your_user_name_/website-v2
cd website-v2
cp env.template .env
```

Edit the .env, adding AWS keys.

Continue to the instructions in the top-level README.md file.

Method 3:

This is a more complicated WSL method.

In Powershell, install WSL:
```
wsl --install
Restart-Computer
```

After rebooting, open Powershell (wait a minute, it may continue installing WSL). If the installation hasn't completed for some reason,  `wsl --install` again. After WSL and an Ubuntu distribution have been installed, log in to WSL:
```
wsl
```

When running the Django website, everything should be done from a WSL session, not Powershell, DOS, or git-bash.  Do not `git clone` the files in a DOS window, for example. However, once it's up and running, files may be edited elsewhere. The file path in explorer will be `\\wsl.localhost\Ubuntu\opt\github\boostorg\website-v2`

Continue to the [Ubuntu 22.04 instructions](#ubuntu-2204) below. Return here before executing `docker compose`.

The docker daemon must be launched manually. Open a WSL window and keep it running. Otherwise there will be an error message "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"

```
sudo dockerd
```

Open another terminal:
```
wsl
```

Continue (as root) to the instructions in the top-level README.md file.

## Ubuntu 22.04

Method 1:

The script dev-bootstrap-linux.sh will automatically install prerequisites, and with the --all or --launch flag will also run docker-compose.

While the dev-bootstrap-linux.sh script should be run as a standard user, after it has been all set up, later you will generally run "docker compose" as root. This is to assure that the permissions match inside the container where the user is also root. Another option is to eventually add a Docker Desktop method for linux to the script.

```
curl -o dev-bootstrap-linux.sh https://raw.githubusercontent.com/boostorg/website-v2/develop/docs/scripts/dev-bootstrap-linux.sh
chmod 755 dev-bootstrap-linux.sh
./dev-bootstrap-linux.sh
```

Method 2:

Or, instead of running the script, manually install the necessary packages as discussed below. It's only necessary to run each command if that package is missing.

Install python
```
sudo apt-get install -y python3
```

Install `makedeb` (as a standard user, not root).
```
bash -ci "$(wget -qO - 'https://shlink.makedeb.org/install')"
```

Install `just` (as a standard user, not root).

```
sudo mkdir -p /opt/justinstall
CURRENTUSER=$(whoami)
sudo chown $CURRENTUSER /opt/justinstall
chmod 777 /opt/justinstall
cd /opt/justinstall
git clone 'https://mpr.makedeb.org/just'
cd just
makedeb -si
```

Install nvm, npm, and yarn, if not installed.
```
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
. ~/.bashrc
nvm install 20
nvm use 20
npm install -g yarn
```

Install docker and docker-compose.
```
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

As root, clone the repository and switch to that directory.
```
sudo su -
```

```
mkdir -p /opt/github/boostorg
cd /opt/github/boostorg
git clone https://github.com/boostorg/website-v2
cd website-v2
cp env.template .env
```

Edit the .env, adding AWS keys.

Continue (as the root user) to the instructions in the top-level README.md file. Or if using WSL, review the last few steps in that section again.

On Linux, the advantage of running `docker compose` as root is the userid (0) will match the containers and the shared files. Another option is
to install Docker Desktop, which would allow you to stay as a regular user.

## macOS

Method 1:

The script dev-bootstrap-macos.sh will automatically install prerequisites, and with the --all or --launch flag will also run docker-compose.

As a standard user account, clone your fork of the repo, and run the script `docs/scripts/dev-bootstrap-macos.ps1`, or just download a copy of the script by itself, and run it.

```
curl -o dev-bootstrap-macos.sh https://raw.githubusercontent.com/boostorg/website-v2/develop/docs/scripts/dev-bootstrap-macos.sh
chmod 755 dev-bootstrap-macos.sh
./dev-bootstrap-macos.sh
```

Method 2:

Or, instead of running the script, manually install the necessary packages as discussed below. It's only necessary to run each command if that package is missing.

Install brew
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install rosetta
```
sudo softwareupdate --install-rosetta --agree-to-license
```

Install git
```
brew install git
```

Install python
```
brew install python3
```

Install just
```
brew install just
```

Install nvm, npm, and yarn
```
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
. ~/.zprofile
nvm install 20
nvm use 20
npm install -g yarn
```

Install docker and docker-compose
```
curl -o /tmp/Docker.dmg https://desktop.docker.com/mac/main/arm64/160616/Docker.dmg
sudo hdiutil attach /tmp/Docker.dmg
sudo /Volumes/Docker/Docker.app/Contents/MacOS/install
sudo hdiutil detach /Volumes/Docker
```

In a desktop GUI window, run Docker Desktop, and complete the installation.

Clone the repository and switch to that directory.
```
mkdir -p ~/github/_your_user_name_
cd ~/github/_your_user_name_
git clone https://github.com/_your_user_name_/website-v2
cd website-v2
cp env.template .env
```

Edit the .env, adding AWS keys.

Continue to the instructions in the top-level README.md file.

## Local Development

### Social Login with django-allauth

Follow these instructions to use the social logins through django-allauth on your local machine.

See https://testdriven.io/blog/django-social-auth/ for more information.

#### Github
- Go to https://github.com/settings/applications/new and add a new OAuth application
- Set `http://localhost:8000` as the Homepage URL
- Set `http://localhost:8000/accounts/github/login/callback/` as the Callback URL
- Click whether you want to enable the device flow
   - <img src="https://user-images.githubusercontent.com/2286304/252841283-9a846c68-46bb-4dac-8d1e-d35270c09f1b.png" alt="The GitHub screen that registers a new OAuth app" width="400">
- On completion copy the Client ID and Client Secret to the `.env` file as values of `GITHUB_OAUTH_CLIENT_ID` and `GITHUB_OAUTH_CLIENT_SECRET`.
- Run `direnv allow` and restart your docker containers.

Setup should be complete and you should be able to see an option to "Use Github" on the sign up page.

To test the flow including authorizing Github for the Boost account, log into your GitHub account settings and click **Applications** in the left menu. Find the "Boost" authorization and delete it. The next time you log into Boost with this GitHub account, you will have to re-authorize it.

<img src="https://user-images.githubusercontent.com/2286304/204642346-8b269aaf-4693-4351-9474-0a998b97689c.png" alt="The 'Authorized OAuth Apps' tab in your GitHub Applications" width="400">

This setup process is not something that can currently be automated through terraform because of a lack of relevant Github API endpoints to create Oauth credentials.

#### Google

More detailed instructions at:

https://docs.allauth.org/en/latest/socialaccount/providers/google.html

1. Update the `.env` file with values for:
   1. `TF_VAR_google_cloud_email` (the email address of your Google Cloud account)
   2. `TF_VAR_google_organization_domain` (usually the domain of your Google Cloud account, e.g. "boost.org" if you will be using an @boost.org email address)
   3. `TF_VAR_google_cloud_project_name` (optional, default: localboostdev) - needs to change if destroyed and a setup is needed within 30 days
2. Run `make development-tofu-init` to initialize tofu.
3. Run `make development-tofu-plan` to confirm the planned changes.
4. Run `make development-tofu-apply` to apply the changes.
5. Go to https://console.developers.google.com/
   1. Search for the newly created project, named "Boost Development" (ID: localboostdev by default).
   2. Type "credentials" in the search input at the top of the page.
   3. Select "Credentials" under "APIs & Services".
      1. Click "+ CREATE CREDENTIALS"
      2. Select "OAuth Client ID"
      3. Select Application Type: "Web application"
      4. Name: "Boost Development" (arbitrary)
      5. For "Authorized Javascript Origins" use:`http://localhost:8000`
      6. For "Authorized Redirect URIs" use:
         * `http://localhost:8000/accounts/google/login/callback/`
         * `http://localhost:8000/accounts/google/login/callback/?flowName=GeneralOAuthFlow`
      7. Save
6. From the page that's displayed, update the `.env` file with values for the following:
   - `GOOGLE_OAUTH_CLIENT_ID` should be similar to "k235bn2b1l1(...)asdsk.apps.googleusercontent.com"
   - `GOOGLE_OAUTH_CLIENT_SECRET` should be similar to "LAJACO(...)KLAI612ANAD"
7. Run `direnv allow` and restart your docker containers.

Point 5 above can not be automated through terraform because of a lack of relevant Google Cloud API endpoints to create Oauth credentials.

Setup should be complete and you should be able to see an option to "Use Google" on the sign up page.

#### Additional Notes:
**Working locally**: If you need to run through the login flows multiple times, create a superuser so you can log into the admin. Then, log into the admin and delete your "Social Account" from the admin. This will test a fresh connection to GitHub for your logged-in GitHub user.

### Debugging
For local development there is Django Debug Toolbar, and the option to set a debugger.

#### Common Options
In your env:
- Django Debug Toolbar, enabled by default, can be disabled by setting DEBUG_TOOLBAR=False
- IDE Debugging, disabled by default, can be enabled by uncommenting `PYTHONBREAKPOINT` in your .env file.


#### Set Up Pycharm
You can set up your IDE with a new "Python Debug Server" configuration as:
<img src="images/pycharm_debugger_settings.png" alt="PyCharm Debugger Settings" width="400">

#### Common Usage
To use the debugger add `breakpoint()` somewhere before you want to start debugging and then add breakpoints by clicking on the gutter. The debugger will stop at these point, you can then step/inspect the variables.
