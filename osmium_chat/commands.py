"""Command parsing and argument conversion.

Commands are registered on a :class:`~osmium_chat.bot.Bot` with the
``@bot.command`` decorator.  The first parameter of every callback always
receives the :class:`~osmium_chat.context.Context`; each subsequent parameter
is parsed from the message text following the command name.

**Basic types**

The built-in converters handle the most common cases:

- ``str`` — raw token, unchanged.
- ``int`` / ``float`` — numeric conversion.
- ``bool`` — accepts ``true``/``false``, ``yes``/``no``, ``on``/``off``,
  ``y``/``n``, ``1``/``0``, ``enable``/``disable`` (case-insensitive).
- :class:`~osmium_chat.content.UnicodeEmoji` — wraps the raw token.

Any other annotation is called with the raw token (``annotation(token)``), so a
type whose constructor accepts a single string just works.  Custom types can be
registered by inserting into :data:`CONVERTERS`.

**Mention types**

These types are resolved from message entities and community data:

- :class:`~osmium_chat.user.user.User` — from a ``user_mention`` entity or
  ``@username``/``@<id>`` text.
- :class:`~osmium_chat.role.Role` — from ``&<name-or-id>`` text.
- :class:`~osmium_chat.channel.Channel` — from ``#<name-or-id>`` text.
- :class:`~osmium_chat.category.Category` — from ``#<name-or-id>`` text
  (resolved against categories).
- :class:`~osmium_chat.emoji.CustomEmoji` — from a ``custom_emoji`` entity or
  ``:name:`` text.

**Multi-type (union) parameters**

Annotating a parameter as ``A | B`` (or ``Union[A, B]``) tells the parser to
try each candidate type in declaration order, accepting the first one that
succeeds::

    @bot.command("target")
    async def target(ctx: Context, who: User | Channel) -> None:
        ...

    # !target @alice   → who is a User
    # !target #general → who is a Channel

When a message entity at the argument's position *unambiguously* identifies a
type (e.g. a ``custom_emoji`` entity for :class:`~osmium_chat.emoji.CustomEmoji`),
the parser skips the fallback candidates and raises
:class:`~osmium_chat.errors.BadArgument` immediately if conversion fails.

``Optional[T]`` / ``T | None`` is treated as the type ``T`` with an implicit
``None`` default — the ``None`` arm is never tried as a conversion candidate.

**Quoting**

Arguments are split on whitespace.  To pass a value containing spaces as a
single argument, wrap it in single or double quotes.  A backslash escapes the
next character inside quotes::

    # !echo "hello world"   →   word == "hello world"

**Consume-rest and variadic parameters**

A keyword-only parameter (declared after a bare ``*``) consumes the entire
remaining message as one unsplit string::

    @bot.command("say")
    async def say(ctx: Context, *, words: str) -> None:
        await ctx.channel.send(words)

    # !say hello there world   →   words == "hello there world"

A variadic ``*args`` parameter collects every remaining token::

    @bot.command("sum")
    async def sum_(ctx: Context, *numbers: int) -> None:
        await ctx.channel.send(str(sum(numbers)))

    # !sum 1 2 3   →   numbers == (1, 2, 3)
"""

import inspect
import re
from collections.abc import Awaitable, Callable
from enum import Enum
from types import UnionType
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin, get_type_hints

from osmium_chat.category import Category
from osmium_chat.channel import Channel
from osmium_chat.content import UnicodeEmoji, _utf16_len
from osmium_chat.emoji import CustomEmoji
from osmium_chat.errors import BadArgument, MissingRequiredArgument, TooManyArguments
from osmium_chat.role import Role
from osmium_chat.user.user import User

if TYPE_CHECKING:
    from osmium_chat.context import Context


__all__: tuple[str, ...] = (
    "Command",
    "CommandRestriction",
    "CONTEXT_CONVERTERS",
    "CONVERTERS",
    "Parameter",
    "StringView",
    "CommandCallback",
)

_ROLE_MENTION_RE = re.compile(r"^&(.+)$")
_CHANNEL_MENTION_RE = re.compile(r"^#(.+)$")
_CUSTOM_EMOJI_RE = re.compile(r"^:([^:]+):$")


