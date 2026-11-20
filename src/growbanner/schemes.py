"""Location -> banner/text colors, with tolerant matching."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Scheme:
    name: str
    banner: str  # hex, e.g. "#8DC63F"
    text: str  # hex


@dataclass(frozen=True)
class LocationRule:
    name: str  # text shown in the dropdown and printed on the banner
    keywords: tuple[str, ...]  # empty -> the name itself is the keyword
    banner: str
    text: str


OTHER = Scheme("Other", "#981B1E", "#FFFFFF")

DEFAULT_RULES: tuple[LocationRule, ...] = (
    LocationRule("Braddock", ("braddock",), "#8DC63F", "#000000"),
    LocationRule("Shiloh", ("shiloh",), "#FFC20E", "#000000"),
    LocationRule("Garden Dreams", ("garden dreams",), "#F7941D", "#000000"),
    LocationRule("Garden Resource Center", ("grc", "garden resource center"), "#003510", "#FFFFFF"),
    LocationRule("Virtual", (), OTHER.banner, OTHER.text),
    LocationRule("Community Forge", (), OTHER.banner, OTHER.text),
    LocationRule("GP Office", (), OTHER.banner, OTHER.text),
)


def new_rule(name: str, other: Scheme = OTHER) -> LocationRule:
    """A newly added location starts with the default (maroon) colors."""
    return LocationRule(name.strip(), (), other.banner, other.text)


def find_rule(location: str, rules=DEFAULT_RULES) -> LocationRule | None:
    text = f" {_norm(location)} "
    for rule in rules:
        for kw in rule.keywords or (rule.name,):
            if _norm(kw) and f" {_norm(kw)} " in text:
                return rule
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def match_scheme(location: str, rules=DEFAULT_RULES, other: Scheme = OTHER) -> Scheme:
    """Case-insensitive, whole-word keyword match; anything unmatched is maroon."""
    rule = find_rule(location, rules)
    return Scheme(rule.name, rule.banner, rule.text) if rule else other
