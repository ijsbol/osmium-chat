from typing import TYPE_CHECKING

from osmium_protos import PB_ChatRef, PB_SendMessage

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "Channel",
)


class Channel:
    """A conversation a message can be sent to.

    Wraps the :class:`~osmium_protos.PB_ChatRef` that identifies a destination
    (a user DM, community channel, group, or self) together with the client used
    to deliver outbound messages, so callers can simply ``await channel.send(...)``.
    """

    __slots__: tuple[str, ...] = (
        "_chat_ref",
        "_client",
    )

    def __init__(self, chat_ref: PB_ChatRef, client: "Client") -> None:
        """Bind a channel to a destination ref and the transport client.

        :param chat_ref: The ref identifying where messages should be delivered.
        :param client: The client used to send messages.
        """
        self._chat_ref = chat_ref
        self._client = client

    async def send(self, content: str, *, reply_to: int | None = None) -> None:
        """Send a text message to this channel.

        :param content: The message text to send.
        :param reply_to: Optional id of a message this should reply to.
        """
        await self._client.send_pb(PB_SendMessage(
            chat_ref=self._chat_ref,
            message=content,
            reply_to=reply_to,
        ))
