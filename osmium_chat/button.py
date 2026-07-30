"""Instance-owned message buttons and their wire conversion."""

import inspect
import secrets
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any

from osmium_protos import (
    PB_MessagesMessageButton,
    PB_MessagesMessageButtonMessageButtonClipboard,
    PB_MessagesMessageButtonMessageButtonInteraction,
    PB_MessagesMessageButtonMessageButtonUrl,
    PB_SendMessageBotInfoButtons,
    PB_SendMessageBotInfoButtonsButtonRow,
)

if TYPE_CHECKING:
    from osmium_chat.interaction import Interaction
    from osmium_chat.message import Message


ButtonCallback = Callable[["Interaction"], Awaitable[None] | None]


__all__: tuple[str, ...] = ("Button", "ClipboardButton", "LinkButton")


class Button:
    """An interaction button with an instance-specific callback."""

    __slots__: tuple[str, ...] = ("label", "custom_id", "_fixed_id", "_callback")

    def __init__(
        self,
        label: str,
        custom_id: str | None = None,
        *,
        callback: ButtonCallback | None = None,
    ) -> None:
        self.label = label
        self._fixed_id = custom_id is not None
        self.custom_id = custom_id if custom_id is not None else secrets.token_urlsafe(18)
        self._callback = callback

    async def on_interaction(self, interaction: "Interaction") -> None:
        """Handle this button's interaction; subclasses may override this."""
        if self._callback is None:
            return
        result = self._callback(interaction)
        if inspect.isawaitable(result):
            await result

    @property
    def interactive(self) -> bool:
        """Whether this button can produce an interaction update."""
        return True

    def to_pb(self) -> PB_MessagesMessageButton:
        """Build the interaction-button protobuf payload."""
        return PB_MessagesMessageButton(
            label=self.label,
            interaction=PB_MessagesMessageButtonMessageButtonInteraction(
                data=self.custom_id,
            ),
        )

    @classmethod
    def from_pb(cls, button: Any) -> "Button":
        if button.interaction is not None:
            return cls(button.label, button.interaction.data)
        if button.url is not None:
            return LinkButton(button.label, button.url.url)
        if button.clipboard is not None:
            return ClipboardButton(button.label, button.clipboard.text)
        return cls(button.label)

    async def submit(self, message: "Message") -> str | None:
        """Submit this button as a client-side interaction for ``message``."""
        from osmium_protos import PB_SubmitInteraction

        if not self.interactive:
            raise ValueError("Only interaction buttons can be submitted")
        if message.chat_ref is None:
            raise ValueError("Cannot submit a button without a message chat ref")
        result = await message._client.request(PB_SubmitInteraction(
            chat_ref=message.chat_ref,
            message_id=message.id,
            data=self.custom_id,
        ))
        response = result.interaction_response
        return response.message if response is not None else None


class LinkButton(Button):
    """A button that opens a URL and does not produce an interaction update."""

    __slots__: tuple[str, ...] = ("url",)

    def __init__(self, label: str, url: str) -> None:
        super().__init__(label, custom_id=url)
        self.url = url

    async def on_interaction(self, interaction: "Interaction") -> None:
        return None

    @property
    def interactive(self) -> bool:
        return False

    def to_pb(self) -> PB_MessagesMessageButton:
        return PB_MessagesMessageButton(
            label=self.label,
            url=PB_MessagesMessageButtonMessageButtonUrl(url=self.url),
        )


class ClipboardButton(Button):
    """A button that copies text and does not produce an interaction update."""

    __slots__: tuple[str, ...] = ("text",)

    def __init__(self, label: str, text: str) -> None:
        super().__init__(label, custom_id=text)
        self.text = text

    async def on_interaction(self, interaction: "Interaction") -> None:
        return None

    @property
    def interactive(self) -> bool:
        return False

    def to_pb(self) -> PB_MessagesMessageButton:
        return PB_MessagesMessageButton(
            label=self.label,
            clipboard=PB_MessagesMessageButtonMessageButtonClipboard(text=self.text),
        )


def make_button_rows(
    rows: Sequence[Sequence[Button]],
) -> PB_SendMessageBotInfoButtons:
    if len(rows) > 5 or any(len(row) > 5 for row in rows):
        raise ValueError("Messages support at most five button rows of five buttons each")
    return PB_SendMessageBotInfoButtons(
        rows=[PB_SendMessageBotInfoButtonsButtonRow(
            buttons=[button.to_pb() for button in row],
        ) for row in rows]
    )
