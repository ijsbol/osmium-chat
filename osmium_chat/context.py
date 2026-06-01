from typing import TYPE_CHECKING, Any

from osmium_chat.channel import Channel
from osmium_chat.message import Message
from osmium_chat.user.user import User

if TYPE_CHECKING:
    from osmium_chat.bot import Bot
    from osmium_chat.commands import Command


__all__: tuple[str, ...] = (
    "Context",
)


class Context:
    """The invocation context handed to a command callback.

    Bundles everything a command needs: who sent the message
    (:attr:`author`), where it came from (:attr:`channel`), the underlying
    :attr:`message`, and the resolved command metadata. Reply with
    ``await ctx.channel.send(...)`` or the :meth:`send` shortcut.
    """

    __slots__: tuple[str, ...] = (
        "bot",
        "message",
        "author",
        "channel",
        "prefix",
        "command",
        "invoked_with",
        "args",
    )

    def __init__(
        self,
        *,
        bot: "Bot",
        message: Message,
        author: User | None,
        channel: Channel,
        prefix: str,
        command: "Command | None" = None,
        invoked_with: str | None = None,
        args: list[Any] | None = None,
    ) -> None:
        """Create a context.

        :param bot: The bot handling the message.
        :param message: The message that triggered the command.
        :param author: The user who sent the message, if known.
        :param channel: The channel the message was sent in.
        :param prefix: The prefix the message was invoked with.
        :param command: The resolved command, if one matched.
        :param invoked_with: The name or alias actually used to invoke it.
        :param args: The converted positional arguments passed to the callback.
        """
        self.bot = bot
        self.message = message
        self.author = author
        self.channel = channel
        self.prefix = prefix
        self.command = command
        self.invoked_with = invoked_with
        self.args: list[Any] = args if args is not None else []

    async def send(self, content: str, *, reply_to: int | None = None) -> Message:
        """Send a message to the channel this command was invoked in.

        A shortcut for ``ctx.channel.send(...)``.

        :param content: The message text to send.
        :param reply_to: Optional id of a message this should reply to.
        :returns: The newly created message.
        """
        return await self.channel.send(content, reply_to=reply_to)

    async def reply(self, content: str) -> Message:
        """Reply to the invoking message, threading it as a reply.

        :param content: The message text to send.
        :returns: The newly created message.
        """
        return await self.channel.send(content, reply_to=self.message.id)
