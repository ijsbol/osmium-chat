import asyncio
from collections.abc import Coroutine
from logging import Logger
import platform
from typing import TYPE_CHECKING, Any, cast

from osmium_chat import __version__

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed
from osmium_protos import (
    unwrap,
    wrap,
    PB_Authorization,
    PB_Authorize,
    PB_Initialize,
    PB_RpcResult,
    PB_ServerMessage,
    PB_UpdateMessageCreated,
)
from osmium_protos.osmium.client.auth import Authorization
from osmium_chat.errors import RequestError
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
        "_pending",
        "_req_counter",
        "_tasks",
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
        # Outstanding requests awaiting an ``RpcResult``, keyed by request id.
        self._pending: dict[int, asyncio.Future[PB_RpcResult]] = {}
        # Monotonic source of request ids; starts at 1 so it never collides with
        # the ``id=0`` used by fire-and-forget :meth:`send_pb` calls.
        self._req_counter: int = 0
        # Strong references to in-flight dispatch tasks so they aren't GC'd.
        self._tasks: set[asyncio.Task[None]] = set()

    async def _handle_msg(self, message: Any) -> None:
        """Process a single decoded inbound message.

        Routes ``message_created`` updates into the bot's command pipeline; all
        other messages are logged for now.

        :param message: The unwrapped protobuf message.
        """
        self._logger.debug(f"Received message: {message}")
        if isinstance(message, PB_UpdateMessageCreated):
            await self.bot.process_commands(message)

    async def _handle_ws(self, **kwargs: Any) -> None:
        """Read and dispatch inbound messages until the connection closes.

        Responses to outstanding :meth:`request` calls are resolved inline so the
        correlation stays ordered, while everything else is dispatched on its own
        task. Dispatching concurrently is what lets a command await a
        :meth:`request` response: the read loop keeps draining frames (including
        that very response) instead of blocking on the handler.
        """
        assert self._connection is not None

        async for data in self._connection:
            try:
                server = PB_ServerMessage.parse(cast(bytes, data))
            except ConnectionClosed as e:
                self._logger.error("WebSocket connection closed: %s", e)
                raise ConnectionError("Connection closed unexpectedly") from e
            except Exception:
                self._logger.exception("Failed to parse inbound frame")
                continue

            if self._resolve_result(server):
                continue
            self._spawn(self._dispatch_frame(cast(bytes, data)))

    def _resolve_result(self, server: PB_ServerMessage) -> bool:
        """Hand a server frame to the request that's waiting on it, if any.

        :param server: The parsed top-level ``ServerMessage``.
        :returns: ``True`` if the frame was a result that matched a pending
            request (and was consumed here), ``False`` if it should fall through
            to normal dispatch.
        """
        result = server.result
        if result is None:
            return False
        future = self._pending.get(result.req_id)
        if future is None or future.done():
            return False
        if result.error is not None:
            future.set_exception(RequestError(result.error.error_code, result.error.error_message))
        else:
            future.set_result(result)
        return True

    async def _dispatch_frame(self, data: bytes) -> None:
        """Decode a non-result frame to its leaf payload and handle it.

        :param data: The raw frame bytes.
        """
        try:
            _, message = unwrap(data)
            await self._handle_msg(message)
        except Exception:
            self._logger.exception("Error dispatching inbound frame")

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        """Schedule ``coro`` as a tracked background task.

        :param coro: The coroutine to run; a strong reference to its task is kept
            until it completes so it isn't garbage collected mid-flight.
        """
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def send_pb(self, message: Any) -> None:
        """Wrap, serialize, and send a protobuf message over the connection.

        This is fire-and-forget: it sends with request id ``0`` and does not wait
        for a reply. Use :meth:`request` when you need the server's response.

        :param message: The protobuf message to send.
        """
        assert self._connection is not None
        await self._connection.send(wrap(message).SerializeToString())

    async def request(self, payload: Any, *, timeout: float = 60.0) -> PB_RpcResult:
        """Send a request and wait for the gateway's matching ``RpcResult``.

        Tags the outbound frame with a unique request id, registers a future for
        it, and resolves once the server replies with a result carrying the same
        id. This requires the read loop (:meth:`_handle_ws`) to be running, which
        it is for the whole lifetime of a connected bot.

        :param payload: The request protobuf to send.
        :param timeout: How long to wait for the response, in seconds.
        :returns: The :class:`~osmium_protos.PB_RpcResult` for this request.
        :raises RequestError: If the gateway answers with an error.
        :raises TimeoutError: If no response arrives within ``timeout``.
        """
        assert self._connection is not None
        self._req_counter += 1
        req_id = self._req_counter
        future: asyncio.Future[PB_RpcResult] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        try:
            await self._connection.send(wrap(payload, id=req_id).SerializeToString())
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(req_id, None)

    def _handle_authorization(self, message: Authorization) -> None:
        """Store the session id/token and the authenticated user from an
        authorization response.

        :param message: The authorization payload from the gateway.
        """
        self.__session_id = message.session_id
        self.__token = message.token
        if message.user:
            self.bot.user = User(message.user, self)

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
