"""cleaner.py: normalise raw arcanite card JSON fields (zodiac dirty-data rules), per design §1.2.

Rules (design doc §1.2):
- zodiac value in 12 signs      -> keep
- zodiac value in planet names  -> move to ruler_planet channel, clear zodiac
- "sun in scorpio" mixed text   -> parse sign out, set zodiac
- empty string                  -> leave empty (element is 78/78 present, so scoring unaffected)
"""
from __future__ import annotations

import re
from typing import Any

SIGNS: frozenset[str] = frozenset({
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
})

PLANETS: frozenset[str] = frozenset({
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
})

_SIGNED_RE = re.compile(r"^(?P<planet>[a-z]+)\s+in\s+(?P<sign>[a-z]+)$")


def clean_card(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a cleaned copy of one arcanite card JSON.

    Adds/normalises:
      elemental_correspondences.zodiac       -> only 12-sign values or ""
      elemental_correspondences.ruler_planet -> planet-channel value (from dirty zodiac or planet field)
    The input dict is NOT mutated.
    """
    out: dict[str, Any] = dict(raw)
    ecal_raw: dict[str, Any] = dict(out.get("elemental_correspondences") or {})
    ecal: dict[str, Any] = dict(ecal_raw)

    zodiac_raw: str = str(ecal.get("zodiac") or "").strip().lower()
    planet_field: str = str(ecal.get("planet") or "").strip().lower()

    ruler_planet: str = planet_field
    zodiac_clean: str = ""

    if zodiac_raw in SIGNS:
        zodiac_clean = zodiac_raw
    elif zodiac_raw in PLANETS:
        # planet-channel card (the_fool=uranus, judgement=pluto, ...)
        ruler_planet = planet_field or zodiac_raw
    else:
        m = _SIGNED_RE.match(zodiac_raw)
        if m and m.group("sign") in SIGNS:
            zodiac_clean = m.group("sign")
            # "sun in scorpio": planet info still belongs to the planet channel —
            # only accept words that are actual planets (review fix: "banana in scorpio" is noise)
            captured = m.group("planet")
            if captured in PLANETS:
                ruler_planet = ruler_planet or captured
        # anything else / empty: leave zodiac empty; element (78/78 present) covers scoring

    ecal["zodiac"] = zodiac_clean
    ecal["ruler_planet"] = ruler_planet
    out["elemental_correspondences"] = ecal
    return out
