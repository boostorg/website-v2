# Boost Mailing List

Access to the mailing list is granted to Boost users via OAuth using `django-oauth-toolkit`.

## Setting Up Boost as an OAuth identity provider

1. In the admin `/admin/`, create a new **Application** under the **Django OAuth Toolkit** heading.

<img width="245" alt="Screenshot 2024-01-23 at 1 34 44 PM" src="https://github.com/cppalliance/temp-site/assets/2286304/bf6b5b34-e270-483b-861d-eddcaa6cb6d6">

2. Fill in the form:
<img width="1906" alt="Screenshot 2024-01-23 at 1 35 40 PM" src="https://github.com/cppalliance/temp-site/assets/2286304/3f0c9924-7734-41d3-b9fd-d588212c09d7">

  - The `client_id` and `client_secret` will fill in automatically. Make sure to copy and paste them somewhere before you save.
  - Add the `redirect_uri` (this URL will be from the project that hosts the mailing list, and is not in **this** project. A sample URL for testing is `https://www.getpostman.com/oauth2/callback`.)
  - Whatever is in the `name` field will be what the user sees on the authorization screen.
  - Select **confidential** as the client type, and **Authorization code** as the grant type.
  - Save the record.
