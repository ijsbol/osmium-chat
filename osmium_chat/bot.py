import asyncio
from collections.abc import Awaitable, Callable
from logging import Logger
from typing import Any, TypeVar

from osmium_protos import PB_UpdateMessageCreated, PB_UseInvite

from osmium_chat.channel import Channel
from osmium_chat.client import Client
from osmium_chat.community import Community
from osmium_chat.commands import Command, CommandCallback, StringView
from osmium_chat.context import Context
from osmium_chat.errors import CommandError, CommandNotFound
from osmium_chat.message import Message
from osmium_chat.user.user import User


EventHandler = Callable[..., Awaitable[None]]
EH = TypeVar("EH", bound=EventHandler)


class Bot:
    """The main entry point for an Osmium bot.

    Holds connection state, the registered event listeners, and the
    authenticated :class:`~osmium_chat.user.user.User` once connected.

    **Events**

    Listeners are registered with :meth:`on` and receive the arguments the event
    is dispatched with. The built-in events are:

    - ``connect`` — fired with no arguments once the bot has authorized.
    - ``message`` — fired with the :class:`~osmium_chat.context.Context` for
      *every* inbound message, regardless of where it came from.
    - ``guild_message`` — fired with the context when the message was sent in a
      community (guild) channel.
    - ``dm_message`` — fired with the context when the message was a direct
      message to the bot.
    - ``command_error`` — fired with ``(ctx, error)`` when a command lookup or
      invocation fails.

    .. code-block:: python

        @bot.on("message")
        async def on_message(ctx: Context) -> None:
            ...

        @bot.on("guild_message")
        async def on_guild_message(ctx: Context) -> None:
            ...

        @bot.on("dm_message")
        async def on_dm_message(ctx: Context) -> None:
            ...
    """

    __slots__: tuple[str, ...] = (
        "prefix",
        "_logger",
        "_client",
        "_listeners",
        "_commands",
        "user",
    )

    def __init__(
        self,
        prefix: str,
        client_id: int,
        *,
        logger: Logger | None = None,
    ) -> None:
        """Create a bot.

        :param prefix: The command prefix the bot responds to (e.g. ``"!"``).
        :param client_id: The Osmium client id this bot authenticates as.
        :param logger: Optional logger; a default one is created if omitted.
        """
        self.prefix = prefix
        self._logger = logger or Logger(__name__)
        self._client: Client = Client(
            client_id=client_id,
            bot=self,
            logger=self._logger,
        )
        self._listeners: dict[str, list[EventHandler]] = {}
        self._commands: dict[str, Command] = {}
        self.user: User | None = None

    def on(self, event: str) -> Callable[[EH], EH]:
        """Register a coroutine as a listener for the given event.

        This is the generic primitive every ``on_*`` decorator is built on,
        so new events only need a thin wrapper here plus a ``dispatch`` call
        from wherever the event originates.

        .. code-block:: python

            @bot.on("connect")
            async def handler() -> None:
                ...
        """
        def decorator(func: EH) -> EH:
            self._listeners.setdefault(event, []).append(func)
            return func
        return decorator

    async def dispatch(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Invoke every listener registered for ``event``.

        Handler errors are logged and swallowed so one faulty listener can't
        take down the connection or block the others.
        """
        for handler in self._listeners.get(event, []):
            try:
                await handler(*args, **kwargs)
            except Exception:
                self._logger.exception("Error in '%s' event handler", event)

    def command(
        self,
        name: str | None = None,
        *,
        aliases: tuple[str, ...] = (),
    ) -> Callable[[CommandCallback], Command]:
        """Register a coroutine as a command.

        The decorated coroutine receives a :class:`~osmium_chat.context.Context`
        as its first argument; every parameter after that is parsed from the
        message text and converted to its annotated type. Parameters with a
        default become optional, a keyword-only parameter (after ``*``) consumes
        the rest of the message, and ``*args`` collects all remaining tokens.

        .. code-block:: python

            @bot.command("say")
            async def say(ctx: Context, *, words: str = "...") -> None:
                await ctx.channel.send(words)

        :param name: The command name; defaults to the function name.
        :param aliases: Additional names the command also responds to.
        """
        def decorator(func: CommandCallback) -> Command:
            command = Command(func, name=name, aliases=aliases)
            self.add_command(command)
            return command
        return decorator

    def add_command(self, command: Command) -> None:
        """Register a command under its name and every alias.

        :param command: The command to register.
        :raises ValueError: If the name or an alias is already registered.
        """
        for key in (command.name, *command.aliases):
            if key in self._commands:
                raise ValueError(f"Command name {key!r} is already registered")
            self._commands[key] = command

    def get_command(self, name: str) -> Command | None:
        """Look up a command by name or alias.

        :param name: The name or alias to resolve.
        """
        return self._commands.get(name)

    async def process_commands(self, update: PB_UpdateMessageCreated) -> None:
        """Turn an inbound message into a command invocation.

        Builds the :class:`~osmium_chat.context.Context`, fires the ``message``
        event, and — if the message starts with the prefix and names a known
        command — parses its arguments and invokes it. Command failures are
        surfaced through the ``command_error`` event.

        :param update: The decoded ``message_created`` payload from the gateway.
        """
        if update.message is None or update.message.chat_ref is None:
            return

        author = User(update.author, self._client) if update.author else None
        message = Message(update.message, self._client, author=author)
        chat_ref = update.message.chat_ref
        channel_ref = chat_ref.channel
        channel = Channel(
            chat_ref,
            self._client,
            id=channel_ref.channel_id if channel_ref is not None else None,
            community_id=channel_ref.community_id if channel_ref is not None else None,
        )
        community = (
            Community.from_id(channel_ref.community_id, self._client)
            if channel_ref is not None
            else None
        )
        ctx = Context(
            bot=self,
            message=message,
            author=author,
            channel=channel,
            community=community,
            prefix=self.prefix,
        )

        await self.dispatch("message", ctx)
        # Fire the finer-grained event for where the message came from. A
        # ``chat_ref`` carrying a ``channel`` is a community (guild) channel; one
        # carrying a ``user`` is a direct message.
        if chat_ref.channel is not None:
            await self.dispatch("guild_message", ctx)
        elif chat_ref.user is not None:
            await self.dispatch("dm_message", ctx)

        # Never react to our own messages, to avoid command loops.
        if self.user is not None and message.author_id == self.user.id:
            return

        content = message.content
        if not content.startswith(self.prefix):
            return

        view = StringView(content[len(self.prefix):])
        name = view.get_word()
        if not name:
            return

        ctx.invoked_with = name
        command = self.get_command(name)
        if command is None:
            await self.dispatch("command_error", ctx, CommandNotFound(name))
            return

        try:
            await command.invoke(ctx, view)
        except CommandError as error:
            await self.dispatch("command_error", ctx, error)
        except Exception as error:
            self._logger.exception("Unhandled error in command %r", name)
            await self.dispatch("command_error", ctx, error)

    async def use_invite(self, invite_code: str) -> None:
        """Redeem an invite code on behalf of the bot.

        :param invite_code: The invite code to redeem.
        """
        self._logger.info(f"Using invite with code: {invite_code}")
        await self._client.send_pb(PB_UseInvite(code=invite_code))

    async def connect(self, token: str) -> None:
        """Connect to Osmium and run the bot until the connection closes.

        This authenticates with ``token``, fires the ``connect`` event, then
        blocks processing incoming messages.

        :param token: The authorization token for this bot.
        """
        await self._client.connect(token)

    def run(self, token: str) -> None:
        """Start the bot's event loop and connect, blocking until it closes.

        A synchronous convenience wrapper around :meth:`connect` for use as a
        program's entry point.

        :param token: The authorization token for this bot.
        """
        asyncio.run(self.connect(token))
