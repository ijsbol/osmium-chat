from collections.abc import Awaitable, Callable
from logging import Logger
from typing import Any, TypeVar

from osmium_protos import PB_UseInvite

from osmium_chat.client import Client
from osmium_chat.user.user import User


EventHandler = Callable[..., Awaitable[None]]
EH = TypeVar("EH", bound=EventHandler)


class Bot:
    """The main entry point for an Osmium bot.

    Holds connection state, the registered event listeners, and the
    authenticated :class:`~osmium_chat.user.user.User` once connected.
    """

    __slots__: tuple[str, ...] = (
        "prefix",
        "_logger",
        "_client",
        "_listeners",
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

    def on_connect(self) -> Callable[[EH], EH]:
        """Register a listener fired once the bot is connected and authorized."""
        return self.on("connect")

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
