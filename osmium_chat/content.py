"""Rich text formatting for outbound messages.

Formatting nodes — :class:`Bold`, :class:`Italic`, :class:`Underline`,
:class:`Strikethrough`, :class:`Code`, :class:`CodeBlock`, :class:`Spoiler`,
:class:`TextUrl`, and :class:`CustomEmoji <osmium_chat.emoji.CustomEmoji>` — can
be nested freely and embedded inside a :class:`Content` using either the
constructor or f-string interpolation::

    from osmium_chat.content import Bold, Content, Italic, UnicodeEmoji

    # constructor form
    msg = Content("Hello, ", Bold("world"), "!")

    # f-string form — identical result
    msg = Content(f"Hello, {Bold('world')}!")

    # nesting
    msg = Content(f"{Bold(Italic('important'))}")

    # unicode emoji (rendered as plain text)
    msg = Content("Congrats! ", UnicodeEmoji("🎉"))

Each node tree is serialized to a flat text string plus a matching list of
:class:`~osmium_protos.PB_MessageEntity` offset/length spans — the wire
format the Osmium gateway expects.
"""

from osmium_protos import (
    PB_MessageEntity,
    PB_MessageEntityPreEntity,
    PB_MessageEntitySpoilerEntity,
    PB_MessageEntityTextUrlEntity,
)

__all__: tuple[str, ...] = (
    "Bold",
    "Code",
    "CodeBlock",
    "Content",
    "Italic",
    "Spoiler",
    "Strikethrough",
    "TextUrl",
    "Underline",
    "UnicodeEmoji",
    "parse_content",
    "plain_text",
)

class UnicodeEmoji:
    """A standard Unicode emoji for use in :class:`Content`.

    When passed to :class:`Content`, it is treated as plain text — the emoji
    character is embedded in the message string without any formatting entity.

    .. code-block:: python

        Content("Congrats! ", UnicodeEmoji("🎉"))

    :param emoji: The Unicode emoji character(s).
    """

    __slots__ = ("emoji",)

    def __init__(self, emoji: str) -> None:
        self.emoji: str = emoji

    def __str__(self) -> str:
        return self.emoji

    def __format__(self, _: str) -> str:
        return self.emoji

    def __repr__(self) -> str:
        return f"UnicodeEmoji({self.emoji!r})"


# Unicode Private Use Area sentinel used to embed nodes inside f-strings.
# When __format__ is called on a node (e.g. f"{Bold('hi')}"), we register the
# node here and return "{key}". __init__ then expands those back.
_SENT = ""
_pending: "dict[int, _FormattingNode]" = {}
_seq = 0


def _register(node: "_FormattingNode") -> str:
    global _seq
    _seq += 1
    _pending[_seq] = node
    return f"{_SENT}{_seq}{_SENT}"


def _expand(parts: tuple) -> tuple:
    """Replace sentinel strings in *parts* with the registered node objects."""
    out: list = []
    for part in parts:
        if isinstance(part, UnicodeEmoji):
            out.append(part.emoji)
        elif isinstance(part, str) and _SENT in part:
            segments = part.split(_SENT)
            for i, seg in enumerate(segments):
                if i % 2 == 0:
                    if seg:
                        out.append(seg)
                else:
                    try:
                        out.append(_pending.pop(int(seg)))
                    except (ValueError, KeyError):
                        if seg:
                            out.append(f"{_SENT}{seg}{_SENT}")
        else:
            out.append(part)
    return tuple(out)


class _FormattingNode:
    __slots__ = ("_parts",)

    def __init__(self, *parts: "str | _FormattingNode") -> None:
        self._parts = _expand(parts)

    def __format__(self, _: str) -> str:
        return _register(self)

    def __str__(self) -> str:
        return _node_plain(self)

    def _make_entity(self, _start: int, _length: int) -> PB_MessageEntity:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(repr(p) for p in self._parts)})"


class Bold(_FormattingNode):
    """Renders its contents in **bold**."""

    __slots__ = ()

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(start_index=start, length=length, bold=True)


class Italic(_FormattingNode):
    """Renders its contents in *italic*."""

    __slots__ = ()

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(start_index=start, length=length, italic=True)


class Underline(_FormattingNode):
    """Renders its contents with an underline."""

    __slots__ = ()

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(start_index=start, length=length, underline=True)


class Strikethrough(_FormattingNode):
    """Renders its contents with a ~~strikethrough~~."""

    __slots__ = ()

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(start_index=start, length=length, strikethrough=True)


