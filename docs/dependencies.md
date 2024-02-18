<!--
Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)

Distributed under the Boost Software License, Version 1.0. (See accompanying
file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/boostorg/website-v2
-->
# Dependency Management

## How to add a new Python dependency

1. Run `just down` to kill your running containers
1. Add the package to `requirements.in`
1. Run `just pip-compile`, which will add the dependency to `requirements.txt`
1. Run `just rebuild` to rebuild your Docker image to include the new dependencies
2. Run `docker compose up` and continue with development
