## Development Setup Notes

The procedure to configure a development environment is mainly covered in the top-level README.md. This document will contain more details about installing prerequisites: Just, Python 3.11, Docker, and Docker Compose.

- [Development Setup Notes](#development-setup-notes)
- [Windows](#windows)
- [Ubuntu 22.04](#ubuntu-2204)
- [Local Development](#local-development)
  - [Social Login with django-allauth](#social-login-with-django-allauth)


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

Check if python3 is installed.
```
python3 --version
```

or

```
apt-get install -y python3
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
```

```
mkdir -p /opt/github/boostorg
cd /opt/github/boostorg
git clone https://github.com/boostorg/website-v2
cd website-v2
cp env.template .env
```

Continue (as the root user) to the instructions in the top-level README.md file. Or if using WSL, review the last few steps in that section again.

The advantage of running `docker compose` as root is the userid (0) will match the containers and the shared files.

## Local Development

### Social Login with django-allauth

Follow these instructions to use the social logins through django-allauth on your local machine.

See https://testdriven.io/blog/django-social-auth/ for more information.

- Go to https://github.com/settings/applications/new and add a new OAuth application
- Set `http://localhost:8000` as the Homepage URL
- Set `http://localhost:8000/accounts/github/login/callback/` as the Callback URL
- Click whether you want to enable the device flow

<img src="https://user-images.githubusercontent.com/2286304/252841283-9a846c68-46bb-4dac-8d1e-d35270c09f1b.png" alt="The GitHub screen that registers a new OAuth app" width="400">

- Log in to the admin
- Click on Social Applications


<img src="https://user-images.githubusercontent.com/2286304/204597123-3c8ae053-1ba8-4347-bacd-784fe52b2a04.png" alt="The Social Accounts section of the Django admin" width="400">

- Click **Add Social Application**
- Choose GitHub as the provider
- Enter a name like "GitHub OAuth Provider"
- Enter the Client ID from GitHub
- Go back to GitHub and generate a new Client Secret, then copy it into the **Secret Key** field. Choose the site as a **Chosen sites** and save.

<img src="https://user-images.githubusercontent.com/2286304/204648736-79aed1be-4b32-4946-be97-27e7c859603d.png" alt="Screenshot of where to get the Client ID and Client Secret" width="400">

It's ready!

**Working locally**: If you need to run through this flow multiple times, create a superuser so you can log into the admin. Then, log into the admin and delete your "Social Account" from the admin. This will test a fresh connection to GitHub for your logged-in GitHub user.

To test the flow including authorizing Github for the Boost account, log into your GitHub account settings and click **Applications** in the left menu. Find the "Boost" authorization and delete it. The next time you log into Boost with this GitHub account, you will have to re-authorize it.

<img src="https://user-images.githubusercontent.com/2286304/204642346-8b269aaf-4693-4351-9474-0a998b97689c.png" alt="The 'Authorized OAuth Apps' tab in your GitHub Applications" width="400">
