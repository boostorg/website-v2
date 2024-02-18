<!--
Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)

Distributed under the Boost Software License, Version 1.0. (See accompanying
file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/boostorg/website-v2
-->
# API Documentation

## `/api/v1/import-versions/`

- **Allowed methods:** POST only; no payload
- **Payload**: None
- **Permissions**: Limited to staff users
- Imports all Boost releases that are not already in the database
- Ignores beta releases, release candidates, etc.
- Will also import library-versions, maintainers, and library-version documentation links
