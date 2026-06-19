from __future__ import annotations

import re
from pathlib import Path

ROLE_KICK = "kick"
ROLE_SNARE = "snare"
ROLE_HAT_CLOSED = "hat_closed"
ROLE_HAT_OPEN = "hat_open"
ROLE_CLAP = "clap"
ROLE_RIM = "rim"
ROLE_TOM = "tom"
ROLE_PERC = "perc"
ROLE_FX = "fx"
ROLE_OTHER = "other"

_KICK_ALIASES = {"kick", "kicks", "kickz", "kik", "kikz", "kiik"}
_SNARE_ALIASES = {"snare", "snares", "snarez", "snz"}
_PERC_ALIASES = {"perc", "percs", "percz", "percussion", "percussions", "percussionz"}
_CLAP_ALIASES = {"clap", "claps", "clapz"}
_HAT_ALIASES = {"hat", "hats", "hihat", "hihats", "hh"}
_HAT_OPEN_ALIASES = {"openhat", "openhats", "openhh", "hihatop", "hatop", "ohh"}
_HAT_CLOSED_ALIASES = {"closedhat", "closedhats", "closedhh", "hihatcl", "hatcl", "chh"}
_TOM_ALIASES = {"tom", "toms"}
_RIM_ALIASES = {"rim", "rimshot"}
_FX_ALIASES = {"fx", "sfx", "impact", "sweep", "rise", "riser", "crash"}


def classify_sample(path: Path, source_rel: str | None = None) -> str:
    name = path.stem.lower()
    role = _classify_from_name(name)
    if role != ROLE_OTHER:
        return role

    if source_rel:
        fallback_role = infer_role_from_source_path(source_rel)
        if fallback_role is not None:
            return fallback_role

    return ROLE_OTHER


def infer_role_from_source_path(source_rel: str) -> str | None:
    parts = Path(source_rel).parts[:-1]
    if not parts:
        return None

    tokens: set[str] = set()
    compact_tokens: set[str] = set()
    for part in parts:
        lowered = part.lower()
        tokens.update(_tokenize(lowered))
        compact = re.sub(r"[^a-z0-9]+", "", lowered)
        if compact:
            compact_tokens.add(compact)

    if compact_tokens.intersection(_HAT_OPEN_ALIASES):
        return ROLE_HAT_OPEN
    if compact_tokens.intersection(_HAT_CLOSED_ALIASES):
        return ROLE_HAT_CLOSED
    if tokens.intersection(_KICK_ALIASES):
        return ROLE_KICK
    if tokens.intersection(_SNARE_ALIASES):
        return ROLE_SNARE
    if tokens.intersection(_PERC_ALIASES):
        return ROLE_PERC
    if tokens.intersection(_CLAP_ALIASES):
        return ROLE_CLAP
    if tokens.intersection(_RIM_ALIASES):
        return ROLE_RIM
    if tokens.intersection(_TOM_ALIASES):
        return ROLE_TOM
    if tokens.intersection(_FX_ALIASES):
        return ROLE_FX
    if tokens.intersection(_HAT_ALIASES):
        return ROLE_HAT_CLOSED

    return None


def _classify_from_name(name: str) -> str:
    # First-pass filename heuristics keep existing behavior stable.
    if "kick" in name:
        return ROLE_KICK
    if "snare" in name:
        return ROLE_SNARE

    if any(token in name for token in ("closedhh", "hat cl", "hatcl", "closed hat", "hihat cl", "hh cl")):
        return ROLE_HAT_CLOSED
    if any(token in name for token in ("openhh", "hat op", "hatop", "open hat", "hihat op", "hh op")):
        return ROLE_HAT_OPEN

    if "clap" in name:
        return ROLE_CLAP
    if "rim" in name or "rimshot" in name:
        return ROLE_RIM
    if "tom" in name:
        return ROLE_TOM

    if any(token in name for token in ("fx", "sfx", "impact", "sweep", "rise", "crash")):
        return ROLE_FX

    if any(token in name for token in ("perc", "shaker", "conga", "bongo", "cowbell", "cabasa", "tamb", "clave")):
        return ROLE_PERC

    return ROLE_OTHER


def _tokenize(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value) if token]
