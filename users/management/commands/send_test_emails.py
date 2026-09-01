"""Send the transactional email templates to a test inbox.

Frontend test helper only -- this does NOT touch the real sign-up / password
reset flows. It renders the
templates in ``templates/emails/`` and sends them through the project's
configured email backend (``settings.EMAIL_BACKEND``) -- the same backend the
real transactional emails use. Locally that is the ``maildev`` SMTP container
(``EMAIL_HOST``/``EMAIL_PORT``); deployed environments use the configured email
service provider.

Examples
--------
Send both emails to your local maildev inbox::

    python manage.py send_test_emails --to you@example.com

By default the email images are embedded inline (multipart/related CID parts) so
they render even when the static host is not publicly reachable. This works with
both SMTP backends (maildev, or your own SMTP server) and API
email-service-provider backends (any Anymail backend). Pass
``--no-inline-images`` together with ``--base-url`` to instead reference the
images served from the real host (S3 large-static).

To send real preview emails through your own email service provider in local
development, point the email settings at it -- an SMTP provider via the
``EMAIL_*`` settings, or an Anymail API backend via ``EMAIL_BACKEND`` +
``ANYMAIL`` -- and use a ``DEFAULT_FROM_EMAIL`` / ``--from-email`` on a domain
that provider has verified.
"""

import re
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from email.message import EmailMessage as PyEmailMessage
from email.mime.image import MIMEImage

import djclick as click
from allauth.account import app_settings as allauth_account_settings
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from users.utils import humanize_link_lifetime

SAMPLE_ENTRY = SimpleNamespace(
    title="Boost 1.90.0 has been released",
    content=(
        "This release adds two new libraries and includes fixes across the "
        "collection. See the release notes for the full list of changes, "
        "acknowledgements and known issues."
    ),
    tag="news",
    slug="boost-1-90-0-has-been-released",
    created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    author=SimpleNamespace(display_name="Vinnie Falco", email="vinnie@example.com"),
)

SAMPLE_LISTS = [
    {
        "name": "Boost Users",
        "address": "boost-users@lists.boost.org",
        "description": "Questions and discussion about using the Boost libraries.",
    },
    {
        "name": "Boost Developers",
        "address": "boost@lists.boost.org",
        "description": "Development of the Boost libraries themselves.",
    },
]

# Available templates: key -> template prefix, a sample CTA link and any
# context the template needs beyond the shared base below.
TEMPLATES = {
    "confirm": {
        "prefix": "emails/confirm_email",
        "action_url": "https://www.boost.org/auth/confirm?token=test-confirm-token-abc123",
    },
    "password_reset": {
        "prefix": "emails/password_reset",
        "action_url": "https://www.boost.org/auth/reset?token=test-reset-token-xyz789",
    },
    "unknown_account": {
        "prefix": "emails/unknown_account",
        "action_url": "https://www.boost.org/v3/accounts/signup/",
    },
    "account_deletion_scheduled": {
        "prefix": "emails/account_deletion_scheduled",
        "action_url": "https://www.boost.org/accounts/login/",
    },
    "news_needs_moderation": {
        "prefix": "news/emails/needs_moderation",
        "action_url": "https://www.boost.org/news/magic-approve/test-token-abc123/",
        "context": {
            "entry": SAMPLE_ENTRY,
            "approval_magic_link": (
                "https://www.boost.org/news/magic-approve/test-token-abc123/"
            ),
            "detail_url": (
                "https://www.boost.org/news/boost-1-90-0-has-been-released/"
            ),
            "moderate_url": "https://www.boost.org/news/moderate/",
            "expiration_hours": 24,
            "with_preferences": True,
        },
    },
    "news_approved": {
        "prefix": "news/emails/approved",
        "action_url": "https://www.boost.org/news/boost-1-90-0-has-been-released/",
        "context": {"entry": SAMPLE_ENTRY, "with_preferences": True},
    },
    "news_posted": {
        "prefix": "news/emails/posted",
        "action_url": "https://www.boost.org/news/boost-1-90-0-has-been-released/",
        "context": {"entry": SAMPLE_ENTRY, "with_preferences": True},
    },
    "mailing_list_confirm": {
        "prefix": "v3/mailing_list/email/confirm_subscription",
        "action_url": "https://www.boost.org/mailing-list/confirm/test-token-abc123/",
        "context": {"lists": SAMPLE_LISTS, "expiry_label": "7\u00a0days"},
    },
    "verify_commit_email": {
        "prefix": "v3/libraries/email/verify_commit_email",
        "action_url": "https://www.boost.org/libraries/commit-email/confirm/test-token/",
        "context": {"requester": "Vinnie Falco", "expiry_label": "7\u00a0days"},
    },
}


