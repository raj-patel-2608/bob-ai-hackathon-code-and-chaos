"""Accused-name extraction and normalisation (rules).

Handles the header "Accused:" line, "X alias Y" / "X urf Y" / "Y (X)" forms,
and a few generic narrative phrasings ("identified as X", "his name is X").
Anything else (names buried in free text) is left to the LLM enrichment stage.

A name identity is either the full name ("salim sheikh") or the alias
("pappu"); a mention that carries both connects them. Generic values such as
"Unknown" or "two unknown persons" are never identities.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

UNKNOWN_RE = re.compile(r"\b(unknown|not\s+known|unidentified|n/?a|nil|none|to be traced|unknown persons?|"
                        r"two unknown|three unknown)\b", re.I)
ALIAS_RE = re.compile(r"(?P<name>[A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){0,3})\s+(?:alias|urf|@)\s+"
                      r"(?P<alias>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)")
PAREN_ALIAS_RE = re.compile(r"(?P<alias>[A-Z][a-z]{2,})\s+\((?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\)")
# someone actually identified (by witness / CCTV / police) -> accused identity
IDENTIFIED_RE = re.compile(r"(?:identified as|was called)\s+"
                           r"(?P<name>[A-Z][a-z]+(?:\s+(?:[A-Z]\.|[A-Z][a-z]+)){0,3})(?![A-Za-z])")
# a name the offender *claimed* (fake caller persona) -> weak signature only, never proof of identity
CLAIMED_RE = re.compile(
    r"(?:his name is|her name is|a person named|who (?:called|introduced) himself as|claiming to be|"
    r"said (?:he|she) is)\s+"
    r"(?P<name>(?:(?:Inspector|Sub-Inspector|ASI|DCP|Dr\.|Captain|Major|Subedar|Havildar|Naik)\s+)?"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})")
HONORIFIC_RE = re.compile(r"^(?:mr|mrs|ms|shri|smt|dr|inspector|sub-inspector|asi|dcp|captain|major|subedar|"
                          r"havildar|naik)\.?\s+", re.I)
BHAI_SUFFIX_RE = re.compile(r"(bhai|ben|bhau)$", re.I)
NOT_NAMES = {"The", "He", "She", "They", "Police", "Bank", "Customer", "Crime", "Branch", "Delhi", "Mumbai"}


@dataclass(frozen=True)
class AccusedMention:
    as_written: str
    name: str | None      # normalised full name, lower case ("salim sheikh")
    alias: str | None     # normalised alias ("pappu")
    source: str           # header | narrative | claimed (fake persona used by the offender)


def normalize_person(value: str) -> str | None:
    value = re.sub(r"\s+", " ", value.replace(".", " ")).strip()
    value = HONORIFIC_RE.sub("", value)
    tokens = [BHAI_SUFFIX_RE.sub("", t) if len(t) > 6 else t for t in value.split()]
    tokens = [t for t in tokens if t]     # initials are kept: "Dhruv S. Sheikh" and "Dhruv C. Sheikh" differ
    if not tokens:
        return None
    return " ".join(t.lower() for t in tokens)


def _mention(text: str, source: str) -> AccusedMention | None:
    text = text.strip(" .,;:")
    if not text or UNKNOWN_RE.search(text):
        return None
    m = ALIAS_RE.search(text)
    if m:
        name = normalize_person(m.group("name"))
        # a single first name before "alias" is too weak to be an identity on its own
        return AccusedMention(text, name if name and " " in name else None,
                              normalize_person(m.group("alias")), source)
    m = PAREN_ALIAS_RE.search(text)
    if m:
        return AccusedMention(text, normalize_person(m.group("name")), normalize_person(m.group("alias")), source)
    words = text.split()
    if len(words) == 1 and words[0][:1].isupper() and words[0] not in NOT_NAMES:
        return AccusedMention(text, None, normalize_person(words[0]), source)       # bare alias, e.g. "Pappu"
    if 2 <= len(words) <= 4 and all(w[:1].isupper() for w in words):
        return AccusedMention(text, normalize_person(text), None, source)
    return None


def extract_accused(header_value: str | None, narrative: str) -> list[AccusedMention]:
    mentions: list[AccusedMention] = []
    if header_value:
        m = _mention(header_value, "header")
        if m:
            mentions.append(m)
    for m in ALIAS_RE.finditer(narrative):
        mention = _mention(m.group(0), "narrative")
        if mention:
            mentions.append(mention)
    for m in PAREN_ALIAS_RE.finditer(narrative):
        mention = _mention(m.group(0), "narrative")
        if mention:
            mentions.append(mention)
    for m in IDENTIFIED_RE.finditer(narrative):
        if m.group("name").split()[0] not in NOT_NAMES:
            mention = _mention(m.group("name"), "narrative")
            if mention:
                mentions.append(mention)
    for m in CLAIMED_RE.finditer(narrative):
        if m.group("name").split()[0] not in NOT_NAMES:
            name = normalize_person(m.group("name"))
            if name:
                mentions.append(AccusedMention(m.group("name"), name, None, "claimed"))
    # de-duplicate on (name, alias)
    seen, unique = set(), []
    for m in mentions:
        key = (m.name, m.alias)
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique
