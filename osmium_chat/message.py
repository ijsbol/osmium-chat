from typing import TYPE_CHECKING

from osmium_protos import (
    PB_AddReaction,
    PB_ChatRef,
    PB_DeleteMessage,
    PB_EditMessage,
    PB_Message,
    PB_ReactionEmoji,
    PB_RemoveReaction,
    PB_SendMessage,
)

from osmium_chat.content import Content, UnicodeEmoji, parse_content
from osmium_chat.file import File
from osmium_chat.member import Member
from osmium_chat.reaction import Reaction
from osmium_chat.user.user import User

if TYPE_CHECKING:
    from osmium_chat.channel import Channel
    from osmium_chat.client import Client
    from osmium_chat.community import Community
    from osmium_chat.emoji import CustomEmoji


__all__: tuple[str, ...] = (
    "Message",
)


def _to_pb_reaction_emoji(emoji: "CustomEmoji | UnicodeEmoji | str") -> PB_ReactionEmoji:
    from osmium_chat.emoji import CustomEmoji as _CustomEmoji
    if isinstance(emoji, str):
        return PB_ReactionEmoji(unicode_emoji=emoji)
    if isinstance(emoji, UnicodeEmoji):
        return PB_ReactionEmoji(unicode_emoji=emoji.emoji)
    return PB_ReactionEmoji(custom_emoji=emoji.id)


