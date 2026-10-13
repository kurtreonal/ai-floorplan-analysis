"""Conservative universal meanings; source identities and model indices survive.

Only identical complete descriptions are aliases. No family/synonym inference:
ratings, mounting, gang count, new/existing and drawing-specific qualifiers stay.
Unknown/unresolved descriptions never establish cross-class equivalence.
"""
import re
import unicodedata


EQUIVALENCE_REVISION = "exact-complete-legend-description-v1"


def meaning_key(name, identity):
    description = " ".join(unicodedata.normalize("NFKC", name).split()).casefold()
    if re.search(r"\b(unknown|unresolved|unclassified|unspecified)\b", description):
        return ("identity", identity)
    return ("meaning", description)


def model_class_groups(classes):
    return {class_id: meaning_key(name, entry)
            for class_id, (name, entry) in classes.items()}
