# Boost Static Content

**Static Content** refers to content such as HTML files, markdown files, asciidoc files, etc. that is retrieved from Amazon S3 and rendered within the Boost site.

We can add "shortcut" URL paths to specific directories or files within S3 by updating the file `stage_static_config.json`.

## Quick Start

### Adding a shortcut url to a static page

1. Identify the URL pattern you would like to use. Example: `/style-guide/`
2. Identify the S3 path to the file you would like that URL to load. Example: `/site-pages/develop/style-guides.adoc`
3. Add an entry to `stage_static_config.json`. `site_path` is your URL route, with a `/` on either side. `s3_path` is the path to your desired file in S3, with a leading `/`:

```javascript
  ...
  },
  {
    "site_path": "/style-guide/",
    "s3_path": "/site-pages/develop/style-guides.adoc"
  },
  {
  ...
```

4. Restart your server and load `/style-guide/` in your browser to confirm it works.

## About Retrieving Static Content

An example shortcut url is the `/help/` page. This is the route that the `/help/` URL takes to render that page:

- The user enters `/help/` into the browser
- There is no `help/` path in `config/urls.py`, so the route falls through to the view that handles static content, `StaticContentTemplateView`.
- In this view, the `content_path` will be `help` . The view uses the `content_path` to try and retrieve the content for the `/help/` page from the Redis cache, the `RenderedContent` table, or from Amazon S3.
- The logic for retrieving the content from Amazon S3 is stored in `core/boostrenderer.py::get_content_from_s3()`. See [Retrieving Static Content from the Boost Amazon S3 Bucket](#retrieving-static-content-from-the-boost-amazon-s3-bucket) and [How we decide which S3 keys to try](#how-we-decide-which-s3-keys-to-try) for more information.
- Back in the view, if the view receives content from S3 (or the Redis cache or the database), it will return that. Otherwise, a 404 is raised.

## Retrieving Static Content from the Boost Amazon S3 Bucket

The `StaticContentTemplateView` class (in the `core/` app) is a Django view that handles requests for static content. It inherits from `BaseStaticContentTemplateView`, which is the class that contains the bulk of the logic.

Its URL path is the very last path in our list of URL patterns (see `config/urls.py`) because it functions as the fallback URL pattern. If a user enters a URL that doesn't match anything else defined in our URL patterns, this view will attempt to retrieve the request as static content from S3 using the URL path.

`StaticContentTemplateView` calls S3 using the URL pattern. The S3 retrieval code in `core/boostrenderer.py::get_content_from_s3()` generates a list of potential keys to check. It then checks the specified S3 bucket for each of those keys and returns the first match it finds, along with the file content type. Passing the content type with the bucket contents allows the content to be delivered appropriately to the user (so HTML files will be rendered as HTML, etc.)

Boost uses the AWS SDK for Python (boto3) to connect to an S3 bucket and retrieve the static content. If no bucket name is provided, pur process uses the `STATIC_CONTENT_BUCKET_NAME` setting from the Django project settings.

## How we decide which S3 keys to try

The JSON config file `{env}_static_config.json` is used to map site paths to corresponding paths in the Amazon S3 bucket where static content is stored. This mapping is used to create shortcuts to static content files in the S3 bucket, which can be accessed using URLs that correspond to the site paths.

The `{env}_static_config.json` file is a list of objects, where each object represents a mapping between a site path and an S3 path. Each object has two properties: `site_path` and `s3_path`.

The `site_path` property is the path to the static content file as it appears in the web application. For example, if the static content file is located at `/static/js/main.js`, the site path would be `/static/js/`.

The `s3_path` property is the path to the static content file in the S3 bucket. For example, if the S3 bucket is named `my-bucket` and the static content file is located at `my-bucket/site/develop/js/main.js`, the S3 path would be `/site/develop/js/`.

When a request is made to a URL that corresponds to a site path, the get_content_from_s3() function looks up the site path in the `{env}_static_config.json` file to find the corresponding S3 path. It then uses the S3 path to retrieve the static content from the S3 bucket.

Take a look at this sample `{env}_static_config.json` file:

```javascript
[
    {
        "site_path": "/develop/libs/",
        "s3_path": "/site/develop/libs/"
    },
    {
        "site_path": "/develop/doc/",
        "s3_path": "/site/develop/doc/html/"
    },
    {
      "site_path": "/doc/_/",
      "s3_path": "/site-docs/develop/_/"
    },
    {
        "site_path": "/",
        "s3_path": "/site/develop/"
    }
]
```

**Example 1**: If the URL request is for `/develop/libs/index.html`, the S3 keys that we would try are:

- `/site/develop/libs/index.html`

Note that the `site_path` and the `s3_path` don't have to be to the same depth; the `site_path` in this example is 2 levels deep, and the `s3_path` is 3 levels deep. It doesn't matter.

**Example 2**: If the URL request is for `/develop/doc/index.html`, the S3 keys that the function would try are:

- `/site/develop/doc/html/index.html`
- `/site/develop/doc/index.html`

**Example 3**: If the url request is for `/doc/accumulators/`, the S3 keys that the function would try are:

- `/site-docs/develop/accumulators/`
- `/site-docs/develop/accumulators/index.html`

In this example, the `_` functions as a wildcard, so `/doc/accumulators/` would shortcut to `/site-docs/develop/accumulators/`, and `/doc/algorithm/` would shortcut to `/site-docs/develop/algorithm/`, even though neither `accumulators` nor `algorithm` have their own entries in the config file.

**Example 4**: If the URL request is for `/index.html`, the S3 keys that the function would try are:

- `/site/develop/index.html`
- `/site/index.html`

We first try to retrieve the static content using the exact S3 key specified in the site-to-S3 mapping. If we can't find the content using that key, we will try alternative S3 keys based on the `site_path` and `s3_path` properties in the `{env}_static_config.json` file.

## Caching

See [Caching and the `RenderedContent` model](./caching_rendered_content.md) for how Django-side caching is handled.

Caching is also handled via Fastly CDN.
