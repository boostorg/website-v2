# Email Routing and the QA Inbox

## How email is routed per environment

| Environment | Backend | Where messages go |
| --- | --- | --- |
| Local development | SMTP | The `maildev` container in `docker-compose.yml`, inbox at http://localhost:1080 |
| `cppal-dev` | SMTP | The in-cluster `maildev` pod, inbox at https://www.cppal-dev.boost.org/maildev/ |
| `stage` | SMTP | The in-cluster `maildev` pod, inbox at https://www.stage.boost.org/maildev/ |
| `production` | Mailgun (Anymail) | Real recipients |
| Tests | `locmem` | `django.core.mail.outbox`, see `config/test_settings.py` |

Non-production environments deliberately send nothing to real recipients. This makes it safe to test flows against real user accounts (sign-in verification, moderation notices, subscription confirmations) without those users receiving anything, and it keeps QA traffic off the Mailgun sender domain.

Mailman is not affected by any of this. It is driven through `MAILMAN_REST_API_URL`, not Django's email backend.

## `CATCH_ALL_EMAIL` & `X_DEPLOYMENT_ENV`

- Set `CATCH_ALL_EMAIL=true` and `X_DEPLOYMENT_ENV=<env's label>` in `kube/boost/values-stage-gke.yaml` and `kube/boost/values-cppal-dev-gke.yaml`.
- When enabled, `EMAIL_BACKEND` defaults to Django's SMTP backend pointed at `EMAIL_HOST` / `EMAIL_PORT` (`maildev:1025`) instead of Mailgun. The `MAILGUN_*` values in those files stay present but become inert.
- Django raises `ImproperlyConfigured` at startup if this is enabled while `X_DEPLOYMENT_ENV` is `production`. Mis-routing production email should be loud, not silent.
- Default is `false`, so an environment only changes behavior if its values file opts in. Enable it only where a `maildev` pod is also deployed (`maildevInstall: true`), otherwise sends will fail with a connection error.

## Reaching the QA inbox

Open the URL for the environment and enter the basic-auth credentials:

- `stage`: https://www.stage.boost.org/maildev/
- `cppal-dev`: https://www.cppal-dev.boost.org/maildev/

Credentials come from the `maildev-auth` Secret in that namespace, which is created by hand and is not in this repository:

```bash
kubectl -n stage create secret generic maildev-auth \
  --from-literal=web_user='<user>' \
  --from-literal=web_pass='<password>'
```

The pod will not start until that Secret exists. Ask an operator for the credentials rather than reading them out of the cluster.

Things worth knowing before someone reports them as bugs:

- **The inbox is ephemeral.** maildev holds messages in memory, so a pod restart (including every deploy that rolls it) empties the inbox. There is no retention by design.
- **The inbox updates live.** New messages appear without refreshing, over a websocket.
- **Do not publish the URL.** maildev applies basic auth as Express middleware, but its socket.io channel is attached to the raw HTTP server and bypasses that middleware, so the live message feed is readable by anyone who can reach the path. The password gate deters casual access; it is not a security boundary. The inbox contains real user addresses and working sign-in links for the QA database.

## How it is wired

- `kube/boost/templates/maildev.yaml` holds everything, behind `maildevInstall`: the `Deployment`, a `ClusterIP` `Service`, and (for Gateway environments) an `HTTPRoute`, a `HealthCheckPolicy` and a `GCPBackendPolicy`.
- Django reaches SMTP at `maildev:1025` over cluster DNS. That port is never exposed outside the cluster.
- The inbox is published as a `/maildev` path on the environment's `mainFqdn`, via a second `HTTPRoute` on the existing Gateway. It reuses the existing static IP and certificate, so no DNS record or certificate is involved, and the traffic never reaches Django or the app pods.
- `MAILDEV_BASE_PATHNAME=/maildev` makes maildev serve itself under that prefix, so no URL rewriting is needed at the edge. The socket.io endpoint moves under the same prefix and is covered by the same route.
- The `HealthCheckPolicy` targets `/maildev/healthz`, the only path maildev exempts from basic auth. A health check against `/` would get a 401, which the load balancer reads as an unhealthy backend.
- The `GCPBackendPolicy` raises `timeoutSec`. On Google load balancers the backend timeout is the maximum *lifetime* of a websocket connection rather than an idle timeout, and the 30 second default would sever the live-update socket every 30 seconds.
- `replicas` must stay at 1. Messages live in the pod's memory, so a second replica would split the inbox.

## Enabling it in another environment

1. In that environment's values file, set `maildevInstall: true` and add `CATCH_ALL_EMAIL: "true"` (plus `EMAIL_HOST: maildev` and `EMAIL_PORT: "1025"`) to the `Env` list.
2. Create the `maildev-auth` Secret in that namespace before deploying.
3. The route is only rendered for environments using the GKE Gateway (`gatewayType: "gce"`). Elsewhere you get the pod and the SMTP sink, and the inbox is reachable with `kubectl -n <ns> port-forward svc/maildev 1080:1080`.