class Message:
    """A chat message, parsed from its protobuf representation.

    Holds where the message came from (:attr:`chat_ref`) so replies, edits, and
    deletes can be routed back to the same conversation, alongside its text
    content, the resolved :attr:`author`, and other metadata.
    """

    __slots__: tuple[str, ...] = (
        "id",
        "content",
        "content_raw",
        "author_id",
        "author",
        "chat_ref",
        "reply_to",
        "attachments",
        "reactions",
        "channel",
        "community",
        "_client",
    )

    def __init__(
        self,
        message: PB_Message,
        client: "Client",
        *,
        author: "Member | User | None" = None,
        channel: "Channel | None" = None,
        community: "Community | None" = None,
    ) -> None:
        """Build a message from a protobuf payload.

        :param message: The raw ``PB_Message`` to read fields from.
        :param client: The client used to edit, delete, reply, and react to
            the message.
        :param author: The resolved author who sent the message. A
            :class:`~osmium_chat.member.Member` for community messages (when
            the gateway supplied user data), a
            :class:`~osmium_chat.user.user.User` for DMs, or ``None`` if the
            gateway did not include author information.
        :param channel: The channel the message was sent in, if known.
        :param community: The community the message was sent in, or ``None``
            for DMs. Only :attr:`~Community.id` is guaranteed to be meaningful.
        """
        self.id: int = message.message_id
        self.content_raw: Content = parse_content(message.message, list(message.entities))
        self.content: str = message.message
        self.author_id: int = message.author_id
        self.author: Member | User | None = author
        self.chat_ref: PB_ChatRef | None = message.chat_ref
        self.reply_to: int | None = message.reply_to
        self.attachments: list[File] = [
            File(media.file.file, client)
            for media in message.media
            if media.file is not None and media.file.file is not None
        ]
        self.reactions: list[Reaction] = []
        self.channel: "Channel | None" = channel
        self.community: "Community | None" = community
        self._client = client

    async def edit(self, content: "str | Content") -> "Message":
        """Edit this message's text content.

        Waits for the gateway to confirm the edit and updates
        :attr:`content` and :attr:`content_raw` to match.

        :param content: The new message text, either a plain string or a
            :class:`~osmium_chat.content.Content` object.
        :returns: This message, with its content updated.
        :raises ValueError: If the message has no chat ref to route the edit to.
        :raises RequestError: If the gateway rejects the edit.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot edit a message without a chat ref")
        new_raw = content if isinstance(content, Content) else Content(content)
        await self._client.request(PB_EditMessage(
            chat_ref=self.chat_ref,
            message_id=self.id,
            message=new_raw.text,
            entities=new_raw.entities,
        ))
        self.content_raw = new_raw
        self.content = new_raw.text
        return self

    async def delete(self) -> None:
        """Delete this message.

        :raises ValueError: If the message has no chat ref to route the delete to.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot delete a message without a chat ref")
        await self._client.send_pb(PB_DeleteMessage(
            chat_ref=self.chat_ref,
            message_ids=[self.id],
        ))

    async def add_reaction(self, emoji: "CustomEmoji | UnicodeEmoji | str") -> None:
        """Add a reaction to this message.

        Accepts a :class:`~osmium_chat.emoji.CustomEmoji`, a
        :class:`~osmium_chat.content.UnicodeEmoji`, or a plain Unicode emoji
        string (e.g. ``"🎉"``). A user may only add one reaction of each
        emoji type to a message.

        :param emoji: The emoji to react with.
        :raises ValueError: If the message has no chat ref.
        :raises RequestError: If the gateway rejects the request.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot react to a message without a chat ref")
        await self._client.send_pb(PB_AddReaction(
            chat_ref=self.chat_ref,
            message_id=self.id,
            emoji=_to_pb_reaction_emoji(emoji),
        ))

    async def remove_reaction(self, emoji: "CustomEmoji | UnicodeEmoji | str") -> None:
        """Remove a previously added reaction from this message.

        Accepts a :class:`~osmium_chat.emoji.CustomEmoji`, a
        :class:`~osmium_chat.content.UnicodeEmoji`, or a plain Unicode emoji
        string (e.g. ``"🎉"``).

        :param emoji: The emoji reaction to remove.
        :raises ValueError: If the message has no chat ref.
        :raises RequestError: If the gateway rejects the request.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot remove a reaction from a message without a chat ref")
        await self._client.send_pb(PB_RemoveReaction(
            chat_ref=self.chat_ref,
            message_id=self.id,
            emoji=_to_pb_reaction_emoji(emoji),
        ))

    async def reply_file(
        self,
        data: bytes,
        filename: str,
        *,
        mimetype: str = "application/octet-stream",
    ) -> "Message":
        """Upload ``data`` and send it as a file reply to this message.

        :param data: The raw file bytes to upload and attach.
        :param filename: The file name shown to recipients.
        :param mimetype: The MIME type of the file; defaults to
            ``application/octet-stream``.
        :returns: The newly created reply message carrying the file attachment.
        :raises ValueError: If the message has no chat ref to reply into.
        :raises RequestError: If the gateway rejects the upload or send.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot reply to a message without a chat ref")
        _, media_ref = await self._client.upload_file(data, filename, mimetype)
        result = await self._client.request(PB_SendMessage(
            chat_ref=self.chat_ref,
            media=[media_ref],
            reply_to=self.id,
        ))
        author = self._client.bot.user
        sent = result.sent_message
        return Message(
            PB_Message(
                chat_ref=self.chat_ref,
                message_id=sent.message_id if sent is not None else 0,
                author_id=author.id if author is not None else 0,
                media=[],
                reply_to=self.id,
            ),
            self._client,
            author=author,
        )

    async def reply(self, content: "str | Content") -> "Message":
        """Send a message to this message's conversation, threaded as a reply.

        Waits for the gateway to acknowledge the send so the returned message
        carries the server-assigned id.

        :param content: The reply text, either a plain string or a
            :class:`~osmium_chat.content.Content` object.
        :returns: The newly created reply message.
        :raises ValueError: If the message has no chat ref to reply into.
        :raises RequestError: If the gateway rejects the send.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot reply to a message without a chat ref")
        content_obj = content if isinstance(content, Content) else Content(content)
        result = await self._client.request(PB_SendMessage(
            chat_ref=self.chat_ref,
            message=content_obj.text,
            entities=content_obj.entities,
            reply_to=self.id,
        ))
        author = self._client.bot.user
        sent = result.sent_message
        return Message(
            PB_Message(
                chat_ref=self.chat_ref,
                message_id=sent.message_id if sent is not None else 0,
                author_id=author.id if author is not None else 0,
                message=content_obj.text,
                entities=content_obj.entities,
                reply_to=self.id,
            ),
            self._client,
            author=author,
        )
