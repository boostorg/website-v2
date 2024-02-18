#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import djclick as click

from versions.tasks import import_most_recent_beta_release


@click.command()
@click.option(
    "--delete-versions", is_flag=True, help="Delete all existing beta versions"
)
@click.option("--token", is_flag=False, help="Github API token")
def command(
    delete_versions,
    token,
):
    """
    Import the most recent beta release from GitHub.

    This command will import the most recent beta release from GitHub. If
    --delete-versions is specified, it will delete all existing beta versions
    before importing the most recent beta release.

    If --token is specified, it will use the specified GitHub API token to
    retrieve the release data. Otherwise, it will use the settings value.
    """
    click.secho("Importing most recent beta release...", fg="green")
    import_most_recent_beta_release(delete_old=delete_versions, token=token)
    click.secho("Finished importing most recent beta release.", fg="green")
