from core.asciidoc_translators.base import AsciidocBaseTranslator


class AtLinkTranslator(AsciidocBaseTranslator):
    pattern = r"at::([a-zA-Z/#_0-9]+)\[([\S\s]+)\]"
    substitution = r"link:\1[\2]"
