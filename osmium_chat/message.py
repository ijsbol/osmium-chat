from osmium_protos import PB_ChatRef, PB_Message


__all__: tuple[str, ...] = (
    "Message",
)


class Message:
    """A chat message, parsed from its protobuf representation.

    Holds where the message came from (``chat_ref``) so replies can be routed
    back to the same conversation, alongside its text content and metadata.
    """

    __slots__: tuple[str, ...] = (
        "id",
        "content",
        "author_id",
        "chat_ref",
        "reply_to",
    )

    def __init__(self, message: PB_Message) -> None:
        """Build a message from a protobuf payload.

        :param message: The raw ``PB_Message`` to read fields from.
        """
        self.id: int = message.message_id
        self.content: str = message.message
        self.author_id: int = message.author_id
        self.chat_ref: PB_ChatRef | None = message.chat_ref
        self.reply_to: int | None = message.reply_to
