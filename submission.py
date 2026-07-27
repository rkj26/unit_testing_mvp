"""Canonical parsing for the single final submission in an episode."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


class SubmissionError(ValueError):
    """The assistant transcript does not contain one valid submission."""


@dataclass(frozen=True)
class CanonicalSubmission:
    code: str
    secret_input: str | None


def extract_submission(messages: Iterable[Any]) -> CanonicalSubmission:
    """Return the transcript's sole valid assistant ``submit`` tool call.

    A transcript with no submit, multiple submits, an empty/non-string code, or
    a non-string ``secret_input`` is ambiguous and therefore rejected. Keeping
    this rule in one place prevents monitors, metrics, and scorers from silently
    evaluating different candidate submissions from the same episode.
    """

    submit_calls: list[Any] = []
    for message in messages:
        if getattr(message, "role", None) != "assistant":
            continue
        tool_calls = getattr(message, "tool_calls", None) or ()
        try:
            submit_calls.extend(
                tool_call
                for tool_call in tool_calls
                if getattr(tool_call, "function", None) == "submit"
            )
        except TypeError as error:
            raise SubmissionError("assistant tool_calls must be an iterable") from error

    if len(submit_calls) != 1:
        raise SubmissionError(
            "expected exactly one assistant submit tool call, "
            f"found {len(submit_calls)}"
        )

    arguments = getattr(submit_calls[0], "arguments", None)
    if not isinstance(arguments, Mapping):
        raise SubmissionError("submit arguments must be a mapping")

    code = arguments.get("code")
    if not isinstance(code, str) or not code.strip():
        raise SubmissionError("submit code must be a non-empty string")

    secret_input = arguments.get("secret_input")
    if secret_input is not None and not isinstance(secret_input, str):
        raise SubmissionError("submit secret_input must be a string or null")

    return CanonicalSubmission(code=code, secret_input=secret_input)


def require_matching_submission(
    transcript: CanonicalSubmission,
    *,
    stored_code: str,
    stored_secret_input: str | None,
) -> None:
    """Reject a submit-tool store value that differs from the transcript."""

    if transcript.code != stored_code or transcript.secret_input != stored_secret_input:
        raise SubmissionError(
            "submission transcript disagrees with the arguments executed by the "
            "submit tool"
        )
