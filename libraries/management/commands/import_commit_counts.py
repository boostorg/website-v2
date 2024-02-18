#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import djclick as click

from libraries.tasks import update_commit_counts


@click.command()
@click.option("--token", is_flag=False, help="Github API token")
def command(token):
    """Imports commit counts for all libraries, broken down by month, and saves
    them to the database. This is a one-time import.

    :param token: Github API token
    """
    click.secho("Importing library commit history...", fg="green")
    update_commit_counts(token=token)
    click.secho("Finished importing library commit history", fg="green")
