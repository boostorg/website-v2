# we only want boost devel for now, leaving the others in case that changes.
ML_STATS_URLS = [
    "https://lists.boost.org/Archives/boost/{:04}/{:02}/author.php",
    # "https://lists.boost.org/boost-users/{:04}/{:02}/author.php",
    # "https://lists.boost.org/boost-announce/{:04}/{:02}/author.php",
]
ARG_DATE_REGEX = r"^([0-9]+)(?:$|(?:-|/)([0-9]+)(?:$|(?:-|/)([0-9]+)$))"
AUTHOR_PATTERN_REGEX = r"<li><strong>(.*)</strong>"
DATE_PATTERN_REGEX = r".*<em>\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)</em>"

# used to map latin-1 characters to their utf-8 equivalents in the mailing list
# page html parser
LATIN_1_EQUIVS = {
    8364: 128,
    8218: 130,
    402: 131,
    8222: 132,
    8230: 133,
    8224: 134,
    8225: 135,
    710: 136,
    8240: 137,
    352: 138,
    8249: 139,
    338: 140,
    381: 142,
    8216: 145,
    8217: 146,
    8220: 147,
    8221: 148,
    8226: 149,
    8211: 150,
    8212: 151,
    732: 152,
    8482: 153,
    353: 154,
    8250: 155,
    339: 156,
    382: 158,
    376: 159,
}
