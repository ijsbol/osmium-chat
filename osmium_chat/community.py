from typing import TYPE_CHECKING

from osmium_protos import (
    PB_AddStickerToPack,
    PB_ChannelType,
    PB_Community,
    PB_CreateChannel,
    PB_CreateRole,
    PB_DeleteCommunity,
    PB_EditCommunity,
    PB_GetChannels,
    PB_GetRoles,
    PB_GetStickerFiles,
    PB_GetStickerPack,
    PB_StickerPackRef,
)

from osmium_chat.category import Category
from osmium_chat.channel import Channel, ChannelType
from osmium_chat.emoji import CustomEmoji
from osmium_chat.errors import OsmiumChatError
from osmium_chat.permissions import CommunityPermission
from osmium_chat.photo import Photo
from osmium_chat.role import Role
from osmium_chat.utils import locate_created

if TYPE_CHECKING:
    from osmium_chat.client import Client


def _build_channels(
    pb_channels: list, client: "Client"
) -> "tuple[list[Channel], list[Category]]":
    """Build the channel and category lists from raw protobuf payloads.

    Returns a flat list of all non-category :class:`~osmium_chat.channel.Channel`
    objects and a separate list of :class:`~osmium_chat.category.Category` objects.
    Each channel that belongs to a category has its
    :attr:`~osmium_chat.channel.Channel.category` back-reference set.
    """
    category_ids: set[int] = {
        c.id for c in pb_channels if int(c.type) == ChannelType.CATEGORY
    }

    channel_map: dict[int, Channel] = {
        c.id: Channel.from_pb(c, client)
        for c in pb_channels
        if c.id not in category_ids
    }

    categories: list[Category] = []
    for c in pb_channels:
        if c.id not in category_ids:
            continue
        child_channels = [
            channel_map[ch.id]
            for ch in pb_channels
            if ch.parent_id == c.id and ch.id in channel_map
        ]
        category = Category.from_pb(c, client, channels=child_channels)
        for ch in child_channels:
            ch.category = category
        categories.append(category)

    return list(channel_map.values()), categories


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
        "categories",
        "roles",
        "custom_emojis",
        "_client",
    )

    def __init__(
        self,
        community: PB_Community,
        client: "Client",
        *,
        channels: list[Channel] | None = None,
        categories: list[Category] | None = None,
        roles: list[Role] | None = None,
    ) -> None:
        """Build a community from a protobuf payload.

        :param community: The raw ``PB_Community`` to read fields from.
        :param client: The client used to edit the community and manage channels,
            roles, and custom emojis.
        :param channels: The community's non-category channels, if already known.
        :param categories: The community's categories, if already known.
        :param roles: The community's roles, if already known.
        """
        self.id: int = community.id
        self.name: str = community.name
        self.username: str | None = community.username
        self.owner: bool = community.owner
        self.permissions: CommunityPermission = CommunityPermission(community.permissions)
        self.photo: Photo | None = Photo(community.photo) if community.photo else None
        self.channels: list[Channel] = channels if channels is not None else []
        self.categories: list[Category] = categories if categories is not None else []
        for ch in self.channels:
            ch.community = self
        self.roles: list[Role] = roles if roles is not None else []
        self.custom_emojis: list[CustomEmoji] = []
        self._client = client

    @classmethod
    def from_id(cls, community_id: int, client: "Client") -> "Community":
        """Build a minimal community stub from a bare id.

        Only :attr:`id` is meaningful; all other descriptive fields are their
        zero/default values until you call :meth:`fetch_channels`,
        :meth:`fetch_roles`, or similar methods that hit the gateway.

        :param community_id: The community's snowflake id.
        :param client: The client used for subsequent operations.
        """
        return cls(PB_Community(id=community_id), client)

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
        built_channels, built_categories = (
            _build_channels(channels, client) if channels else (None, None)
        )
        return cls(
            community,
            client,
            channels=built_channels,
            categories=built_categories,
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
        before = {c.id for c in (await self.fetch_channels())}
        await self._client.request(PB_CreateChannel(
            community_id=self.id,
            name=name,
            type=PB_ChannelType(type.value),
            parent_id=parent_id,
        ))
        await self.fetch_channels()
        created = locate_created(before, self.channels, name)
        if created is None:
            raise OsmiumChatError(f"Created channel {name!r} could not be located")
        return created

    async def create_category(self, name: str) -> Category:
        """Create a new category channel in this community and return it.

        Snapshots existing channel ids, creates the category, refetches, and
        returns the newly appeared :class:`~osmium_chat.category.Category` with
        an empty :attr:`~osmium_chat.category.Category.channels` list (child
        channels can be assigned by creating channels with the category's id as
        ``parent_id``). :attr:`channels` is refreshed as a side effect.

        :param name: The name of the new category.
        :returns: The newly created category.
        :raises RequestError: If the gateway rejects the request.
        :raises OsmiumChatError: If the category was created but cannot be located
            in the refetched channel list.
        """
        await self.fetch_channels()
        before = {c.id for c in self.categories}
        await self._client.request(PB_CreateChannel(
            community_id=self.id,
            name=name,
            type=PB_ChannelType(ChannelType.CATEGORY.value),
        ))
        await self.fetch_channels()
        created = locate_created(before, self.categories, name)
        if created is None:
            raise OsmiumChatError(f"Created category {name!r} could not be located")
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
        pb = result.channels
        if pb is not None:
            self.channels, self.categories = _build_channels(pb.channels, self._client)
        else:
            self.channels, self.categories = [], []
        for ch in self.channels:
            ch.community = self
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

    async def fetch_custom_emojis(self) -> list[CustomEmoji]:
        """Fetch this community's custom emojis from the gateway.

        Requests the community's emoji sticker pack, then fetches full file
        metadata via a second request to resolve emoji names. The result is
        cached on :attr:`custom_emojis`, replacing whatever was there before.

        :returns: The community's custom emojis.
        :raises RequestError: If the gateway rejects either request.
        """
        result = await self._client.request(
            PB_GetStickerPack(pack=PB_StickerPackRef(id=self.id))
        )
        pack = result.sticker_pack
        if pack is None:
            self.custom_emojis = []
            return []

        sticker_ids = [s.file_id for s in pack.stickers]
        if not sticker_ids:
            self.custom_emojis = []
            return []

        # GetStickerPack returns stub File objects (file_id only). Fetch the
        # full file records so we have filename / metadata.custom_emoji.emoji.
        files_result = await self._client.request(
            PB_GetStickerFiles(sticker_ids=sticker_ids)
        )
        full_files = files_result.files
        files_by_id = (
            {f.file_id: f for f in full_files.files}
            if full_files is not None else {}
        )

        self.custom_emojis = []
        for sticker in pack.stickers:
            full = files_by_id.get(sticker.file_id, sticker)
            if full.metadata and full.metadata.custom_emoji:
                name = full.metadata.custom_emoji.emoji or full.filename or str(full.file_id)
            else:
                name = full.filename or str(full.file_id)
            self.custom_emojis.append(CustomEmoji(
                emoji_id=full.file_id,
                name=name,
                community_id=self.id,
                pack_id=pack.id,
                client=self._client,
            ))
        return self.custom_emojis

    async def create_custom_emoji(
        self,
        image: bytes,
        name: str,
        *,
        mimetype: str = "image/png",
    ) -> CustomEmoji:
        """Upload an image and add it as a custom emoji for this community.

        Snapshots the existing emoji ids, uploads ``image``, adds it to the
        community's emoji sticker pack, re-fetches, and returns the newly
        created :class:`~osmium_chat.emoji.CustomEmoji` with its
        server-assigned id.

        :param image: Raw image bytes (PNG or WebP recommended).
        :param name: Short name for the emoji, used as ``:<name>:`` in messages.
        :param mimetype: MIME type of the image; defaults to ``"image/png"``.
        :returns: The newly created custom emoji.
        :raises RequestError: If the gateway rejects the upload or pack add.
        :raises OsmiumChatError: If the emoji was created but cannot be located
            in the re-fetched emoji list.
        """
        before = {e.id for e in await self.fetch_custom_emojis()}
        sticker = await self._client.upload_emoji_image(image, name, mimetype, self.id)
        await self._client.request(PB_AddStickerToPack(
            pack=PB_StickerPackRef(id=self.id),
            sticker=sticker,
        ))
        await self.fetch_custom_emojis()
        created = next((e for e in self.custom_emojis if e.id not in before), None)
        if created is None:
            raise OsmiumChatError(f"Created emoji {name!r} could not be located")
        return created