class CommandRestriction(Enum):
    """Where a command is allowed to be invoked."""
    NONE = "none"
    DM_ONLY = "dm_only"
    COMMUNITY_ONLY = "community_only"


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
    UnicodeEmoji: UnicodeEmoji,
}


async def _resolve_user(ctx: "Context", value: str, *_: Any) -> User:
    # Strip a leading @ to get either a numeric id or a username.
    from osmium_protos import PB_LookupUsername, PB_User
    raw = value.lstrip("@")
    if raw.isdigit():
        user_id = int(raw)
        if ctx.author is not None and ctx.author.id == user_id:
            return ctx.author
        return User(PB_User(id=user_id), ctx.bot._client)
    # Username mention — look up via the gateway.
    if ctx.author is not None and ctx.author.username == raw:
        return ctx.author
    result = await ctx.bot._client.request(PB_LookupUsername(username=raw))
    if result.user_details is None or result.user_details.user is None:
        raise ValueError(value)
    return User(result.user_details.user, ctx.bot._client)


async def _resolve_role(ctx: "Context", value: str, *_: Any) -> Role:
    m = _ROLE_MENTION_RE.match(value)
    if not m:
        raise ValueError(value)
    key = m.group(1)
    if ctx.community is None:
        raise ValueError(value)
    roles = ctx.community.roles if ctx.community.roles else await ctx.community.fetch_roles()
    if key.isdigit():
        role_id = int(key)
        role = next((r for r in roles if r.id == role_id), None)
        if role is None:
            roles = await ctx.community.fetch_roles()
            role = next((r for r in roles if r.id == role_id), None)
    else:
        role = next((r for r in roles if r.name == key), None)
        if role is None:
            roles = await ctx.community.fetch_roles()
            role = next((r for r in roles if r.name == key), None)
    if role is None:
        raise ValueError(value)
    return role


async def _resolve_channel(ctx: "Context", value: str, *_: Any) -> Channel:
    m = _CHANNEL_MENTION_RE.match(value)
    if not m:
        raise ValueError(value)
    key = m.group(1)
    if ctx.community is None:
        raise ValueError(value)
    channels = ctx.community.channels if ctx.community.channels else await ctx.community.fetch_channels()
    if key.isdigit():
        channel_id = int(key)
        channel = next((c for c in channels if c.id == channel_id), None)
        if channel is None:
            channels = await ctx.community.fetch_channels()
            channel = next((c for c in channels if c.id == channel_id), None)
    else:
        channel = next((c for c in channels if c.name == key), None)
        if channel is None:
            channels = await ctx.community.fetch_channels()
            channel = next((c for c in channels if c.name == key), None)
    if channel is None:
        raise ValueError(value)
    return channel


async def _resolve_category(ctx: "Context", value: str, *_: Any) -> Category:
    m = _CHANNEL_MENTION_RE.match(value)
    if not m:
        raise ValueError(value)
    key = m.group(1)
    if ctx.community is None:
        raise ValueError(value)
    if not ctx.community.categories:
        await ctx.community.fetch_channels()
    if key.isdigit():
        category_id = int(key)
        category = next((c for c in ctx.community.categories if c.id == category_id), None)
        if category is None:
            await ctx.community.fetch_channels()
            category = next((c for c in ctx.community.categories if c.id == category_id), None)
    else:
        category = next((c for c in ctx.community.categories if c.name == key), None)
        if category is None:
            await ctx.community.fetch_channels()
            category = next((c for c in ctx.community.categories if c.name == key), None)
    if category is None:
        raise ValueError(value)
    return category


async def _resolve_custom_emoji(ctx: "Context", value: str, entity: Any = None) -> CustomEmoji:
    if ctx.community is None:
        raise ValueError(value)
    # Entity path: emoji_id is authoritative — no name lookup needed.
    if entity is not None and entity.custom_emoji is not None:
        emoji_id = entity.custom_emoji.emoji_id
        emojis = ctx.community.custom_emojis if ctx.community.custom_emojis else await ctx.community.fetch_custom_emojis()
        emoji = next((e for e in emojis if e.id == emoji_id), None)
        if emoji is None:
            emojis = await ctx.community.fetch_custom_emojis()
            emoji = next((e for e in emojis if e.id == emoji_id), None)
        if emoji is not None:
            return emoji
        # ID is known from the entity even if not in the fetched list — return a
        # minimal stub (only .id is needed for reactions and sends).
        return CustomEmoji(
            emoji_id=emoji_id,
            name=value,
            community_id=ctx.community.id,
            pack_id=0,
            client=ctx.bot._client,
        )
    # Text path: :name: form.
    m = _CUSTOM_EMOJI_RE.match(value)
    if not m:
        raise ValueError(value)
    name = m.group(1)
    emojis = ctx.community.custom_emojis if ctx.community.custom_emojis else await ctx.community.fetch_custom_emojis()
    emoji = next((e for e in emojis if e.name == name), None)
    if emoji is None:
        emojis = await ctx.community.fetch_custom_emojis()
        emoji = next((e for e in emojis if e.name == name), None)
    if emoji is None:
        raise ValueError(value)
    return emoji


