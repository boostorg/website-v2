from core.asciidoc_translators.base import AsciidocBaseTranslator


class GithubPRTranslator(AsciidocBaseTranslator):
    pattern = r"github_pr::\[([\S]+),([0-9]+)]"
    substitution = r"https://github.com/boostorg/\1/pull/\2[PR#\2]"
