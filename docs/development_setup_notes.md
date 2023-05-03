## Development Setup Notes

The procedure to configure a development environment is mainly covered in the top-level README.md. This document will contain more details about installing prerequisites: Just, Python 3.11, Docker, and Docker Compose.

- [Windows](#Windows)
- [Ubuntu 22.04](#ubuntu-2204)


## Windows

(Tested on: Windows 2022 Server)

In Powershell, install WSL:
```
wsl --install
Restart-Computer
```

After rebooting, open Powershell (wait a minute, it may continue installing WSL). If the installation hasn't completed for some reason,  `wsl --install` again. After WSL and an Ubuntu distribution have been installed, log in to WSL:
```
wsl
```

When running the Django website, everything should be done from a WSL session, not Powershell, DOS, or git-bash.  Do not `git clone` the files in a DOS window, for example. However, once it's up and running, files may be edited elsewhere. The file path in explorer will be `\\wsl.localhost\Ubuntu\opt\github\cppalliance\temp-site`

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

Check if python 3.11 is installed.
```
python3 --version
```

or install python 3.11:
```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11
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
mkdir -p /opt/github/cppalliance
cd /opt/github/cppalliance
git clone https://github.com/cppalliance/temp-site
cd temp-site
cp env.template .env
```

Continue (as the root user) to the instructions in the top-level README.md file. Or if using WSL, review the last few steps in that section again.

The advantage of running `docker compose` as root is the userid (0) will match the containers and the shared files.
