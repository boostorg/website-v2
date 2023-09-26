# API Documentation

## `/api/v1/import-versions/`

- **Allowed methods:** POST only; no payload
- **Payload**: None
- **Permissions**: Limited to staff users
- Imports all Boost releases that are not already in the database
- Ignores beta releases, release candidates, etc.
- Will also import library-versions, maintainers, and library-version documentation links
