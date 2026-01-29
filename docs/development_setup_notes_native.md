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

Clone your fork of the repo, and run the script `.\scripts\dev-bootstrap-win.ps1`, or just download a copy of the script by itself, and run it.

```
curl -o dev-bootstrap-win.ps1 https://raw.githubusercontent.com/boostorg/website-v2/develop/scripts/dev-bootstrap-win.ps1
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

Theoretically Docker on Linux can either be "Docker Desktop" or native standard Docker. The latter is much more common on Linux, and currently the script only supports standard Docker. In that context, it's helpful for the user account outside of the containers to match the user account inside the containers, and that can be achieved by running docker-compose and all scripts as 'root'. Switch to root before using dev-bootstrap-linux.sh or docker-compose to assure that the permissions match inside the container where the user is also root userid (0). Another option is to eventually add a "Docker Desktop" method for Linux in the script if there is any interest in that, however most developers seem to be using macOS.

```
curl -o dev-bootstrap-linux.sh https://raw.githubusercontent.com/boostorg/website-v2/develop/scripts/dev-bootstrap-linux.sh
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

## macOS

Method 1:

The script dev-bootstrap-macos.sh will automatically install prerequisites, and with the --all or --launch flag will also run docker-compose.

As a standard user account, clone your fork of the repo, and run the script `scripts/dev-bootstrap-macos.ps1`, or just download a copy of the script by itself, and run it.

```
curl -o dev-bootstrap-macos.sh https://raw.githubusercontent.com/boostorg/website-v2/develop/scripts/dev-bootstrap-macos.sh
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

Edit the .env, adding AWS keys, and adjust values to match your local environment. See [Environment Variables](docs/env_vars.md) for more information.

**NOTE**: Double check that the exposed port assigned to the PostgreSQL
container does not clash with a database or other server you have running
locally.

### Pre-commit Hooks Setup

| Description | Command |
| ---- | ------- |
| 1. Install the `pre-commit` package using `pip` | `pip install pre-commit` |
| 2. Install our list of pre-commit hooks locally | `pre-commit install` |
| 3. Run all hooks for changed files before commit | `pre-commit run` |
| 4. Run specific hook before commit | `pre-commit run {hook}` |
| 5. Run hooks for all files, even unchanged ones | `pre-commit run --all-files` |
| 6. Commit without running pre-commit hooks | `git commit -m "Your commit message" --no-verify` |

Continue to the instructions in the top-level README.md file.

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
