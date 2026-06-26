from __future__ import annotations


class _State:
    human: bool = False   # force rich/human output even when piped
    pretty: bool = False  # use indented JSON (default: compact)


state = _State()