def _entity_matches(entity: Any, annotation: type) -> bool:
    """Return True if *entity* unambiguously identifies *annotation*'s type.

    Used by :meth:`Parameter.resolve` to decide whether a failed conversion
    should fall through to the next candidate in a union or raise immediately.
    """
    if entity is None:
        return False
    if annotation is CustomEmoji:
        return entity.custom_emoji is not None
    if annotation is User:
        return entity.user_mention is not None or entity.username is not None
    return False


# Maps an annotated argument type to an async callable that parses a raw token
# using the invocation context (e.g. to look up community members or channels).
# Each converter receives (ctx, value, entity) where entity is the PB_MessageEntity
# at the argument's position in the message, or None if there is no entity there.
CONTEXT_CONVERTERS: dict[type, Callable[..., Awaitable[Any]]] = {
    User: _resolve_user,
    Role: _resolve_role,
    Channel: _resolve_channel,
    Category: _resolve_category,
    CustomEmoji: _resolve_custom_emoji,
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
        "word_start",
    )

    _QUOTES: frozenset[str] = frozenset({'"', "'"})

    def __init__(self, text: str) -> None:
        """:param text: The raw argument string to read from."""
        self.text = text
        self.index = 0
        self.word_start = 0

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

        :attr:`word_start` is updated to the position in :attr:`text` where
        the returned word began, so callers can correlate it with message entities.
        """
        self.skip_whitespace()
        if self.eof:
            return None

        self.word_start = self.index
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

        Tries each candidate type in declaration order, returning the first
        successful result.

        :param value: The raw token from the message.
        :raises BadArgument: If no candidate type can convert the token.
        """
        for ann in self.annotation:
            if ann is inspect.Parameter.empty or ann is str:
                return value
            converter = CONVERTERS.get(ann)
            try:
                if converter is not None:
                    return converter(value)
                if ann not in CONTEXT_CONVERTERS:
                    return ann(value)
            except (ValueError, TypeError):
                continue
        raise BadArgument(self.name, value, self.annotation[0])

    async def resolve(self, ctx: "Context", value: str, *, entity: Any = None) -> Any:
        """Convert a raw token, using the invocation context for mention types.

        Tries each candidate type in declaration order, returning the first
        successful result. Falls back to :meth:`convert` for types that don't
        need context.

        :param ctx: The invocation context (used to look up mentions).
        :param value: The raw token from the message.
        :param entity: The :class:`~osmium_protos.PB_MessageEntity` at this
            argument's position in the message, or ``None`` if absent.
        :raises BadArgument: If no candidate type can convert the token.
        """
        for ann in self.annotation:
            context_converter = CONTEXT_CONVERTERS.get(ann)
            if context_converter is not None:
                try:
                    return await context_converter(ctx, value, entity)
                except (ValueError, TypeError) as exc:
                    # If the message entity at this position unambiguously
                    # identifies the type (e.g. a custom_emoji entity for
                    # CustomEmoji), don't silently fall through — the conversion
                    # failed for a definitive reason.
                    if _entity_matches(entity, ann):
                        raise BadArgument(self.name, value, ann) from exc
                    continue
            if ann is inspect.Parameter.empty or ann is str:
                return value
            converter = CONVERTERS.get(ann)
            try:
                if converter is not None:
                    return converter(value)
                if ann not in CONTEXT_CONVERTERS:
                    return ann(value)
            except (ValueError, TypeError):
                continue
        raise BadArgument(self.name, value, self.annotation[0])


