import re


class AsciidocBaseTranslator:
    pattern = None
    substitution = None

    def __init__(self):
        self.compiled = re.compile(self.pattern)

    def __call__(self, line: str) -> str:
        if not self.pattern:
            raise NotImplementedError("Subclasses must implement the pattern")
        if not self.substitution:
            raise NotImplementedError("Subclasses must implement the substitution")
        return re.sub(self.compiled, self.substitution, line)
