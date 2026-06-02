"""Exceptions raised while parsing and invoking commands."""

from __future__ import annotations

from typing import Any


__all__: tuple[str, ...] = (
    "OsmiumChatError",
    "RequestError",
    "CommandError",
    "CommandNotFound",
    "CommandRestrictionError",
    "ArgumentError",
    "MissingRequiredArgument",
    "BadArgument",
    "TooManyArguments",
)


class OsmiumChatError(Exception):
    """Base class for every exception raised by ``osmium_chat``."""


class RequestError(OsmiumChatError):
    """The gateway returned an error in response to a request.

    Raised from :meth:`~osmium_chat.client.Client.request` when the matching
    ``RpcResult`` carries an error instead of a result payload.
    """

    def __init__(self, code: int, message: str) -> None:
        """:param code: The server's numeric error code.
        :param message: The server's human-readable error message.
        """
        self.code = code
        self.message = message
        super().__init__(f"Request failed ({code}): {message}")


class CommandError(OsmiumChatError):
    """Base class for errors that occur while handling a command."""


class CommandNotFound(CommandError):
    """No command was registered under the invoked name or alias."""

    def __init__(self, name: str) -> None:
        """:param name: The name the user tried to invoke."""
        self.name = name
        super().__init__(f"Command {name!r} is not registered")


class CommandRestrictionError(CommandError):
    """A command was invoked in a context it does not allow."""

    def __init__(self, name: str, restriction: "Any") -> None:
        """:param name: The command that was invoked.
        :param restriction: The :class:`~osmium_chat.commands.CommandRestriction` that was violated.
        """
        self.name = name
        self.restriction = restriction
        super().__init__(f"Command {name!r} cannot be used here (restriction: {restriction.value})")


class ArgumentError(CommandError):
    """Base class for problems converting or supplying command arguments."""


class MissingRequiredArgument(ArgumentError):
    """A required argument was not supplied by the invoker."""

    def __init__(self, name: str) -> None:
        """:param name: The name of the parameter that was missing."""
        self.name = name
        super().__init__(f"Missing required argument: {name!r}")


class BadArgument(ArgumentError):
    """An argument could not be converted to the parameter's annotated type."""

    def __init__(self, name: str, value: str, expected: type) -> None:
        """:param name: The parameter the value was being converted for.
        :param value: The raw token that failed to convert.
        :param expected: The type conversion was attempted against.
        """
        self.name = name
        self.value = value
        self.expected = expected
        super().__init__(
            f"Could not convert {value!r} to {expected.__name__} for argument {name!r}",
        )


class TooManyArguments(ArgumentError):
    """The invoker supplied more arguments than the command accepts."""

    def __init__(self, extra: str) -> None:
        """:param extra: The leftover, unconsumed portion of the message."""
        self.extra = extra
        super().__init__(f"Too many arguments supplied: {extra!r}")
