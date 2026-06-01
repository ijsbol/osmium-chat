from collections.abc import Container, Sequence
from typing import Protocol, TypeVar


__all__: tuple[str, ...] = (
    "locate_created",
)


class Identifiable(Protocol):
    """Structural type for anything carrying an ``id`` and a ``name``.

    Used by :func:`locate_created` so it can operate on any wrapped entity
    (channels, roles, …) without importing their concrete classes.
    """

    @property
    def id(self) -> int | None: ...

    @property
    def name(self) -> str: ...


_T = TypeVar("_T", bound=Identifiable)


def locate_created(before_ids: Container[object], after: Sequence[_T], name: str) -> _T | None:
    """Pick the entity just created out of a freshly fetched list.

    Several Osmium create RPCs don't echo the new entity back, so the caller
    snapshots the ids that existed beforehand, performs the create, refetches,
    and uses this to find what appeared. Among the ids that are new we prefer a
    name match and take the highest id (the most recently created); if nothing is
    new we fall back to the newest name match across the whole list.

    :param before_ids: The set of entity ids that existed before the create.
    :param after: The entities fetched after the create.
    :param name: The name the new entity was created with.
    :returns: The created entity, or ``None`` if it could not be located.
    """
    new = [item for item in after if item.id not in before_ids]
    candidates = new or after
    matches = [item for item in candidates if item.name == name] or candidates
    return max(matches, key=lambda item: item.id or 0) if matches else None
