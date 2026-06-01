import inspect
from collections.abc import Awaitable, Callable
from types import UnionType
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin, get_type_hints

from osmium_chat.errors import BadArgument, MissingRequiredArgument, TooManyArguments

if TYPE_CHECKING:
    from osmium_chat.context import Context


__all__: tuple[str, ...] = (
    "Command",
    "Parameter",
    "StringView",
    "CommandCallback",
)


CommandCallback = Callable[..., Awaitable[None]]

_TRUE = frozenset({"true", "t", "yes", "y", "1", "on", "enable", "enabled"})
_FALSE = frozenset({"false", "f", "no", "n", "0", "off", "disable", "disabled"})


def _convert_bool(value: str) -> bool:
    """Convert a token to a bool, accepting common truthy/falsey spellings."""
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError(value)


# Maps an annotated argument type to the callable that parses a raw token into it.
# Extend this to teach the command parser about new argument types.
CONVERTERS: dict[type, Callable[[str], Any]] = {
    str: str,
    int: int,
    float: float,
    bool: _convert_bool,
}


class StringView:
    """A cursor over a command's argument string.

    Hands out whitespace-delimited words one at a time (respecting single and
    double quotes so multi-word arguments can be passed), or the entire
    remaining string for "consume rest" parameters.
    """

    __slots__: tuple[str, ...] = (
        "text",
        "index",
    )

    _QUOTES: frozenset[str] = frozenset({'"', "'"})

    def __init__(self, text: str) -> None:
        """:param text: The raw argument string to read from."""
        self.text = text
        self.index = 0

    @property
    def eof(self) -> bool:
        """Whether the cursor has reached the end of the string."""
        return self.index >= len(self.text)

    def skip_whitespace(self) -> None:
        """Advance the cursor past any run of whitespace."""
        while not self.eof and self.text[self.index].isspace():
            self.index += 1

    def rest(self) -> str:
        """Consume and return the remaining string, stripped of surrounding space."""
        self.skip_whitespace()
        remaining = self.text[self.index:]
        self.index = len(self.text)
        return remaining.strip()

    def get_word(self) -> str | None:
        """Consume and return the next word, or ``None`` if none remain.

        A word is a run of non-whitespace characters, unless it is wrapped in
        matching quotes, in which case everything up to the closing quote is
        returned as a single word (with backslash escaping inside the quotes).
        """
        self.skip_whitespace()
        if self.eof:
            return None

        char = self.text[self.index]
        if char in self._QUOTES:
            return self._read_quoted(char)

        start = self.index
        while not self.eof and not self.text[self.index].isspace():
            self.index += 1
        return self.text[start:self.index]

    def _read_quoted(self, quote: str) -> str:
        """Read a quoted word starting at the opening ``quote`` character."""
        self.index += 1  # skip opening quote
        chars: list[str] = []
        while not self.eof:
            char = self.text[self.index]
            if char == "\\" and self.index + 1 < len(self.text):
                self.index += 1
                chars.append(self.text[self.index])
            elif char == quote:
                self.index += 1  # skip closing quote
                return "".join(chars)
            else:
                chars.append(char)
            self.index += 1
        # Unterminated quote: treat the rest as literal content.
        return "".join(chars)


class Parameter:
    """A single command argument, resolved from the callback's signature."""

    __slots__: tuple[str, ...] = (
        "name",
        "annotation",
        "kind",
        "default",
        "optional",
    )

    def __init__(
        self,
        name: str,
        annotation: Any,
        kind: inspect._ParameterKind,
        default: Any,
    ) -> None:
        """:param name: The parameter name.
        :param annotation: The resolved leaf type to convert tokens to.
        :param kind: The parameter kind (positional, keyword-only, var-positional).
        :param default: The default value, or :data:`inspect.Parameter.empty`.
        """
        self.name = name
        self.annotation = annotation
        self.kind = kind
        self.default = default
        # A parameter is optional if it has a default or accepts ``None``.
        self.optional = default is not inspect.Parameter.empty

    @property
    def required(self) -> bool:
        """Whether a value must be supplied for this parameter."""
        return not self.optional

    def convert(self, value: str) -> Any:
        """Convert a raw token to this parameter's annotated type.

        :param value: The raw token from the message.
        :raises BadArgument: If the token cannot be converted.
        """
        annotation = self.annotation
        if annotation is inspect.Parameter.empty or annotation is str:
            return value
        converter = CONVERTERS.get(annotation)
        try:
            if converter is not None:
                return converter(value)
            return annotation(value)
        except (ValueError, TypeError) as exc:
            raise BadArgument(self.name, value, annotation) from exc


