#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import frontmatter
from core.boostrenderer import BoostRenderer
from mistletoe import Document


def process_md(filename):
    with open(filename) as f:
        post = frontmatter.load(f)
        metadata = post.metadata
        content = post.content

        with BoostRenderer() as renderer:
            doc = Document(content)
            rendered = renderer.render(doc)

    return metadata, rendered
