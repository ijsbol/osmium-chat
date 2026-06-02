"""Community member: a user viewed through the lens of a specific community."""

from typing import TYPE_CHECKING

from osmium_protos import (
    PB_CommunityMember,
    PB_CommunityMemberRoleIds,
    PB_EditMember,
    PB_User,
)

from osmium_chat.user.user import User

if TYPE_CHECKING:
    from osmium_chat.client import Client
    from osmium_chat.community import Community
    from osmium_chat.role import Role


__all__: tuple[str, ...] = (
    "Member",
)


class Member(User):
    """A user as a member of a specific community.

    Extends :class:`~osmium_chat.user.user.User` with community-specific data:
    a :attr:`nickname`, a list of :attr:`role_ids`, and helpers to manage roles.

    .. note::

        When a :class:`~osmium_chat.member.Member` is built from an incoming
        message event the gateway does not include full member metadata, so
        :attr:`nickname` starts as ``None`` and :attr:`role_ids` starts empty.
        Call :meth:`~osmium_chat.community.Community.fetch_members` (once
        available) if you need the current roles.
    """

    __slots__: tuple[str, ...] = (
        "community",
        "nickname",
        "role_ids",
        "_client",
    )

    def __init__(
        self,
        member: PB_CommunityMember,
        user: PB_User,
        client: "Client",
        *,
        community: "Community",
    ) -> None:
        """Build a member from protobuf payloads.

        :param member: The raw ``PB_CommunityMember`` for community-specific data.
        :param user: The raw ``PB_User`` for the underlying user data.
        :param client: The client used to perform role edits.
        :param community: The community this member belongs to.
        """
        super().__init__(user, client)
        self.community: "Community" = community
        self.nickname: str | None = member.nickname or None
        self.role_ids: list[int] = list(member.role_ids)
        self._client = client

    @property
    def display_name(self) -> str:
        """Display name: the community :attr:`nickname` if set, otherwise the user's name."""
        return self.nickname or self.name

    @property
    def roles(self) -> "list[Role]":
        """The member's roles, resolved from the community's cached role list.

        Call :meth:`~osmium_chat.community.Community.fetch_roles` first if you
        need up-to-date role data.
        """
        role_id_set = set(self.role_ids)
        return [r for r in self.community.roles if r.id in role_id_set]

    async def add_role(self, role: "Role") -> None:
        """Add a role to this member.

        No-ops if the member already has the role. Updates :attr:`role_ids` on
        success.

        :param role: The role to add.
        :raises RequestError: If the gateway rejects the request.
        """
        if role.id in self.role_ids:
            return
        new_ids = self.role_ids + [role.id]
        await self._client.request(PB_EditMember(
            community_id=self.community.id,
            member_id=self.id,
            role_ids=PB_CommunityMemberRoleIds(role_ids=new_ids),
        ))
        self.role_ids = new_ids

    async def remove_role(self, role: "Role") -> None:
        """Remove a role from this member.

        No-ops if the member does not have the role. Updates :attr:`role_ids` on
        success.

        :param role: The role to remove.
        :raises RequestError: If the gateway rejects the request.
        """
        if role.id not in self.role_ids:
            return
        new_ids = [r for r in self.role_ids if r != role.id]
        await self._client.request(PB_EditMember(
            community_id=self.community.id,
            member_id=self.id,
            role_ids=PB_CommunityMemberRoleIds(role_ids=new_ids),
        ))
        self.role_ids = new_ids
