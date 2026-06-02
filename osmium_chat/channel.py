from enum import IntEnum
from typing import TYPE_CHECKING

from osmium_chat.content import Content

from osmium_protos import (
    PB_Channel,
    PB_ChannelRef,
    PB_ChatRef,
    PB_CreateChatInvite,
    PB_DeleteChannel,
    PB_EditChannel,
    PB_ListChatInvites,
    PB_LookupInvite,
    PB_Message,
    PB_SendMessage,
)

if TYPE_CHECKING:
    from osmium_chat.category import Category
    from osmium_chat.client import Client
    from osmium_chat.invite import InvitePreview
    from osmium_chat.message import Message


__all__: tuple[str, ...] = (
    "ChannelType",
    "Channel",
)


class ChannelType(IntEnum):
    """The kind of a community channel.

    Mirrors :class:`~osmium_protos.PB_ChannelType` so callers can use a readable
    name (``ChannelType.TEXT``) instead of a raw integer when creating channels.
    """

    TEXT = 0
    VOICE = 1
    CATEGORY = 2


class Channel:
    """A conversation a message can be sent to.

    Wraps the :class:`~osmium_protos.PB_ChatRef` that identifies a destination
    (a user DM, community channel, group, or self) together with the client used
    to deliver outbound messages, so callers can simply ``await channel.send(...)``.

    When the channel was resolved from a community (see :meth:`from_pb`) the
    descriptive fields — :attr:`id`, :attr:`name`, :attr:`type`,
    :attr:`community_id`, :attr:`position`, and :attr:`parent_id` — are populated;
    for an ad-hoc DM or group ref they are ``None``. Only community channels can
    be edited or deleted, since those operations need a
    :class:`~osmium_protos.PB_ChannelRef`.
    """

    __slots__: tuple[str, ...] = (
        "_chat_ref",
        "_client",
        "id",
        "name",
        "type",
        "community_id",
        "position",
        "parent_id",
        "category",
    )

    def __init__(
        self,
        chat_ref: PB_ChatRef,
        client: "Client",
        *,
        id: int | None = None,
        name: str | None = None,
        type: ChannelType | None = None,
        community_id: int | None = None,
        position: int | None = None,
        parent_id: int | None = None,
    ) -> None:
        """Bind a channel to a destination ref and the transport client.

        :param chat_ref: The ref identifying where messages should be delivered.
        :param client: The client used to send messages.
        :param id: The channel id, for a community channel.
        :param name: The channel name, for a community channel.
        :param type: The channel :class:`ChannelType`, for a community channel.
        :param community_id: The owning community id, for a community channel.
        :param position: The channel's sort position within the community.
        :param parent_id: The id of the category channel this sits under, if any.
        """
        self._chat_ref = chat_ref
        self._client = client
        self.id = id
        self.name = name
        self.type = type
        self.community_id = community_id
        self.position = position
        self.parent_id = parent_id
        self.category: "Category | None" = None

    @classmethod
    def from_pb(cls, channel: PB_Channel, client: "Client") -> "Channel":
        """Build a channel from a community's :class:`~osmium_protos.PB_Channel`.

        Constructs the addressing ref from the channel's community and id and
        copies across the descriptive metadata, so the returned channel can be
        both sent to and edited/deleted.

        :param channel: The raw ``PB_Channel`` describing a community channel.
        :param client: The client used to deliver messages and edits.
        """
        return cls(
            PB_ChatRef(channel=PB_ChannelRef(
                community_id=channel.community_id,
                channel_id=channel.id,
            )),
            client,
            id=channel.id,
            name=channel.name,
            type=ChannelType(channel.type),
            community_id=channel.community_id,
            position=channel.position,
            parent_id=channel.parent_id,
        )

    @property
    def _channel_ref(self) -> PB_ChannelRef:
        """The community :class:`~osmium_protos.PB_ChannelRef` for this channel.

        :raises TypeError: If this channel is not a community channel and so
            cannot be referenced for edit/delete operations.
        """
        ref = self._chat_ref.channel
        if ref is None:
            raise TypeError("Only community channels can be edited or deleted")
        return ref

    async def send(self, content: "str | Content", *, reply_to: int | None = None) -> "Message":
        """Send a message to this channel and return the created message.

        Waits for the gateway to acknowledge the send so the returned
        :class:`~osmium_chat.message.Message` carries the server-assigned id,
        ready to :meth:`~osmium_chat.message.Message.edit` or
        :meth:`~osmium_chat.message.Message.delete`.

        :param content: The message text, either a plain string or a
            :class:`~osmium_chat.content.Content` object.
        :param reply_to: Optional id of a message this should reply to.
        :returns: The newly created message.
        """
        # Imported lazily to avoid a circular import (message -> user -> channel).
        from osmium_chat.message import Message

        content_obj = content if isinstance(content, Content) else Content(content)
        result = await self._client.request(PB_SendMessage(
            chat_ref=self._chat_ref,
            message=content_obj.text,
            entities=content_obj.entities,
            reply_to=reply_to,
        ))
        author = self._client.bot.user
        sent = result.sent_message
        return Message(
            PB_Message(
                chat_ref=self._chat_ref,
                message_id=sent.message_id if sent is not None else 0,
                author_id=author.id if author is not None else 0,
                message=content_obj.text,
                entities=content_obj.entities,
                reply_to=reply_to,
            ),
            self._client,
            author=author,
        )

    async def send_file(
        self,
        data: bytes,
        filename: str,
        *,
        mimetype: str = "application/octet-stream",
        reply_to: int | None = None,
    ) -> "Message":
        """Upload ``data`` and send it as a file attachment to this channel.

        :param data: The raw file bytes to upload and attach.
        :param filename: The file name shown to recipients.
        :param mimetype: The MIME type of the file; defaults to
            ``application/octet-stream``.
        :param reply_to: Optional id of a message this should reply to.
        :returns: The newly created message carrying the file attachment.
        :raises RequestError: If the gateway rejects the upload or send.
        """
        from osmium_chat.message import Message

        _, media_ref = await self._client.upload_file(data, filename, mimetype)
        result = await self._client.request(PB_SendMessage(
            chat_ref=self._chat_ref,
            media=[media_ref],
            reply_to=reply_to,
        ))
        author = self._client.bot.user
        sent = result.sent_message
        return Message(
            PB_Message(
                chat_ref=self._chat_ref,
                message_id=sent.message_id if sent is not None else 0,
                author_id=author.id if author is not None else 0,
                media=[],
            ),
            self._client,
            author=author,
        )

    async def edit(
        self,
        *,
        name: str | None = None,
        position: int | None = None,
        parent_id: int | None = None,
        explicit: bool | None = None,
    ) -> "Channel":
        """Edit this community channel's attributes.

        Only the arguments you pass are changed; anything left as ``None`` is
        kept as-is by the server. Waits for the gateway to confirm the edit and
        updates the local metadata to match.

        :param name: A new name for the channel.
        :param position: A new sort position within the community.
        :param parent_id: A new parent category id (or ``None`` to leave it).
        :param explicit: Whether the channel is flagged as explicit.
        :returns: This channel, with its local metadata updated.
        :raises TypeError: If this channel is not a community channel.
        :raises RequestError: If the gateway rejects the edit.
        """
        ref = self._channel_ref
        await self._client.request(PB_EditChannel(
            channel=ref,
            name=name,
            position=position,
            parent_id=parent_id,
            explicit=explicit,
        ))
        if name is not None:
            self.name = name
        if position is not None:
            self.position = position
        if parent_id is not None:
            self.parent_id = parent_id
        return self

    async def delete(self) -> None:
        """Delete this community channel.

        :raises TypeError: If this channel is not a community channel.
        """
        await self._client.send_pb(PB_DeleteChannel(channel=self._channel_ref))

    async def create_invite(
        self,
        *,
        expires_at: int | None = None,
        max_uses: int | None = None,
    ) -> "InvitePreview":
        """Create an invite link for this channel and return the full preview.

        Creates the invite then immediately fetches its metadata so the returned
        :class:`~osmium_chat.invite.InvitePreview` carries creator and target info.

        :param expires_at: Optional Unix timestamp (seconds) at which the invite expires.
        :param max_uses: Optional maximum number of times the invite can be used.
        :returns: The newly created invite with full metadata.
        :raises RequestError: If the gateway rejects the request.
        """
        from osmium_chat.invite import InvitePreview

        result = await self._client.request(PB_CreateChatInvite(
            chat_ref=self._chat_ref,
            expires_at=expires_at,
            max_uses=max_uses,
        ))
        created = result.created_invite
        if created is None:
            raise RuntimeError("Gateway did not return a created invite")
        preview_result = await self._client.request(PB_LookupInvite(code=created.code))
        preview = preview_result.invite_preview
        if preview is None:
            raise RuntimeError("Gateway did not return an invite preview")
        return InvitePreview(preview, self._client)

    async def get_invites(self) -> "list[InvitePreview]":
        """Fetch all active invite links for this channel.

        :returns: The channel's active invites with full metadata.
        :raises RequestError: If the gateway rejects the request.
        """
        from osmium_chat.invite import InvitePreview

        result = await self._client.request(
            PB_ListChatInvites(chat_ref=self._chat_ref)
        )
        invite_list = result.invite_list
        if invite_list is None:
            return []
        return [InvitePreview(inv, self._client) for inv in invite_list.invites]
