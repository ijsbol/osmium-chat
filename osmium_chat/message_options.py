"""Value objects used by the v2 message send and reply APIs."""

from dataclasses import dataclass

from osmium_protos import (
    PB_MessageEntity,
    PB_MessageMessageReplyInfo,
    PB_SendMessageBotInfo,
    PB_SendMessageBotInfoMessageCloak,
    PB_SendMessageReplyTo,
    PB_SendMessageReplyToQuote,
)

from osmium_chat.content import Content


@dataclass(frozen=True, slots=True, init=False)
class MessageQuote:
    """A partial or complete quote attached to a reply."""

    message: str
    entities: tuple[PB_MessageEntity, ...]
    offset: int | None

    def __init__(
        self,
        content: str | Content,
        *,
        offset: int | None = None,
    ) -> None:
        content_obj = content if isinstance(content, Content) else Content(content)
        object.__setattr__(self, "message", content_obj.text)
        object.__setattr__(self, "entities", tuple(content_obj.entities))
        object.__setattr__(self, "offset", offset)

    @classmethod
    def from_pb(cls, quote: object) -> "MessageQuote":
        obj = cls.__new__(cls)
        object.__setattr__(obj, "message", quote.message)
        object.__setattr__(obj, "entities", tuple(quote.entities))
        object.__setattr__(obj, "offset", quote.offset)
        return obj

    def to_send_pb(self) -> PB_SendMessageReplyToQuote:
        return PB_SendMessageReplyToQuote(
            message=self.message,
            entities=list(self.entities),
            offset=self.offset,
        )


@dataclass(frozen=True, slots=True)
class MessageCloak:
    """The pseudoidentity shown for a bot-authored message."""

    name: str
    photo_id: int | None = None

    @classmethod
    def from_pb(cls, cloak: object) -> "MessageCloak":
        return cls(
            name=cloak.name,
            photo_id=cloak.photo.file_id if cloak.photo is not None else None,
        )

    def to_send_pb(self) -> PB_SendMessageBotInfoMessageCloak:
        return PB_SendMessageBotInfoMessageCloak(name=self.name, photo_id=self.photo_id)


def make_send_reply_to(
    reply_to: int | object | None,
    quote: MessageQuote | None = None,
) -> PB_SendMessageReplyTo | None:
    if reply_to is None:
        if quote is not None:
            raise ValueError("A quote requires a reply target")
        return None
    message_id = reply_to if isinstance(reply_to, int) else reply_to.id
    return PB_SendMessageReplyTo(
        message_id=message_id,
        quote=quote.to_send_pb() if quote is not None else None,
    )


def make_message_reply_info(
    reply_to: int | object | None,
    quote: MessageQuote | None = None,
) -> PB_MessageMessageReplyInfo | None:
    if reply_to is None:
        if quote is not None:
            raise ValueError("A quote requires a reply target")
        return None
    message_id = reply_to if isinstance(reply_to, int) else reply_to.id
    from osmium_protos import PB_MessageMessageReplyInfoQuote

    wire_quote = None
    if quote is not None:
        wire_quote = PB_MessageMessageReplyInfoQuote(
            message=quote.message,
            entities=list(quote.entities),
            offset=quote.offset,
        )
    return PB_MessageMessageReplyInfo(message_id=message_id, quote=wire_quote)


def make_bot_info(
    cloak: MessageCloak | None,
    buttons: object | None = None,
) -> PB_SendMessageBotInfo | None:
    if cloak is None and buttons is None:
        return None
    from osmium_chat.button import make_button_rows

    return PB_SendMessageBotInfo(
        cloak=cloak.to_send_pb() if cloak is not None else None,
        buttons=make_button_rows(buttons) if buttons is not None else None,
    )