def build_context(key, base_url, first_name="Vinnie", email="you@example.com"):
    """Sample context for one template, matching what the real flow passes."""
    scheme, _, host = base_url.partition("://")
    if not host:  # base_url given without a scheme
        scheme, host = "https", base_url

    spec = TEMPLATES[key]
    extra = dict(spec.get("context", {}))
    # Only the notification emails carry the footer's preferences link; the
    # base template omits that sentence without it.
    preferences_url = (
        f"{base_url}/users/me/" if extra.pop("with_preferences", False) else ""
    )
    return {
        "scheme": scheme,
        "host": host,
        "first_name": first_name,
        "user_email": email,
        "email": email,
        "action_url": spec["action_url"],
        "preferences_url": preferences_url,
        # Account-deletion-scheduled email context.
        "grace_days": settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS,
        "postorius_url": settings.POSTORIUS_URL,
        # Link lifetimes shown in the email bodies, sourced from the same
        # settings the real flows enforce (allauth email confirmation in days,
        # Django's password reset token timeout in seconds).
        "confirmation_link_lifetime": humanize_link_lifetime(
            timedelta(days=allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)
        ),
        "password_reset_link_lifetime": humanize_link_lifetime(
            timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)
        ),
        **extra,
    }


def render_template(key, base_url="https://www.boost.org", **kwargs):
    """Render one template's subject, text and HTML bodies."""
    context = build_context(key, base_url, **kwargs)
    prefix = TEMPLATES[key]["prefix"]
    return (
        render_to_string(f"{prefix}_subject.txt", context).strip(),
        render_to_string(f"{prefix}.txt", context),
        render_to_string(f"{prefix}.html", context),
    )


# Matches the URL of any email image, e.g. src="/static/static-large/img/emails/x.png"
# (local dev) or the absolute S3 URL (prod) -- both end in "img/emails/<file>".
EMAIL_IMG_RE = re.compile(r'src="[^"]*?(img/emails/[^"]+\.(?:png|jpe?g))"')
EXT_SUBTYPE = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg"}


def _collect_inline_images(html):
    """Rewrite email image ``src`` to ``cid:`` refs; return (html, images).

    ``images`` is a list of ``(cid, subtype, bytes)`` for each referenced file.
    """
    relpaths = {m.group(1) for m in EMAIL_IMG_RE.finditer(html)}
    html = EMAIL_IMG_RE.sub(
        lambda m: 'src="cid:{}"'.format(m.group(1).split("/")[-1]), html
    )
    images = []
    for relpath in sorted(relpaths):
        # Email images are served from large static (static/static-large/, synced
        # to S3); the rendered URL drops that prefix, so add it back to locate the
        # file on disk for inline embedding.
        path = finders.find(f"static-large/{relpath}")
        if not path:
            raise click.ClickException(f"Static file not found: {relpath}")
        cid = relpath.split("/")[-1]
        subtype = EXT_SUBTYPE[relpath.rsplit(".", 1)[1].lower()]
        with open(path, "rb") as fh:
            images.append((cid, subtype, fh.read()))
    return html, images


