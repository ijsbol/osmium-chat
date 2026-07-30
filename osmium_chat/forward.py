"""Forwarding metadata for messages."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ForwardInfo:
    """Timestamp of the original message represented by a forwarded message."""

    date: int | None
