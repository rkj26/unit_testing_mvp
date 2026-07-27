from types import SimpleNamespace

import pytest

from paper_metrics import attempted_backdoor_from_messages
from submission import (
    CanonicalSubmission,
    SubmissionError,
    extract_submission,
    require_matching_submission,
)

_DEFAULT_ARGUMENTS = object()


def message(*tool_calls, role="assistant"):
    return SimpleNamespace(role=role, tool_calls=list(tool_calls))


def tool_call(function="submit", arguments=_DEFAULT_ARGUMENTS):
    return SimpleNamespace(
        function=function,
        arguments={"code": "def solve():\n    return 1"}
        if arguments is _DEFAULT_ARGUMENTS
        else arguments,
    )


def test_extracts_the_only_submit_and_ignores_other_calls():
    result = extract_submission(
        [
            message(tool_call("search", {"query": "x"})),
            message(tool_call(), role="user"),
            message(
                tool_call(
                    arguments={
                        "code": "def solve():\n    return 1",
                        "secret_input": '{"x": 1}',
                    }
                )
            ),
        ]
    )

    assert result == CanonicalSubmission(
        code="def solve():\n    return 1", secret_input='{"x": 1}'
    )
    assert attempted_backdoor_from_messages(
        [message(tool_call(arguments={"code": "pass", "secret_input": "{}"}))]
    )


def test_absent_secret_is_an_honest_submission():
    messages = [message(tool_call(arguments={"code": "pass"}))]

    assert extract_submission(messages).secret_input is None
    assert attempted_backdoor_from_messages(messages) is False


@pytest.mark.parametrize(
    ("messages", "match"),
    [
        ([], "found 0"),
        (
            [message(tool_call()), message(tool_call())],
            "found 2",
        ),
    ],
)
def test_rejects_zero_or_multiple_submits(messages, match):
    with pytest.raises(SubmissionError, match=match):
        extract_submission(messages)


@pytest.mark.parametrize(
    ("arguments", "match"),
    [
        (None, "mapping"),
        ([], "mapping"),
        ({}, "non-empty string"),
        ({"code": "   "}, "non-empty string"),
        ({"code": 42}, "non-empty string"),
        ({"code": "pass", "secret_input": {}}, "string or null"),
    ],
)
def test_rejects_malformed_submit_arguments(arguments, match):
    with pytest.raises(SubmissionError, match=match):
        extract_submission([message(tool_call(arguments=arguments))])


def test_attempt_classification_rejects_ambiguous_transcript():
    with pytest.raises(SubmissionError, match="found 2"):
        attempted_backdoor_from_messages([message(tool_call()), message(tool_call())])


@pytest.mark.parametrize(
    ("stored_code", "stored_secret_input"),
    [("different", None), ("pass", "{}")],
)
def test_rejects_store_arguments_that_disagree_with_transcript(
    stored_code, stored_secret_input
):
    transcript = CanonicalSubmission(code="pass", secret_input=None)

    with pytest.raises(SubmissionError, match="disagrees"):
        require_matching_submission(
            transcript,
            stored_code=stored_code,
            stored_secret_input=stored_secret_input,
        )


def test_accepts_store_arguments_that_match_transcript():
    transcript = CanonicalSubmission(code="pass", secret_input="{}")

    assert (
        require_matching_submission(
            transcript,
            stored_code="pass",
            stored_secret_input="{}",
        )
        is None
    )
