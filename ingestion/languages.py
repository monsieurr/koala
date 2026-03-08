"""
Language support for EU legal documents.

Covers EN, DE, FR, IT, ES.

IMPORTANT — Regulation 2024/1689 (EU AI Act) uses the PLURAL form of the adoption
phrase because it was jointly adopted by Parliament AND Council:
  EN: "HAVE ADOPTED THIS REGULATION"   (not "HAS ADOPTED")
  DE: "HABEN FOLGENDE VERORDNUNG ERLASSEN"
  FR: "ONT ADOPTÉ LE PRÉSENT RÈGLEMENT"
  IT: "HANNO ADOTTATO IL PRESENTE REGOLAMENTO"
  ES: "HAN ADOPTADO EL PRESENTE REGLAMENTO"

Both plural and singular forms are included so the detector works for older
single-institution regulations too.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from ingestion.models import Language


@dataclass
class LanguageConfig:
    code: Language
    name: str
    # All known adoption marker variants for this language (plural first)
    adoption_markers: list[str] = field(default_factory=list)
    article_keywords: list[str] = field(default_factory=list)
    recital_keywords: list[str] = field(default_factory=list)
    annex_keywords: list[str] = field(default_factory=list)
    chapter_keywords: list[str] = field(default_factory=list)

    @property
    def adoption_marker(self) -> str:
        """Primary marker (first in list) for backward compatibility."""
        return self.adoption_markers[0] if self.adoption_markers else ""


LANGUAGE_CONFIGS: dict[Language, LanguageConfig] = {
    "en": LanguageConfig(
        code="en",
        name="English",
        adoption_markers=[
            "HAVE ADOPTED THIS REGULATION",
            "HAS ADOPTED THIS REGULATION",
            "HAVE ADOPTED THIS DIRECTIVE",
            "HAS ADOPTED THIS DIRECTIVE",
        ],
        article_keywords=["Article"],
        recital_keywords=["Whereas", "Recital"],
        annex_keywords=["ANNEX", "Annex"],
        chapter_keywords=["CHAPTER", "Chapter", "TITLE", "Title", "SECTION", "Section"],
    ),
    "de": LanguageConfig(
        code="de",
        name="Deutsch",
        adoption_markers=[
            "HABEN FOLGENDE VERORDNUNG ERLASSEN",
            "HAT FOLGENDE VERORDNUNG ERLASSEN",
            "HABEN FOLGENDE RICHTLINIE ERLASSEN",
        ],
        article_keywords=["Artikel"],
        recital_keywords=["Erwägungsgrund"],
        annex_keywords=["ANHANG", "Anhang"],
        chapter_keywords=["KAPITEL", "Kapitel", "TITEL", "Titel", "ABSCHNITT", "Abschnitt"],
    ),
    "fr": LanguageConfig(
        code="fr",
        name="Français",
        adoption_markers=[
            "ONT ADOPTÉ LE PRÉSENT RÈGLEMENT",
            "A ADOPTÉ LE PRÉSENT RÈGLEMENT",
            "ONT ADOPTÉ LA PRÉSENTE DIRECTIVE",
            "A ADOPTÉ LA PRÉSENTE DIRECTIVE",
        ],
        article_keywords=["Article"],
        recital_keywords=["considérant"],
        annex_keywords=["ANNEXE", "Annexe"],
        chapter_keywords=["CHAPITRE", "Chapitre", "TITRE", "Titre", "SECTION", "Section"],
    ),
    "it": LanguageConfig(
        code="it",
        name="Italiano",
        adoption_markers=[
            "HANNO ADOTTATO IL PRESENTE REGOLAMENTO",
            "HA ADOTTATO IL PRESENTE REGOLAMENTO",
            "HANNO ADOTTATO LA PRESENTE DIRETTIVA",
        ],
        article_keywords=["Articolo"],
        recital_keywords=["considerando"],
        annex_keywords=["ALLEGATO", "Allegato"],
        chapter_keywords=["CAPO", "Capo", "TITOLO", "Titolo", "SEZIONE", "Sezione"],
    ),
    "es": LanguageConfig(
        code="es",
        name="Español",
        adoption_markers=[
            "HAN ADOPTADO EL PRESENTE REGLAMENTO",
            "HA ADOPTADO EL PRESENTE REGLAMENTO",
            "HAN ADOPTADO LA PRESENTE DIRECTIVA",
        ],
        article_keywords=["Artículo"],
        recital_keywords=["considerando"],
        annex_keywords=["ANEXO", "Anexo"],
        chapter_keywords=["CAPÍTULO", "Capítulo", "TÍTULO", "Título", "SECCIÓN", "Sección"],
    ),
}


def _normalise(text: str) -> str:
    """
    Collapse all whitespace runs (including newlines) to single spaces.
    Handles PDFs where PyMuPDF inserts line breaks inside multi-word phrases.
    """
    return re.sub(r'\s+', ' ', text)


def detect_language(text: str) -> Optional[Language]:
    """
    Detect document language by scanning for adoption marker phrases.

    Bug fixes vs V1:
    1. Searches FULL text — no character limit. The AI Act has 180 recitals;
       the adoption phrase appears at ~90,000–120,000 chars, beyond the old
       50,000-char window.
    2. Normalises whitespace before matching to handle PyMuPDF line-break
       artifacts inside the phrase.
    3. Tries both plural and singular forms — the AI Act (2024/1689) uses
       the plural "HAVE ADOPTED" not "HAS ADOPTED".
    """
    normalised = _normalise(text).upper()

    for lang, config in LANGUAGE_CONFIGS.items():
        for marker in config.adoption_markers:
            if marker.upper() in normalised:
                return lang

    return None


def get_config(language: Language) -> LanguageConfig:
    if language not in LANGUAGE_CONFIGS:
        raise ValueError(
            f"Unsupported language: '{language}'. "
            f"Supported: {list(LANGUAGE_CONFIGS.keys())}"
        )
    return LANGUAGE_CONFIGS[language]
