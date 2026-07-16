const { createProxyMiddleware } = require("http-proxy-middleware");
const {
  createDjangoAPIMiddleware,
} = require("storybook-django/src/middleware");

const djangoOrigin = process.env.DJANGO_ORIGIN || "http://localhost:8000";

// storybook-django middleware for the pattern-library API (handles POST body restreaming)
const djangoAPI = createDjangoAPIMiddleware({
  origin: djangoOrigin,
  apiPath: ["/pattern-library/"],
});

module.exports = function expressMiddleware(router) {
  // Pattern library API proxy (POST requests with JSON body)
  djangoAPI(router);

  // Static files proxy (CSS, JS, images, fonts)
  router.use(
    "/static/",
    createProxyMiddleware({
      target: djangoOrigin,
      changeOrigin: true,
    })
  );
};
