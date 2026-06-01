from typing import TYPE_CHECKING

from osmium_protos import (
    PB_Community,
    PB_CreateChannel,
    PB_CreateRole,
    PB_DeleteCommunity,
    PB_EditCommunity,
    PB_GetChannels,
    PB_GetRoles,
)

from osmium_chat.channel import Channel, ChannelType
from osmium_chat.errors import OsmiumChatError
from osmium_chat.permissions import CommunityPermission
from osmium_chat.photo import Photo
from osmium_chat.role import Role
from osmium_chat.utils import locate_created

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "Community",
)


class Community:
    """An Osmium community (a server), parsed from its protobuf representation.

    A community owns a list of :attr:`channels` and :attr:`roles`. Those lists
    are populated when the community is built from data that includes them (see
    :meth:`from_pb`); since the gateway delivers channels and roles as separate
    updates, :meth:`fetch_channels` and :meth:`fetch_roles` ask the server to
    (re)send them. Use :meth:`edit`, :meth:`create_channel`, and
    :meth:`create_role` to manage the community.
    """

    __slots__: tuple[str, ...] = (
        "id",
        "name",
        "username",
        "owner",
        "permissions",
        "photo",
        "channels",
        "roles",
        "_client",
    )

    def __init__(
        self,
        community: PB_Community,
        client: "Client",
        *,
        channels: list[Channel] | None = None,
        roles: list[Role] | None = None,
    ) -> None:
        """Build a community from a protobuf payload.

        :param community: The raw ``PB_Community`` to read fields from.
        :param client: The client used to edit the community and manage channels
            and roles.
        :param channels: The community's channels, if already known.
        :param roles: The community's roles, if already known.
        """
        self.id: int = community.id
        self.name: str = community.name
        self.username: str | None = community.username
        self.owner: bool = community.owner
        self.permissions: CommunityPermission = CommunityPermission(community.permissions)
        self.photo: Photo | None = Photo(community.photo) if community.photo else None
        self.channels: list[Channel] = channels if channels is not None else []
        self.roles: list[Role] = roles if roles is not None else []
        self._client = client

    @classmethod
    def from_pb(
        cls,
        community: PB_Community,
        client: "Client",
        *,
        channels: "list | None" = None,
        roles: "list | None" = None,
    ) -> "Community":
        """Build a community, wrapping any raw channel/role protobufs supplied.

        :param community: The raw ``PB_Community`` describing the community.
        :param client: The client used for subsequent operations.
        :param channels: Raw ``PB_Channel`` objects to wrap as :class:`~osmium_chat.channel.Channel`.
        :param roles: Raw ``PB_CommunityRole`` objects to wrap as :class:`~osmium_chat.role.Role`.
        """
        return cls(
            community,
            client,
            channels=[Channel.from_pb(c, client) for c in channels] if channels else None,
            roles=[Role(r, client) for r in roles] if roles else None,
        )

    async def edit(
        self,
        *,
        name: str | None = None,
        username: str | None = None,
    ) -> "Community":
        """Edit this community's attributes.

        Only the arguments you pass are changed; anything left as ``None`` is
        kept as-is. The local attributes are updated to match.

        :param name: A new display name for the community.
        :param username: A new public username (handle) for the community.
        :returns: This community, with its local attributes updated.
        :raises RequestError: If the gateway rejects the edit.
        """
        if name is not None:
            self.name = name
        if username is not None:
            self.username = username
        await self._client.request(PB_EditCommunity(
            community_id=self.id,
            name=name,
            username=username,
        ))
        return self

    async def delete(self) -> None:
        """Delete this community."""
        await self._client.send_pb(PB_DeleteCommunity(community_id=self.id))

    async def create_channel(
        self,
        name: str,
        *,
        type: ChannelType = ChannelType.TEXT,
        parent_id: int | None = None,
    ) -> Channel:
        """Create a new channel in this community and return it.

        The gateway's create RPC doesn't echo the new channel, so this snapshots
        the existing channel ids, creates the channel, refetches, and returns the
        newly appeared one (with its server-assigned id). :attr:`channels` is
        refreshed as a side effect.

        :param name: The name of the new channel.
        :param type: The :class:`~osmium_chat.channel.ChannelType` to create.
        :param parent_id: The id of the category channel to nest it under, if any.
        :returns: The newly created channel.
        :raises RequestError: If the gateway rejects the request.
        :raises OsmiumChatError: If the channel was created but cannot be located
            in the refetched channel list.
        """
        before = {channel.id for channel in await self.fetch_channels()}
        await self._client.request(PB_CreateChannel(
            community_id=self.id,
            name=name,
            type=type.value,
            parent_id=parent_id,
        ))
        created = locate_created(before, await self.fetch_channels(), name)
        if created is None:
            raise OsmiumChatError(f"Created channel {name!r} could not be located")
        return created

    async def create_role(
        self,
        name: str,
        *,
        permissions: CommunityPermission | int = CommunityPermission.NO_PERMISSION,
        priority: int = 0,
        color: int = 0,
        separated: bool = False,
        public: bool = False,
    ) -> Role:
        """Create a new role in this community and return it.

        The gateway's create RPC doesn't echo the new role, so this snapshots the
        existing role ids, creates the role, refetches, and returns the newly
        appeared one (with its server-assigned id). :attr:`roles` is refreshed as
        a side effect.

        :param name: The name of the new role.
        :param permissions: The permission bitfield to grant.
        :param priority: The role priority (higher sorts above lower).
        :param color: The role's display color.
        :param separated: Whether members with this role are shown separately.
        :param public: Whether the role is publicly visible.
        :returns: The newly created role.
        :raises RequestError: If the gateway rejects the request.
        :raises OsmiumChatError: If the role was created but cannot be located in
            the refetched role list.
        """
        before = {role.id for role in await self.fetch_roles()}
        await self._client.request(PB_CreateRole(
            community_id=self.id,
            name=name,
            permissions=int(permissions),
            priority=priority,
            color=color,
            separated=separated,
            public=public,
        ))
        created = locate_created(before, await self.fetch_roles(), name)
        if created is None:
            raise OsmiumChatError(f"Created role {name!r} could not be located")
        return created

    async def fetch_channels(self) -> list[Channel]:
        """Fetch this community's channels from the gateway.

        The result is also cached on :attr:`channels`, replacing whatever was
        there before.

        :returns: The community's channels.
        """
        result = await self._client.request(PB_GetChannels(community_id=self.id))
        channels = result.channels
        self.channels = (
            [Channel.from_pb(c, self._client) for c in channels.channels]
            if channels is not None else []
        )
        return self.channels

    async def fetch_roles(self) -> list[Role]:
        """Fetch this community's roles from the gateway.

        The result is also cached on :attr:`roles`, replacing whatever was there
        before.

        :returns: The community's roles.
        """
        result = await self._client.request(PB_GetRoles(community_id=self.id))
        roles = result.community_roles
        self.roles = (
            [Role(r, self._client) for r in roles.roles]
            if roles is not None else []
        )
        return self.roles
