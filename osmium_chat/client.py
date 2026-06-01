from logging import Logger
import platform
from typing import TYPE_CHECKING, Any, cast

from osmium_chat import __version__

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed
from osmium_protos import unwrap, wrap, PB_Initialize, PB_Authorization, PB_Authorize
from osmium_protos.osmium.client.auth import Authorization
from osmium_chat.user.user import User

if TYPE_CHECKING:
    from osmium_chat.bot import Bot


class Client:
    """Low-level WebSocket transport between a :class:`~osmium_chat.bot.Bot`
    and the Osmium gateway.

    Handles connecting, the initialize/authorize handshake, sending protobuf
    messages, and reading the inbound message stream.
    """

    __slots__: tuple[str, ...] = (
        "bot",
        "id",
        "_connection",
        "__session_id",
        "__token",
        "_logger",
    )

    WS_URL: str = "wss://ws-0.osmium.chat"

    def __init__(
        self,
        client_id: int,
        bot: "Bot",
        *,
        logger: Logger | None = None,
    ) -> None:
        """Create a client bound to ``bot``.

        :param client_id: The Osmium client id to identify as.
        :param bot: The owning bot, used to dispatch events and store the user.
        :param logger: Optional logger; a default one is created if omitted.
        """
        self.bot: "Bot" = bot
        self.id: int = client_id
        self._connection: ClientConnection | None = None
        self.__session_id: int | None = None
        self.__token: str | None = None
        self._logger = logger or Logger(__name__)

    async def _handle_msg(self, message: Any) -> None:
        """Process a single decoded inbound message.

        :param message: The unwrapped protobuf message.
        """
        self._logger.debug(f"Received message: {message}")

    async def _handle_ws(self, **kwargs: Any) -> None:
        """Read and dispatch inbound messages until the connection closes."""
        assert self._connection is not None

        async for data in self._connection:
            try:
                _, message = unwrap(cast(bytes, data))
                await self._handle_msg(message)
            except ConnectionClosed as e:
                self._logger.error("WebSocket connection closed: %s", e)
                raise ConnectionError("Connection closed while waiting for authorization") from e

    async def send_pb(self, message: Any) -> None:
        """Wrap, serialize, and send a protobuf message over the connection.

        :param message: The protobuf message to send.
        """
        assert self._connection is not None
        await self._connection.send(wrap(message).SerializeToString())

    def _handle_authorization(self, message: Authorization) -> None:
        """Store the session id/token and the authenticated user from an
        authorization response.

        :param message: The authorization payload from the gateway.
        """
        self.__session_id = message.session_id
        self.__token = message.token
        if message.user:
            self.bot.user = User(message.user)

    async def connect(self, token: str) -> None:
        """Open the connection, run the handshake, and process messages.

        Performs the initialize/authorize exchange, dispatches the bot's
        ``connect`` event once authorized, then blocks reading messages until
        the connection closes.

        :param token: The authorization token for the bot.
        :raises ConnectionError: If the connection closes before authorization.
        """
        self._logger.info("Connecting to WebSocket server...")
        self._connection = await connect(
            uri=self.WS_URL,
        )

        self._logger.info("Connected to WebSocket server, initializing...")
        await self.send_pb(PB_Initialize(
            client_id=self.id,
            device_type="Library[Python/OsmiumChat]",
            device_version=__version__,
            app_version=f"OsmiumChat Python API Wrapper (Python {platform.python_version()}) (OsmiumChat {__version__})",
            no_subscribe=False,
        ))

        self._logger.info("Received initialization response, getting entry points...")

        # this will return entry points and vapidPublicKey, but we don't need them for now
        await self._connection.recv()

        self._logger.info("Received initialization response, sending authorization...")
        await self.send_pb(PB_Authorize(
            token=token,
        ))

        # wait for authorization
        # most of the time it is the first or second message, but to be safe we will loop until we get it
        self._logger.info("Waiting for authorization...")
        async for data in self._connection:
            try:
                _, message = unwrap(cast(bytes, data))
                if isinstance(message, PB_Authorization):
                    self._handle_authorization(message)
                    break
                else:
                    await self._handle_msg(message)
            except ConnectionClosed:
                self._logger.error("Connection closed while waiting for authorization")
                raise ConnectionError("Connection closed while waiting for authorization")

        self._logger.info("Authorized successfully, dispatching connect event...")
        await self.bot.dispatch("connect")

        self._logger.info("Starting message handler...")
        await self._handle_ws()
