from __future__ import annotations

from functools import lru_cache

from omdc.encoders.base import Encoder, EncoderPin


@lru_cache(maxsize=8)
def _by_name(name: str) -> Encoder:
    if name == "hist":
        from omdc.encoders.histogram import HistogramEncoder

        return HistogramEncoder()
    if name == "mace":
        from omdc.encoders.mace import MaceEncoder

        return MaceEncoder()
    raise KeyError(f"unknown encoder {name!r}; known: 'mace', 'hist'")


def get_encoder(name: str | Encoder) -> Encoder:
    if isinstance(name, Encoder):
        return name
    return _by_name(name)


__all__ = ["Encoder", "EncoderPin", "get_encoder"]
