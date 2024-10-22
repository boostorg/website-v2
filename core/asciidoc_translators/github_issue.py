from core.asciidoc_translators.base import AsciidocBaseTranslator


class GithubIssueTranslator(AsciidocBaseTranslator):
    pattern = r"github_issue::\[([\S]+),([0-9]+)\]"
    substitution = r"https://github.com/boostorg/\1/issues/\2[#\2]"