def _resolve_annotation(annotation: Any) -> tuple[Any, bool]:
    """Reduce an annotation to a concrete leaf type and an optional flag.

    Unwraps ``Optional[T]`` / ``T | None`` to ``((T,), True)``. For genuine
    multi-type unions like ``A | B`` all non-``None`` members are preserved so
    the parser can try each in order.  For a plain ``T`` returns ``((T,), False)``.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        accepts_none = len(args) != len(get_args(annotation))
        return tuple(args) if args else (str,), accepts_none
    return (annotation,), False


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
    - ``UnicodeEmoji`` — wraps the raw token as a :class:`~osmium_chat.content.UnicodeEmoji`.

    **Mention types** (resolved via message entities and community lookups)

    - ``User`` — decoded from a ``user_mention`` entity; the text at that span
      must be the user's numeric id (with or without a leading ``@``).
    - ``Role`` — decoded from ``&<name-or-id>`` text.
    - ``Channel`` — decoded from ``#<name-or-id>`` text.
    - ``Category`` — decoded from ``#<name-or-id>`` text (resolved in categories).
    - ``CustomEmoji`` — decoded from a ``custom_emoji`` entity (by ``emoji_id``)
      or from ``:name:`` text as a fallback.

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
        "restriction",
    )

    def __init__(
        self,
        callback: CommandCallback,
        *,
        name: str | None = None,
        aliases: tuple[str, ...] = (),
        restriction: CommandRestriction = CommandRestriction.NONE,
    ) -> None:
        """:param callback: The coroutine invoked when the command runs.
        :param name: The command name; defaults to the callback's name.
        :param aliases: Additional names the command also responds to.
        :param restriction: Where the command may be invoked.
        """
        if not inspect.iscoroutinefunction(callback):
            raise TypeError("Command callback must be a coroutine function")
        self.callback = callback
        self.name = name or callback.__name__
        self.aliases = aliases
        self.restriction = restriction
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

    async def parse_arguments(
        self,
        ctx: "Context",
        view: StringView,
        entity_by_pos: "dict[int, Any]",
        prefix_utf16: int,
    ) -> tuple[list[Any], dict[str, Any]]:
        """Convert the argument string into call arguments for the callback.

        Returns the positional ``args`` and keyword-only ``kwargs`` to pass to
        the callback alongside the context.

        :param ctx: The invocation context, used to resolve mention-type arguments.
        :param view: A view over the message text following the command name.
        :param entity_by_pos: Mapping of UTF-16 start position → message entity,
            built from the message's entity list.
        :param prefix_utf16: The UTF-16 length of the command prefix, used to
            translate view-relative positions back to full-content positions.
        :raises MissingRequiredArgument: If a required argument is absent.
        :raises BadArgument: If an argument fails type conversion.
        :raises TooManyArguments: If unconsumed tokens remain at the end.
        """
        def _entity_at(word_start: int) -> Any:
            utf16_pos = prefix_utf16 + _utf16_len(view.text[:word_start])
            return entity_by_pos.get(utf16_pos)

        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        for param in self.params:
            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                # ``*args``: greedily convert every remaining token.
                while True:
                    word = view.get_word()
                    if word is None:
                        break
                    args.append(await param.resolve(ctx, word, entity=_entity_at(view.word_start)))
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
                    kwargs[param.name] = await param.resolve(ctx, remaining, entity=None)
                return args, kwargs

            word = view.get_word()
            if word is None:
                if param.required:
                    raise MissingRequiredArgument(param.name)
                args.append(param.default)
            else:
                args.append(await param.resolve(ctx, word, entity=_entity_at(view.word_start)))

        leftover = view.rest()
        if leftover:
            raise TooManyArguments(leftover)
        return args, kwargs

    async def invoke(self, ctx: "Context", view: StringView) -> None:
        """Parse arguments from ``view`` and run the command callback.

        :param ctx: The invocation context, passed as the first argument.
        :param view: A view over the message text following the command name.
        """
        prefix_utf16 = _utf16_len(ctx.prefix)
        entity_by_pos: dict[int, Any] = {
            e.start_index: e for e in ctx.message.content_raw.entities
        }
        args, kwargs = await self.parse_arguments(ctx, view, entity_by_pos, prefix_utf16)
        ctx.command = self
        ctx.args = args
        await self.callback(ctx, *args, **kwargs)
