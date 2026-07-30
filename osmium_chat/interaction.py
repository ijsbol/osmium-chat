"""Inbound button interaction objects."""

from typing import TYPE_CHECKING

from osmium_protos import PB_SetInteractionResponse

if TYPE_CHECKING:
    from osmium_chat.client import Client
    from osmium_chat.message import Message


__all__: tuple[str, ...] = ("Interaction",)


class Interaction:
    """A button interaction delivered by the gateway."""

    __slots__: tuple[str, ...] = (
        "id",
        "user_id",
        "message_id",
        "data",
        "message",
        "_client",
    )

    def __init__(
        self,
        interaction_id: int,
        user_id: int,
        message_id: int,
        data: str | None,
        client: "Client",
        *,
        message: "Message | None" = None,
    ) -> None:
        self.id = interaction_id
        self.user_id = user_id
        self.message_id = message_id
        self.data = data
        self.message = message
        self._client = client

    async def respond(self, message: str | None = None) -> None:
        """Acknowledge the interaction with an optional ephemeral message."""
        await self._client.request(PB_SetInteractionResponse(
            interaction_id=self.id,
            message=message,
        ))
