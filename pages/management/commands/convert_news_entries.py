import djclick as click
from wagtail.models import Page
from wagtail.images.models import Image

from pages.models import PostPage
from pages.models import PostIndexPage

from news.models import Video
from news.models import News
from news.models import BlogPost
from news.models import Link
from news.models import Entry

from django.template.defaultfilters import urlize
from django.template.defaultfilters import linebreaks_filter


def get_or_create_page(entry: Entry, index_page: PostIndexPage) -> PostPage:
    try:
        page = index_page.get_children().get(title=entry.title).specific
    except Page.DoesNotExist:
        page = PostPage(
            title=entry.title,
            first_published_at=entry.publish_at,
            owner=entry.author,
        )
        index_page.add_child(instance=page)
    return page


def convert_text_content(content: str):
    r_content = content
    r_content = urlize(r_content)
    r_content = linebreaks_filter(r_content)
    return r_content


def convert_image(entry: Entry, post_page: PostPage):
    image = entry.image
    wagtail_image, _ = Image.objects.get_or_create(
        title=image.name,
        defaults={"width": image.width, "height": image.height, "file": image},
    )
    post_page.image = wagtail_image
    post_page.save()


def basic_conversion(entry: Entry, index_page: PostIndexPage):
    print(f"Creating or updating PostPage {entry.title}")
    page = get_or_create_page(entry, index_page)
    if entry.image:
        convert_image(entry, page)
    if entry.summary:
        page.summary = entry.summary
    return page


@click.command()
def command():
    post_index_page = PostIndexPage.objects.first()
    if not post_index_page:
        raise Exception(
            "No Post Index Page found. Create one before running this command."
        )

    blogs_posts = BlogPost.objects.all()
    print(f"Creating or updating {blogs_posts.count()} Blog Posts")
    for bp in blogs_posts:
        page = basic_conversion(bp, post_index_page)
        page.content = [
            {
                "type": "markdown",
                "value": convert_text_content(bp.content),
            }
        ]
        page.save()
    news_posts = News.objects.all()
    print(f"Creating or updating {news_posts.count()} News Posts")
    for np in news_posts:
        page = basic_conversion(np, post_index_page)
        page.content = [
            {
                "type": "markdown",
                "value": convert_text_content(np.content),
            }
        ]
        page.save()
    videos = Video.objects.all()
    print(f"Creating or updating {news_posts.count()} Videos")
    for video in videos:
        page = basic_conversion(video, post_index_page)
        page.content = [
            {
                "type": "video",
                "value": {"video": video.external_url},
            }
        ]
        page.save()

    links = Link.objects.all()
    print(f"Creating or updating {links.count()} Links")
    for link in links:
        page = basic_conversion(link, post_index_page)
        page.content = [
            {
                "type": "url",
                "value": link.external_url,
            }
        ]
        page.save()
