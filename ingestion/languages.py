"""Language configuration and lightweight language detection for EU acts."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True, slots=True)
class LanguageConfig:
    code: str
    name: str
    adoption_markers: tuple[str, ...]
    recital_start_markers: tuple[str, ...]
    article_word: str
    chapter_word: str
    annex_word: str


LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "en": LanguageConfig(
        code="en",
        name="English",
        adoption_markers=("HAS ADOPTED THIS REGULATION:", "HAVE ADOPTED THIS REGULATION:"),
        recital_start_markers=("WHEREAS:",),
        article_word="Article",
        chapter_word="CHAPTER",
        annex_word="ANNEX",
    ),
    "de": LanguageConfig(
        code="de",
        name="Deutsch",
        adoption_markers=("HABEN FOLGENDE VERORDNUNG ERLASSEN:",),
        recital_start_markers=("IN ERWAGUNG NACHSTEHENDER GRUNDE:",),
        article_word="Artikel",
        chapter_word="KAPITEL",
        annex_word="ANHANG",
    ),
    "fr": LanguageConfig(
        code="fr",
        name="Francais",
        adoption_markers=("ONT ADOPTE LE PRESENT REGLEMENT:", "ONT ADOPTE LE PRESENT REGLEMENT"),
        recital_start_markers=("CONSIDERANT CE QUI SUIT:",),
        article_word="Article",
        chapter_word="CHAPITRE",
        annex_word="ANNEXE",
    ),
    "it": LanguageConfig(
        code="it",
        name="Italiano",
        adoption_markers=("HANNO ADOTTATO IL PRESENTE REGOLAMENTO:",),
        recital_start_markers=("CONSIDERANDO QUANTO SEGUE:",),
        article_word="Articolo",
        chapter_word="CAPO",
        annex_word="ALLEGATO",
    ),
    "es": LanguageConfig(
        code="es",
        name="Espanol",
        adoption_markers=("HAN ADOPTADO EL PRESENTE REGLAMENTO:",),
        recital_start_markers=("CONSIDERANDO LO SIGUIENTE:",),
        article_word="Artículo",
        chapter_word="CAPÍTULO",
        annex_word="ANEXO",
    ),
}


def normalize_for_matching(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_value.upper().split())


def get_language_config(language_code: str) -> LanguageConfig:
    code = language_code.lower()
    if code not in LANGUAGE_CONFIGS:
        supported = ", ".join(sorted(LANGUAGE_CONFIGS))
        raise ValueError(f"Unsupported language '{language_code}'. Supported: {supported}")
    return LANGUAGE_CONFIGS[code]


def detect_language(text: str) -> str:
    sample = normalize_for_matching(text)
    for code, config in LANGUAGE_CONFIGS.items():
        for marker in config.adoption_markers:
            if marker in sample:
                return code
    supported = ", ".join(sorted(LANGUAGE_CONFIGS))
    raise ValueError(
        "Could not detect document language from adoption markers. "
        f"Use --language explicitly. Supported languages: {supported}"
    )


def supported_languages() -> tuple[str, ...]:
    return tuple(sorted(LANGUAGE_CONFIGS))
