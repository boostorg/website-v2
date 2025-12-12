# Production/Staging Server setup for allauth

For development see [development_setup_notes_native.md](development_setup_notes_native.md).

For this setup adjustments will need to be made to the values as applicable for each server and service.

### Social Login with django-allauth

Follow these instructions to use the social logins through django-allauth.

See https://testdriven.io/blog/django-social-auth/ for more information.

#### Github
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

#### Google

More detailed instructions at:

https://docs.allauth.org/en/latest/socialaccount/providers/google.html

Go to https://console.developers.google.com/ and create a new project. Create OAuth 2.0 credentials.

The client id is the full value including domain and tld.

For the "authorized javascript origins" values use:

* `http://localhost:8000`

For the "authorized redirect URIs" use:

* `http://localhost:8000/accounts/google/login/callback/`
* `http://localhost:8000/accounts/google/login/callback/?flowName=GeneralOAuthFlow`
