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
   2. `TF_VAR_google_organization_domain` (usually the domain of your Google Cloud account, e.g. "boost.org" if you will be using a @boost.org email address)
   3. `TF_VAR_google_cloud_project_name` (optional, default: localboostdev) - needs to change if destroyed and a setup is needed within 30 days
2. Run `just development-tofu-init` to initialize tofu.
3. Run `just development-tofu-plan` to confirm the planned changes.
4. Run `just development-tofu-apply` to apply the changes.
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

Point 5 above can not be automated through terraform because of a lack of relevant Google Cloud API endpoints to create Oauth credentials.

Setup should be complete and you should be able to see an option to "Use Google" on the sign up page.

#### Additional Notes on allauth login flows:
**Working locally**: If you need to run through the login flows multiple times, create a superuser so you can log into the admin. Then, log into the admin and delete your "Social Account" from the admin. This will test a fresh connection to GitHub for your logged-in GitHub user.
