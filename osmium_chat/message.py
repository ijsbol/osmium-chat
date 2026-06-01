from typing import TYPE_CHECKING

from osmium_protos import (
    PB_ChatRef,
    PB_DeleteMessage,
    PB_EditMessage,
    PB_Message,
    PB_SendMessage,
)

from osmium_chat.user.user import User

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "Message",
)


class Message:
    """A chat message, parsed from its protobuf representation.

    Holds where the message came from (:attr:`chat_ref`) so replies, edits, and
    deletes can be routed back to the same conversation, alongside its text
    content, the resolved :attr:`author`, and other metadata.
    """

    __slots__: tuple[str, ...] = (
        "id",
        "content",
        "author_id",
        "author",
        "chat_ref",
        "reply_to",
        "_client",
    )

    def __init__(
        self,
        message: PB_Message,
        client: "Client",
        *,
        author: User | None = None,
    ) -> None:
        """Build a message from a protobuf payload.

        :param message: The raw ``PB_Message`` to read fields from.
        :param client: The client used to edit, delete, and reply to the message.
        :param author: The resolved :class:`~osmium_chat.user.user.User` who sent
            the message, if the gateway supplied one.
        """
        self.id: int = message.message_id
        self.content: str = message.message
        self.author_id: int = message.author_id
        self.author: User | None = author
        self.chat_ref: PB_ChatRef | None = message.chat_ref
        self.reply_to: int | None = message.reply_to
        self._client = client

    async def edit(self, content: str) -> "Message":
        """Edit this message's text content.

        Waits for the gateway to confirm the edit and updates
        :attr:`content` to match.

        :param content: The new message text.
        :returns: This message, with its content updated.
        :raises ValueError: If the message has no chat ref to route the edit to.
        :raises RequestError: If the gateway rejects the edit.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot edit a message without a chat ref")
        await self._client.request(PB_EditMessage(
            chat_ref=self.chat_ref,
            message_id=self.id,
            message=content,
        ))
        self.content = content
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

    async def reply(self, content: str) -> "Message":
        """Send a message to this message's conversation, threaded as a reply.

        Waits for the gateway to acknowledge the send so the returned message
        carries the server-assigned id.

        :param content: The reply text to send.
        :returns: The newly created reply message.
        :raises ValueError: If the message has no chat ref to reply into.
        :raises RequestError: If the gateway rejects the send.
        """
        if self.chat_ref is None:
            raise ValueError("Cannot reply to a message without a chat ref")
        result = await self._client.request(PB_SendMessage(
            chat_ref=self.chat_ref,
            message=content,
            reply_to=self.id,
        ))
        author = self._client.bot.user
        sent = result.sent_message
        return Message(
            PB_Message(
                chat_ref=self.chat_ref,
                message_id=sent.message_id if sent is not None else 0,
                author_id=author.id if author is not None else 0,
                message=content,
                reply_to=self.id,
            ),
            self._client,
            author=author,
        )
