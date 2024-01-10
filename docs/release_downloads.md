# Boost Release Downloads

## Artifactory

- Populate the release downloads by running `./manage.py import_artifactory_release_data`. See [Management Commands](./commands.md#import_artifactory_release_data) for more information.
- Downloads for new versions populate as part of the new version import process
- Existing data can be refreshed by running `./manage.py import_artifactory_release_data` in the desired environment
- Environment variables: `ARTIFACTORY_URL` and `MIN_ARTIFACTORY_RELEASE`. See the [Envrionment Variables](./env_vars.md) for more information.

The Artifactory API URL in `ARTIFACTORY_URL` allows us to retrieve the data about the downloads from the Artifactory API.

The URLs for the downloads themselves are retrieved from the URLs provided to us by the Artifactory API. We don't generate the download links ourselves.
