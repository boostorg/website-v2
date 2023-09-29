# Handling "Unclaimed" User Accounts

This page covers how to handle the User records that are created as part of the upload process from the [first-time data import](./first_time_data_import.md) and through [syncing with GitHub](./syncing_data_with_github.md).

The code for this page lives in the `users/` app.

## About Registration and Login

- We use Django Allauth to handle user accounts
- We do some overriding of their logic for the profile page
- We override the password reset logic as part of allowing users to claim their unclaimed accounts

## About Unclaimed User Accounts

- When libraries are created and updated from GitHub, we receive information on Library Maintainers and Authors.
- Those authors and maintainers are added as Users and then linked to the Library or LibraryVersion record they belong to.
- When they are created, the User accounts have their `claimed` field marked as False. This field defaults to `True`, and will only be `False` for users who were created by an automated process.
- We use the email address and name in the `libraries.json` file for that library to create the User record

## When An Unclaimed User Tries to Register

- If a user tries to register with the same email address as an existing user (a user with `claimed` set to `False`), we interrupt the Django Allauth registration error that happens in this case to check whether the user has been claimed
- If the user has `claimed` set to `False`, we send the user a custom message and send them a password reset email
- On the backend, we interrupt the Django Allauth password reset process to mark users as claimed once their password has been successfully reset