def _send_inline(connection, subject, text_body, html_body, from_email, recipient):
    """Send a message with inline (CID) images, for any email backend.

    The two backends need different handling (Django 6 dropped the high-level
    ``multipart/related`` hooks, so attachments otherwise land in a flat
    ``multipart/mixed``):

    * SMTP (maildev, or your own SMTP server) -- hand-build a proper
      ``multipart/alternative[text, multipart/related[html, images]]`` tree so
      clients render the ``cid:`` references inline.
    * API email service provider (any Anymail backend) -- attach the images
      as ``Content-ID`` inline parts; Anymail turns those into the provider's
      native inline images.
    """
    html_body, images = _collect_inline_images(html_body)

    if "smtp" in settings.EMAIL_BACKEND:
        msg = PyEmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = recipient
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
        # The HTML alternative is the last payload; attach the images to it so
        # they form a multipart/related group resolving the cid: references.
        html_part = msg.get_payload()[-1]
        for cid, subtype, data in images:
            html_part.add_related(
                data, maintype="image", subtype=subtype, cid=f"<{cid}>"
            )
        connection.open()
        # No from_addr/to_addrs: let smtplib derive the envelope from the
        # headers so a "Name <addr>" --from-email still yields a bare MAIL FROM.
        connection.connection.send_message(msg)
        return

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[recipient],
        connection=connection,
    )
    msg.attach_alternative(html_body, "text/html")
    for cid, subtype, data in images:
        image = MIMEImage(data, _subtype=subtype)
        image.add_header("Content-ID", f"<{cid}>")
        image.add_header("Content-Disposition", "inline", filename=cid)
        msg.attach(image)
    msg.send()


@click.command()
@click.option("--to", "recipient", required=True, help="Recipient email address.")
@click.option(
    "--template",
    "which",
    type=click.Choice([*TEMPLATES, "all"]),
    default="all",
    show_default=True,
    help="Which template(s) to send.",
)
@click.option("--first-name", default="Vinnie", show_default=True)
@click.option(
    "--user-email",
    default="",
    help="Account email shown in the password reset body (defaults to --to).",
)
@click.option(
    "--from-email",
    default=settings.DEFAULT_FROM_EMAIL,
    show_default=True,
    help=(
        "From address. Overrides DEFAULT_FROM_EMAIL -- use a domain your email "
        "service provider has verified (most providers require the sender "
        "domain to be verified)."
    ),
)
@click.option(
    "--base-url",
    default="https://www.boost.org",
    show_default=True,
    help="scheme://host used to build absolute asset/link URLs.",
)
@click.option(
    "--inline-images/--no-inline-images",
    default=True,
    show_default=True,
    help="Embed images as inline CID parts (recommended for previews).",
)
@click.option(
    "--delay",
    type=float,
    default=0.0,
    show_default=True,
    help=(
        "Seconds to wait between messages (raise it if your email service "
        "provider rate-limits bursts)."
    ),
)
def command(
    recipient,
    which,
    first_name,
    user_email,
    from_email,
    base_url,
    inline_images,
    delay,
):
    """Render and send the transactional email templates."""
    # Use the project's configured email backend -- the same one the real
    # transactional emails go through (local maildev SMTP, or the deployed
    # email service provider).
    connection = get_connection()
    is_smtp = "smtp" in settings.EMAIL_BACKEND
    target = (
        f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT}"
        if is_smtp
        else settings.EMAIL_BACKEND
    )

    keys = list(TEMPLATES) if which == "all" else [which]
    click.secho(f"Sending via {target} -> {recipient}", fg="green")

    for index, key in enumerate(keys):
        if index and delay:
            time.sleep(delay)
        subject, text_body, html_body = render_template(
            key,
            base_url=base_url,
            first_name=first_name,
            email=user_email or recipient,
        )

        if inline_images:
            _send_inline(
                connection, subject, text_body, html_body, from_email, recipient
            )
        else:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[recipient],
                connection=connection,
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send()
        click.secho(f"  sent: {key} — {subject!r}", fg="cyan")

    connection.close()
    click.secho("Done.", fg="green")
