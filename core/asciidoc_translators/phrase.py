from core.asciidoc_translators.base import AsciidocBaseTranslator


class PhraseTranslator(AsciidocBaseTranslator):
    pattern = r"phrase::\[([a-zA-Z]+),([\s\S]+)\]"
    substitution = r"[.\1]#\2#"
