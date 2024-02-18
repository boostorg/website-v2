#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import djclick as click

from libraries.github import LibraryUpdater


@click.command()
@click.option("--local", is_flag=True, default=False)
@click.option("--token", is_flag=False, help="Github API token")
def command(local, token):
    """
    Calls the LibraryUpdater, which retrieves the active boost libraries
    from the Boost repo and updates the models in our database with the latest
    information on that library (repo) from GitHub.
    """
    click.secho(
        "Updating libraries -- expect to wait 1-2 minutes before seeing output",
        fg="green",
    )
    updater = LibraryUpdater(token=token)
    updater.update_libraries()
    click.secho("Finished importing libraries.", fg="green")
