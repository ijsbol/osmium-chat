from typing import TYPE_CHECKING

from osmium_protos import PB_CommunityRole, PB_DeleteRole, PB_EditRole

from osmium_chat.permissions import CommunityPermission

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "Role",
)


class Role:
    """A role within a community, parsed from its protobuf representation.

    Roles bundle a set of :class:`~osmium_chat.permissions.CommunityPermission`
    grants, a display :attr:`color`, and a :attr:`priority` that orders them. The
    :meth:`edit` and :meth:`delete` helpers let you manage a role in place.
    """

    __slots__: tuple[str, ...] = (
        "id",
        "community_id",
        "name",
        "permissions",
        "priority",
        "color",
        "separated",
        "public",
        "_client",
    )

    def __init__(self, role: PB_CommunityRole, client: "Client") -> None:
        """Build a role from a protobuf payload.

        :param role: The raw ``PB_CommunityRole`` to read fields from.
        :param client: The client used to edit and delete the role.
        """
        self.id: int = role.id
        self.community_id: int = role.community_id
        self.name: str = role.name
        self.permissions: CommunityPermission = CommunityPermission(role.permissions)
        self.priority: int = role.priority
        self.color: int = role.color
        self.separated: bool = role.separated
        self.public: bool = role.public
        self._client = client

    async def edit(
        self,
        *,
        name: str | None = None,
        permissions: CommunityPermission | int | None = None,
        priority: int | None = None,
        color: int | None = None,
        separated: bool | None = None,
        public: bool | None = None,
    ) -> "Role":
        """Edit this role's attributes.

        The edit endpoint replaces the whole role, so any argument left as
        ``None`` keeps the role's current value. The local attributes are updated
        to match, and the call waits for the gateway to confirm the edit.

        :param name: A new name for the role.
        :param permissions: A new permission bitfield.
        :param priority: A new priority (higher sorts above lower).
        :param color: A new display color.
        :param separated: Whether members with this role are shown separately.
        :param public: Whether the role is publicly visible.
        :returns: This role, with its local attributes updated.
        :raises RequestError: If the gateway rejects the edit.
        """
        if name is not None:
            self.name = name
        if permissions is not None:
            self.permissions = CommunityPermission(permissions)
        if priority is not None:
            self.priority = priority
        if color is not None:
            self.color = color
        if separated is not None:
            self.separated = separated
        if public is not None:
            self.public = public

        await self._client.request(PB_EditRole(
            id=self.id,
            community_id=self.community_id,
            name=self.name,
            permissions=int(self.permissions),
            priority=self.priority,
            color=self.color,
            separated=self.separated,
            public=self.public,
        ))
        return self

    async def delete(self) -> None:
        """Delete this role from its community."""
        await self._client.send_pb(PB_DeleteRole(
            id=self.id,
            community_id=self.community_id,
        ))
