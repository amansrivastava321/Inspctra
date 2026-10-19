"""Helpers for building HTTP response headers from user-influenced values."""

from __future__ import annotations

import re
from urllib.parse import quote

# Control characters (incl. CR/LF), the quote that delimits the value, and path separators.
_UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f"\\/]')


def attachment_disposition(filename: str | None, fallback: str = "download") -> str:
    """``Content-Disposition`` value for a download named ``filename``.

    Evidence, report and baseline names come from users and uploads. Echoing them raw lets
    CR/LF make the header invalid (the response then fails with a server error), lets a
    quote break out of the value, and passes path-like names to the browser. This keeps the
    basename only, replaces unsafe characters, and adds an RFC 5987 ``filename*`` for
    non-ASCII names.
    """
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = _UNSAFE_FILENAME_CHARS.sub("_", name).strip(" .") or fallback
    ascii_name = name.encode("ascii", "replace").decode("ascii").replace("?", "_")
    value = f'attachment; filename="{ascii_name}"'
    if ascii_name != name:
        value += f"; filename*=UTF-8''{quote(name, safe='')}"
    return value
