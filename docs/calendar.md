<!--
Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)

Distributed under the Boost Software License, Version 1.0. (See accompanying
file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/boostorg/website-v2
-->
# Events Calendar

The "Schedule of Events" section on the homepage dynamically display upcoming events from the Boost Google Calendar. See the settings in [Environment Variables](./env_vars.md).

- See the settings in [Environment Variables](./env_vars.md).
- Main code for event retrieval is in `core/calendar.py`
- Raw data is extracted from the Google Calendar API
- The raw data is processed to extract the event data that we want to display, and sorted into the order we want
- The home page caches the result, and attempts to retrieve the events from the cache before hitting the Google Calendar API
