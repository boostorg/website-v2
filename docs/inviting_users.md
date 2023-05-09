# Inviting New Users 

## Goals 

- Be able to invite specific users to create an account with Boost 
- Invite contributors (authors and maintainers) of libraries who have had stub accounts created for them to claim those accounts 

## `InvitationToken` model 

- Is tied to a user 
- Generates a unique UUID per row 
- Expiration date is based on a setting, after which the invite can no longer be claimed 
- Has a `is_expired` property to tell you whether it's expired 
- The `save()` method sets the expiration date based on the setting 