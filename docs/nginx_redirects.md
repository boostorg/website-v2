# Nginx Redirect Generation

`/nginx_redirects_data` contains files used to generate the Nginx redirects configuration:

1. `verified_paths` directory, there are files that cache results for each pass over the docs. While it shouldn't be necessary to re-run analysis of a version's docs, if you need to you should delete the relevant version file in the `verified_paths` directory.
1. `known_redirects.json` is the canonical data for destinations for the redirects by version. More details below.
1. `check_redirects.py` is a script you can use to mass confirm that the destinations in known_redirects.json are valid.

## known_redirects.json
format:
```json
{
  "/doc/libs/1.34.0/boost/archive/impl": {
    "destination": "https://github.com/boostorg/serialization/tree/boost-1.34.0/include/boost/archive/impl",
    "redirect_format": "BoostRedirectFormat"
  }
}
```
The key `/doc/libs/1.34.0/boost/archive/impl` is the path as it will appear in the url.

The `destination` value is the URL to which a visiting user will be 301 redirected.
the `redirect_format` is the format used to generate the redirect in Nginx. For now we only support `BoostRedirectFormat`, more could be added in the future if needed if the format was to change. This is optional really as BoostRedirectFormat is the default, but was added to be explicit about it, for the sake of developer clarity for the future.

Note: The generated output will merge redirects where they all match.


## Generating Nginx Redirects and 404 data
In the root of the repository:

1. update the `VERSION_FILTER` (e.g. "1.30.0-1.88.0") value in Taskfile.yml to any new versions you want to include.
1. run: `task generate-path-data`.
   * For any ACTIVE version that has not been processed before, this will:
     1. generate a new file in `nginx_redirects_data/verified_paths/` with the format: `a.b.c.json` matching the version.
     1. Update `nginx_redirects_data/known_redirects.json` with any new 404 directory paths found in the docs for that version which need a redirect. (LLMs are useful for this)
     1. Optional: you may run `task check-redirect-urls` to verify all the destination urls in `known_redirects.json` return a 200 status.
1. For nginx redicts: Run `task generate-nginx-redirect-list` which will create the redirects in `nginx_redirects_workspace/results/nginx_redirects.conf`
1. For 404 data: Run `task generate-404-list` which will create the 404 data in `nginx_redirects_workspace/results/404_urls.csv`.
1. After inspecting the changes, you should commit any new contents in `verified_paths` and `known_redirects.json` to the repository so the data is available for future runs.

## Troubleshooting

For any issues you might see there are stages to the process of generating the nginx and redirect data, with intermediate files that can be inspected to see where the problem is.

These are generated in nginx_redirects_workspace/ as `stage_1_tarballs.json` and `stage_2_docs_files.json`. Finally the files in `nginx_redirects_data/verified_paths/*.json` will contain the final results for each version and that can also be considered an intermediary stage.
