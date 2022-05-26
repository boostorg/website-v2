import frontmatter
from mistletoe import Document, HTMLRenderer


def process_md():
    with open("content/test.md") as f:
        post = frontmatter.load(f)
        metadata = post.metadata
        content = post.content

        with HTMLRenderer() as renderer:
            doc = Document(content)
            rendered = renderer.render(doc)

    return metadata, rendered