def _resolve_annotation(annotation: Any) -> tuple[Any, bool]:
    """Reduce an annotation to a concrete leaf type and an optional flag.

    Unwraps ``Optional[T]`` / ``T | None`` to ``(T, True)``; for a plain ``T``
    returns ``(T, False)``. For unions of several non-``None`` types the first
    member is used.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        accepts_none = len(args) != len(get_args(annotation))
        leaf = args[0] if args else str
        return leaf, accepts_none
    return annotation, False


class Command:
    """A registered command: a name, optional aliases, and a parsed callback.

    The callback's signature drives argument parsing. The first parameter always
    receives the :class:`~osmium_chat.context.Context`; each parameter after it
    becomes a command argument, read from the message text following the command
    name and converted according to the rules below.

    **Automatic type conversion**

    Each argument is converted to its annotated type before the callback runs.
    The built-in converters are:

    - ``str`` (or an un-annotated parameter) — the raw token, unchanged.
    - ``int`` — parsed with :class:`int`.
    - ``float`` — parsed with :class:`float`.
    - ``bool`` — accepts ``true``/``false``, ``yes``/``no``, ``y``/``n``,
      ``on``/``off``, ``1``/``0``, ``enable``/``disable`` (case-insensitive).

    Any other annotation is called with the raw token (``annotation(token)``),
    so a type whose constructor takes a single string just works. Conversion
    failures raise :class:`~osmium_chat.errors.BadArgument`. New types can be
    registered by adding to :data:`CONVERTERS`.

    **Optional arguments**

    A parameter with a default value is optional; if the invoker omits it, the
    default is used. Otherwise a missing argument raises
    :class:`~osmium_chat.errors.MissingRequiredArgument`. An annotation of
    ``T | None`` (i.e. ``Optional[T]``) is converted as ``T``.

    **Quoting** (``"..."``)

    Arguments are split on whitespace, so each parameter normally receives a
    single word. To pass a value that contains spaces as one argument, wrap it
    in single or double quotes; the surrounding quotes are stripped and a
    backslash escapes the next character inside them::

        @bot.command("echo")
        async def echo(ctx: Context, word: str) -> None:
            await ctx.channel.send(word)

        # !echo "hello world"   ->   word == "hello world"

    **Consume-rest** (``*``) **and variadic** (``*args``)

    A keyword-only parameter — one declared after a bare ``*`` — consumes the
    entire remaining message as a single, unsplit string (quotes are kept
    verbatim here). This is the idiomatic way to accept free-form text::

        @bot.command("say")
        async def say(ctx: Context, *, words: str) -> None:
            await ctx.channel.send(words)

        # !say hello there world   ->   words == "hello there world"

    A variadic ``*args`` parameter instead collects every remaining token,
    converting each one to the annotated element type::

        @bot.command("sum")
        async def sum_(ctx: Context, *numbers: int) -> None:
            await ctx.channel.send(str(sum(numbers)))

        # !sum 1 2 3   ->   numbers == (1, 2, 3)

    Any leftover text after all parameters are filled raises
    :class:`~osmium_chat.errors.TooManyArguments`.
    """

    __slots__: tuple[str, ...] = (
        "name",
        "callback",
        "aliases",
        "params",
    )

    def __init__(
        self,
        callback: CommandCallback,
        *,
        name: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> None:
        """:param callback: The coroutine invoked when the command runs.
        :param name: The command name; defaults to the callback's name.
        :param aliases: Additional names the command also responds to.
        """
        if not inspect.iscoroutinefunction(callback):
            raise TypeError("Command callback must be a coroutine function")
        self.callback = callback
        self.name = name or callback.__name__
        self.aliases = aliases
        self.params = self._build_params(callback)

    @staticmethod
    def _build_params(callback: CommandCallback) -> list[Parameter]:
        """Parse the callback signature into argument parameters (skipping ctx)."""
        signature = inspect.signature(callback)
        try:
            hints = get_type_hints(callback)
        except Exception:
            # If annotations can't be resolved (e.g. a missing import) fall back
            # to whatever raw annotations the signature carries.
            hints = {}

        params: list[Parameter] = []
        for index, param in enumerate(signature.parameters.values()):
            if index == 0:
                continue  # the context parameter
            if param.kind in (
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue  # **kwargs is not fed from the message
            raw = hints.get(param.name, param.annotation)
            annotation, _ = _resolve_annotation(raw)
            params.append(Parameter(param.name, annotation, param.kind, param.default))
        return params

    def parse_arguments(self, view: StringView) -> tuple[list[Any], dict[str, Any]]:
        """Convert the argument string into call arguments for the callback.

        Returns the positional ``args`` and keyword-only ``kwargs`` to pass to
        the callback alongside the context.

        :param view: A view over the message text following the command name.
        :raises MissingRequiredArgument: If a required argument is absent.
        :raises BadArgument: If an argument fails type conversion.
        :raises TooManyArguments: If unconsumed tokens remain at the end.
        """
        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        for param in self.params:
            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                # ``*args``: greedily convert every remaining token.
                while True:
                    word = view.get_word()
                    if word is None:
                        break
                    args.append(param.convert(word))
                return args, kwargs

            if param.kind is inspect.Parameter.KEYWORD_ONLY:
                # Keyword-only parameter: consume the rest of the message. It is
                # passed by name since the callback won't accept it positionally.
                remaining = view.rest()
                if not remaining:
                    if param.required:
                        raise MissingRequiredArgument(param.name)
                    kwargs[param.name] = param.default
                else:
                    kwargs[param.name] = param.convert(remaining)
                return args, kwargs

            word = view.get_word()
            if word is None:
                if param.required:
                    raise MissingRequiredArgument(param.name)
                args.append(param.default)
            else:
                args.append(param.convert(word))

        leftover = view.rest()
        if leftover:
            raise TooManyArguments(leftover)
        return args, kwargs

    async def invoke(self, ctx: "Context", view: StringView) -> None:
        """Parse arguments from ``view`` and run the command callback.

        :param ctx: The invocation context, passed as the first argument.
        :param view: A view over the message text following the command name.
        """
        args, kwargs = self.parse_arguments(view)
        ctx.command = self
        ctx.args = args
        await self.callback(ctx, *args, **kwargs)
