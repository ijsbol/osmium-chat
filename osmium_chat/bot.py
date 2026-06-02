import asyncio
from collections.abc import Awaitable, Callable
from logging import Logger
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from osmium_chat.invite import InvitePreview

from osmium_protos import PB_CommunityMember, PB_LookupInvite, PB_UpdateMessageCreated, PB_UseInvite

from osmium_chat.channel import Channel
from osmium_chat.client import Client
from osmium_chat.community import Community
from osmium_chat.commands import Command, Commands, CommandRestriction, StringView
from osmium_chat.context import Context
from osmium_chat.errors import CommandError, CommandNotFound, CommandRestrictionError
from osmium_chat.member import Member
from osmium_chat.message import Message
from osmium_chat.user.user import User


EventHandler = Callable[..., Awaitable[None]]


class Bot:
    """The main entry point for an Osmium bot.

    Holds connection state, the registered event listeners, and the
    authenticated :class:`~osmium_chat.user.user.User` once connected.

    Commands and event listeners are defined by subclassing
    :class:`~osmium_chat.commands.Commands` and registering the subclass with
    :meth:`add_commands`.

    **Events**

    The built-in events (used with
    :func:`~osmium_chat.commands.listen`) are:

    - ``connect`` — fired with no arguments once the bot has authorized.
    - ``message`` — fired with a :class:`~osmium_chat.message.Message` for
      *every* inbound message, regardless of where it came from.
    - ``guild_message`` — fired with a :class:`~osmium_chat.message.Message`
      when the message was sent in a community (guild) channel.
    - ``dm_message`` — fired with a :class:`~osmium_chat.message.Message`
      when the message was a direct message to the bot.
    - ``command_error`` — fired with ``(ctx, error)`` when a command lookup or
      invocation fails.

    .. code-block:: python

        from osmium_chat import Bot, Context, Message, commands

        class MyCommands(commands.Commands):
            @commands.listen("message")
            async def on_message(self, message: Message) -> None:
                ...

            @commands.command("ping")
            async def ping(self, ctx: Context) -> None:
                await ctx.channel.send("pong")

        bot = Bot(prefix="!", client_id=12345)
        bot.add_commands(MyCommands)
        bot.run(token="...")
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

    async def lookup_invite(self, code: str) -> "InvitePreview":
        """Fetch an invite by code and return its full metadata.

        :param code: The invite code to resolve.
        :returns: The :class:`~osmium_chat.invite.InvitePreview` for the invite.
        :raises RequestError: If the gateway cannot find the invite.
        """
        from osmium_chat.invite import InvitePreview

        result = await self._client.request(PB_LookupInvite(code=code))
        preview = result.invite_preview
        if preview is None:
            raise RuntimeError("Gateway did not return an invite preview")
        return InvitePreview(preview, self._client)

    def _add_command(self, command: Command) -> None:
        for key in (command.name, *command.aliases):
            if key in self._commands:
                raise ValueError(f"Command name {key!r} is already registered")
            self._commands[key] = command

    def add_commands(self, cls: type[Commands], *args: Any, **kwargs: Any) -> None:
        """Instantiate a :class:`~osmium_chat.commands.Commands` subclass and
        register all its decorated commands and listeners.

        The bot calls ``cls(self, *args, **kwargs)``, so any extra arguments
        are forwarded directly to the subclass ``__init__`` after ``bot``.
        This lets command collections accept configuration at registration
        time without needing globals or post-init setters:

        .. code-block:: python

            class Greeter(commands.Commands):
                def __init__(self, bot: Bot, greeting: str) -> None:
                    super().__init__(bot)
                    self.greeting = greeting

                @commands.command("hi")
                async def hi(self, ctx: Context) -> None:
                    await ctx.channel.send(self.greeting)

            bot.add_commands(Greeter, greeting="Howdy!")

        :param cls: An uninitialised :class:`~osmium_chat.commands.Commands`
            subclass.
        :param args: Extra positional arguments passed to ``cls.__init__``
            after ``bot``.
        :param kwargs: Extra keyword arguments passed to ``cls.__init__``.
        :raises ValueError: If any command name or alias is already registered.
        """
        instance = cls(self, *args, **kwargs)
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(cls, attr_name, None)
            if attr is None:
                continue
            cmd_meta = getattr(attr, "_command_meta", None)
            if cmd_meta is not None:
                bound = getattr(instance, attr_name)
                name = cmd_meta.name or attr_name
                self._add_command(Command(bound, name=name, aliases=cmd_meta.aliases, restriction=cmd_meta.restriction))
                continue
            listen_meta = getattr(attr, "_listen_meta", None)
            if listen_meta is not None:
                bound = getattr(instance, attr_name)
                self._listeners.setdefault(listen_meta.event, []).append(bound)

    def remove_commands(self, cls: type[Commands]) -> None:
        """Remove all commands and listeners that were registered from *cls*.

        :param cls: The same :class:`~osmium_chat.commands.Commands` subclass
            that was passed to :meth:`add_commands`.
        """
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(cls, attr_name, None)
            if attr is None:
                continue
            cmd_meta = getattr(attr, "_command_meta", None)
            if cmd_meta is not None:
                name = cmd_meta.name or attr_name
                cmd = self._commands.get(name)
                if cmd is not None:
                    for key in [k for k, v in self._commands.items() if v is cmd]:
                        del self._commands[key]
                continue
            listen_meta = getattr(attr, "_listen_meta", None)
            if listen_meta is not None:
                event = listen_meta.event
                handlers = self._listeners.get(event, [])
                self._listeners[event] = [
                    h for h in handlers
                    if getattr(h, "__func__", None) is not attr
                ]

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

        chat_ref = update.message.chat_ref
        channel_ref = chat_ref.channel
        community = (
            Community.from_id(channel_ref.community_id, self._client)
            if channel_ref is not None
            else None
        )
        if update.author and community is not None:
            author: Member | User | None = Member(
                PB_CommunityMember(id=update.author.id, community_id=community.id),
                update.author,
                self._client,
                community=community,
            )
        elif update.author:
            author = User(update.author, self._client)
        else:
            author = None
        channel = Channel(
            chat_ref,
            self._client,
            id=channel_ref.channel_id if channel_ref is not None else None,
            community_id=channel_ref.community_id if channel_ref is not None else None,
            community=community,
        )
        message = Message(
            update.message,
            self._client,
            author=author,
            channel=channel,
            community=community,
        )
        ctx = Context(
            bot=self,
            message=message,
            author=author,
            channel=channel,
            community=community,
            prefix=self.prefix,
        )

        await self.dispatch("message", message)
        # Fire the finer-grained event for where the message came from. A
        # ``chat_ref`` carrying a ``channel`` is a community (guild) channel; one
        # carrying a ``user`` is a direct message.
        if chat_ref.channel is not None:
            await self.dispatch("guild_message", message)
        elif chat_ref.user is not None:
            await self.dispatch("dm_message", message)

        # Never react to our own messages, to avoid command loops.
        if self.user is not None and message.author_id == self.user.id:
            return

        content = str(message.content_raw)
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

        is_dm = ctx.community is None
        if command.restriction is CommandRestriction.DM_ONLY and not is_dm:
            await self.dispatch("command_error", ctx, CommandRestrictionError(command.name, command.restriction))
            return
        if command.restriction is CommandRestriction.COMMUNITY_ONLY and is_dm:
            await self.dispatch("command_error", ctx, CommandRestrictionError(command.name, command.restriction))
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
