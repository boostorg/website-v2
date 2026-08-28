"""Which changed file paths count as documentation.

The commit importer counts these per commit, and the Documenter achievement is
derived from that count. Kept in one place so tightening the rules is a small diff
rather than a hunt.
"""

from pathlib import PurePosixPath

DOC_DIRECTORIES = frozenset({"doc", "docs"})
DOC_SUFFIXES = frozenset({".adoc", ".qbk", ".rst", ".md"})
# Build output, committed in some repos. It outnumbers the sources it was
# generated from by orders of magnitude.
GENERATED_DIRECTORIES = frozenset({"html"})
IGNORED_DIRECTORIES = frozenset({".github"})
IGNORED_SUFFIXES = frozenset({".json", ".yml", ".yaml", ".cmake", ".jam"})
IGNORED_NAME_PREFIXES = ("Jamfile",)


def resolve_rename(path):
    """Take the destination of a rename, which git reports as one path.

    Two shapes: ``doc/{old => new}/index.adoc``, and ``old.adoc => new.adoc``
    where the paths share no prefix.
    """
    if "=>" not in path:
        return path
    if "{" in path and "}" in path:
        before, rest = path.split("{", 1)
        inner, after = rest.split("}", 1)
        _, _, destination = inner.partition("=>")
        return f"{before}{destination.strip()}{after}".replace("//", "/")
    return path.split("=>", 1)[1].strip()


def is_doc_path(path):
    """True if changing ``path`` counts as documentation work."""
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    directories, name = set(parts[:-1]), parts[-1]
    if directories & (IGNORED_DIRECTORIES | GENERATED_DIRECTORIES):
        return False
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in IGNORED_SUFFIXES or name.startswith(IGNORED_NAME_PREFIXES):
        return False
    if directories & DOC_DIRECTORIES:
        return True
    if not directories and name.lower() == "readme.md":
        # A README at the repository root introduces the library rather than
        # documenting it.
        return False
    return suffix in DOC_SUFFIXES


def count_doc_files(stat_lines):
    """Count the documentation files in ``git log --numstat`` output lines.

    A binary file reports ``-`` for its line counts and is classified on its path
    like any other.
    """
    total = 0
    for line in stat_lines:
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        if is_doc_path(resolve_rename(fields[2].strip())):
            total += 1
    return total
