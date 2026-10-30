"""Display equivalence only; source IDs and model classes remain distinct."""
import re
import unicodedata

SOURCE_SUFFIX = re.compile(r'(?:\s*\[(?:sheet[- :][^\]]+|pdf-[^\]]+|pec-[^\]]+|u:[^\]]+)\])+\s*$', re.I)


def legend_description(name):
    return SOURCE_SUFFIX.sub('', name).strip()


def meaning_key(name):
    label = re.sub(r'\s*\((new|old)\)\s*$', '', legend_description(name), flags=re.I)
    return ' '.join(unicodedata.normalize('NFKC', label).casefold().split())


def same_meaning(names):
    keys = {meaning_key(name) for name in names}
    return len(keys) == 1 and not re.search(r'\b(unknown|unresolved|unclassified|unspecified)\b', next(iter(keys), ''))
