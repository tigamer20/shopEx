"""Text normalisation shared by matching, catalog filters and chain detection.

Kept dependency-free so every service can import it without import cycles
(``matching`` re-exports ``normalise_text`` as part of its contract).
"""

from __future__ import annotations

import re
import unicodedata

# Letters that Unicode decomposition does not split into a base letter plus an accent.
_LIGATURES = str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae", "ß": "ss"})
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")

# Words that carry no meaning for matching ("beurre d'arachide" == "beurre arachide").
# "the" is deliberately absent: it is the accent-free spelling of "thé" (tea).
STOPWORDS = frozenset(
    {
        "a", "au", "aux", "avec", "d", "de", "des", "du", "en", "et", "l", "la", "le", "les",
        "pour", "un", "une",
        "and", "for", "of", "with",
    }
)  # fmt: skip


def normalise_text(text: str) -> str:
    """Lower-case, accent-free, single-spaced text: ``"Crème 35 %"`` -> ``"creme 35"``."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_LIGATURES))
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _NON_ALPHANUMERIC.sub(" ", without_accents.lower()).strip()


def significant_tokens(text: str) -> tuple[str, ...]:
    """Normalised words of ``text`` without stopwords (all words when only stopwords remain)."""
    tokens = normalise_text(text).split()
    significant = tuple(token for token in tokens if token not in STOPWORDS)
    return significant or tuple(tokens)