class Code(_FormattingNode):
    """Renders its contents as inline ``code``."""

    __slots__ = ()

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(start_index=start, length=length, code=True)


class CodeBlock(_FormattingNode):
    """Renders its contents as a fenced code block with optional syntax highlighting.

    .. code-block:: python

        CodeBlock("print('hello')", language="python")

    :param parts: The text content of the block.
    :param language: An optional language hint for syntax highlighting (e.g. ``"python"``).
    """

    __slots__ = ("_language",)

    def __init__(self, *parts: "str | _FormattingNode", language: str = "") -> None:
        super().__init__(*parts)
        self._language = language

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(
            start_index=start,
            length=length,
            pre=PB_MessageEntityPreEntity(language=self._language or None),
        )

    def __repr__(self) -> str:
        lang = f", language={self._language!r}" if self._language else ""
        return f"CodeBlock({', '.join(repr(p) for p in self._parts)}{lang})"


class Spoiler(_FormattingNode):
    """Hides its contents behind a spoiler that must be clicked to reveal."""

    __slots__ = ()

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(
            start_index=start,
            length=length,
            spoiler=PB_MessageEntitySpoilerEntity(),
        )


class TextUrl(_FormattingNode):
    """Renders its contents as a hyperlink.

    .. code-block:: python

        TextUrl("osmium.chat", url="https://osmium.chat")

    :param parts: The visible link text.
    :param url: The URL the link points to.
    """

    __slots__ = ("_url",)

    def __init__(self, *parts: "str | _FormattingNode", url: str) -> None:
        super().__init__(*parts)
        self._url = url

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(
            start_index=start,
            length=length,
            text_url=PB_MessageEntityTextUrlEntity(url=self._url),
        )

    def __repr__(self) -> str:
        return f"TextUrl({', '.join(repr(p) for p in self._parts)}, url={self._url!r})"


class Content:
    """A complete message payload: plain text plus formatting entity spans.

    Construct by passing any mix of :class:`str` and formatting nodes::

        content = Content("Price: ", Bold("$9.99"), " — limited time!")

    Or use f-string embedding::

        content = Content(f"Price: {Bold('$9.99')} — limited time!")

    The :attr:`text` property returns the plain-text string; :attr:`entities`
    returns the matching ``PB_MessageEntity`` list ready for the wire.
    """

    __slots__ = ("_parts", "_wire_entities")

    def __init__(self, *parts: "str | _FormattingNode | UnicodeEmoji") -> None:
        self._parts = _expand(parts)
        self._wire_entities: "list[PB_MessageEntity] | None" = None

    @property
    def text(self) -> str:
        return "".join(_node_plain(p) for p in self._parts)

    @property
    def entities(self) -> "list[PB_MessageEntity]":
        if self._wire_entities is not None:
            return self._wire_entities
        result: list[PB_MessageEntity] = []
        _collect_entities(self._parts, 0, result)
        return result

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Content({', '.join(repr(p) for p in self._parts)})"


def _node_plain(node: "str | _FormattingNode") -> str:
    if isinstance(node, str):
        return node
    return "".join(_node_plain(p) for p in node._parts)


def _utf16_len(s: str) -> int:
    """Return the number of UTF-16 code units in *s*.

    Osmium encodes entity offsets in UTF-16 code units. Characters outside the
    Basic Multilingual Plane (e.g. most emoji: 😀, 🎉) are a single Python
    ``str`` character but occupy *two* UTF-16 code units, so ``len()`` alone
    gives wrong offsets for any text containing such characters.
    """
    return len(s.encode("utf-16-le")) >> 1


def _collect_entities(
    parts: tuple,
    offset: int,
    out: "list[PB_MessageEntity]",
) -> int:
    pos = offset
    for part in parts:
        if isinstance(part, str):
            pos += _utf16_len(part)
        else:
            plain_len = _utf16_len(_node_plain(part))
            out.append(part._make_entity(pos, plain_len))
            _collect_entities(part._parts, pos, out)
            pos += plain_len
    return pos


def parse_content(
    text: str,
    entities: "list[PB_MessageEntity] | None" = None,
) -> Content:
    """Build a :class:`Content` from a plain-text string and optional entity list."""
    c = Content(text)
    c._wire_entities = list(entities) if entities else []
    return c


def plain_text(content: Content) -> str:
    """Return the plain text of *content* with all formatting stripped."""
    return content.text
