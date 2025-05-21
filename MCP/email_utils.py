"""Utilities for processing email text."""

from __future__ import annotations

import re
from collections import defaultdict


def condense_repetitive_messages(text: str) -> str:
    """Collapse messages with the same subject line.

    Each message is expected to be separated by blank lines and contain a
    ``Subject:`` header. When multiple messages share the same subject,
    only the first is kept and annotated with ``(xN)`` to indicate the
    number of repetitions.
    """
    messages = [m.strip() for m in text.strip().split("\n\n") if m.strip()]
    groups: dict[str, list[str]] = defaultdict(list)
    for msg in messages:
        match = re.search(r"^Subject:\s*(.*)$", msg, flags=re.MULTILINE)
        subject = match.group(1).strip() if match else msg[:20]
        groups[subject].append(msg)

    condensed: list[str] = []
    for subject, msgs in groups.items():
        msg = msgs[0]
        if len(msgs) > 1:
            msg = re.sub(
                r"^Subject:\s*.*$",
                f"Subject: {subject} (x{len(msgs)})",
                msg,
                flags=re.MULTILINE,
            )
        condensed.append(msg)

    return "\n\n".join(condensed)
