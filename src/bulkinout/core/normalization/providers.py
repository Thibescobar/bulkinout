"""Small deterministic providers and adapters for externally supplied terminology."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ...types import JsonValue
from ..models import CodedConcept, UCUM_SYSTEM

_SEPARATOR = re.compile(r"[.;,:]|\b(?:but|however|mais|cependant)\b", re.IGNORECASE)
_NON_WORD = re.compile(r"[^a-z0-9]+")
_NEGATION = re.compile(
    r"(?:^|\b)(?:"
    r"no|not|without|denies?|negative for|absence (?:of|de|d)|"
    r"aucun(?:e)?(?: signe| argument)?(?: de| d)?|sans(?: signe)?(?: de| d)?|pas (?:de|d)"
    r")(?:\b|$)"
)
_NUMBER = r"(?P<number>[+-]?\d+(?:[.,]\d+)?)"


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return _NON_WORD.sub(" ", ascii_text.casefold()).strip()


def _text_values(value: JsonValue) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def _term_pattern(term: str) -> re.Pattern[str]:
    words = _fold(term).split()
    body = r"\W+".join(map(re.escape, words))
    return re.compile(rf"(?<!\w){body}(?!\w)")


def _negated(prefix: str) -> bool:
    words = prefix.split()
    return _NEGATION.search(" ".join(words[-8:])) is not None


def _positive_terms(text: str, terms: Iterable[str]) -> set[str]:
    matches: set[str] = set()
    for clause in _SEPARATOR.split(text):
        folded = _fold(clause)
        for term in terms:
            match = _term_pattern(term).search(folded)
            if match is not None and not _negated(folded[: match.start()]):
                matches.add(_fold(term))
    return matches


@dataclass(frozen=True, slots=True)
class TerminologyEntry:
    """One caller-supplied mapping; entries are data, not a bundled terminology."""

    system: str
    code: str
    display: str
    synonyms: tuple[str, ...]
    field_paths: frozenset[str] = field(default_factory=frozenset)
    version: str | None = None


class InMemoryTerminologyProvider:
    """Conservative FR/EN matcher for licensed or locally maintained entries."""

    def __init__(
        self,
        entries: Sequence[TerminologyEntry],
        *,
        name: str = "in_memory",
        version: str = "unversioned",
    ) -> None:
        self.name = name
        self.version = version
        self._entries = tuple(entries)
        payload = [
            {
                "system": item.system,
                "code": item.code,
                "display": item.display,
                "synonyms": item.synonyms,
                "field_paths": sorted(item.field_paths),
                "version": item.version,
            }
            for item in self._entries
        ]
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.content_sha256 = hashlib.sha256(encoded).hexdigest()

    def concepts_for(self, field_path: str, value: JsonValue) -> list[CodedConcept]:
        concepts: list[CodedConcept] = []
        for original_text in _text_values(value):
            matches = [
                (entry, _positive_terms(original_text, entry.synonyms))
                for entry in self._entries
                if (not entry.field_paths or field_path in entry.field_paths)
            ]
            matched = [(entry, terms) for entry, terms in matches if terms]
            ambiguous_terms = {
                term
                for _, terms in matched
                for term in terms
                if len(
                    {
                        (candidate.system, candidate.code)
                        for candidate, candidate_terms in matched
                        if term in candidate_terms
                    }
                )
                > 1
            }
            for entry, terms in matched:
                if terms <= ambiguous_terms:
                    continue
                concepts.append(
                    CodedConcept(
                        system=entry.system,
                        code=entry.code,
                        display=entry.display,
                        original_text=original_text,
                        version=entry.version,
                    )
                )
        return concepts


@dataclass(frozen=True, slots=True)
class _Unit:
    code: str
    display: str
    aliases: tuple[str, ...]


_UNITS = (
    _Unit("umol/L", "micromole per liter", ("µmol/L", "μmol/L", "umol/L")),
    _Unit("mmol/L", "millimole per liter", ("mmol/L",)),
    _Unit("mg/dL", "milligram per deciliter", ("mg/dL",)),
    _Unit("mg/L", "milligram per liter", ("mg/L",)),
    _Unit("g/L", "gram per liter", ("g/L",)),
    _Unit("mm[Hg]", "millimeter of mercury", ("mmHg", "mm Hg")),
    _Unit("%", "percent", ("%",)),
)


class UCUMUnitProvider:
    """Recognize a limited set of common UCUM units without converting values."""

    name = "builtin_ucum_units"
    version = "1"
    content_sha256 = hashlib.sha256(
        json.dumps(
            [(unit.code, unit.display, unit.aliases) for unit in _UNITS],
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    def concepts_for(self, field_path: str, value: JsonValue) -> list[CodedConcept]:
        del field_path
        concepts: list[CodedConcept] = []
        for original_text in _text_values(value):
            matches: list[tuple[_Unit, re.Match[str]]] = []
            for unit in _UNITS:
                aliases = "|".join(re.escape(alias) for alias in unit.aliases)
                pattern = re.compile(rf"{_NUMBER}\s*(?:{aliases})(?![A-Za-z])", re.IGNORECASE)
                matches.extend((unit, match) for match in pattern.finditer(original_text))
            for unit, match in matches:
                number = float(match.group("number").replace(",", "."))
                normalized_value: int | float = int(number) if number.is_integer() else number
                concepts.append(
                    CodedConcept(
                        system=UCUM_SYSTEM,
                        code=unit.code,
                        display=unit.display,
                        original_text=match.group(0),
                        normalized_value=normalized_value,
                    )
                )
        return concepts
