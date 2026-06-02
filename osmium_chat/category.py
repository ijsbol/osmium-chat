from typing import TYPE_CHECKING

from osmium_protos import PB_Channel

from osmium_chat.channel import Channel

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "Category",
)


class Category(Channel):
    """A category channel that groups other channels under it.

    Subclasses :class:`~osmium_chat.channel.Channel` — it can be sent to,
    edited, and deleted via the inherited methods. The extra :attr:`channels`
    attribute holds the channels nested under this category.
    """

    __slots__: tuple[str, ...] = ("channels",)

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.channels: list[Channel] = []

    @classmethod
    def from_pb(  # type: ignore[override]
        cls,
        channel: PB_Channel,
        client: "Client",
        *,
        channels: "list[Channel] | None" = None,
    ) -> "Category":
        """Build a category from a protobuf channel and its child channels.

        :param channel: The raw ``PB_Channel`` with ``type=CATEGORY``.
        :param client: The client used for subsequent operations.
        :param channels: The channels nested under this category.
        :returns: The built :class:`Category`.
        """
        obj: Category = super().from_pb(channel, client)  # type: ignore[assignment]
        obj.channels = channels if channels is not None else []
        return obj
