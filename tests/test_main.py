import pytest

from main import calculate_metrics, generate_team_insight, parse_llm_response
from schemas import InvalidEvent, InvalidLLMResponse, LLMClient

VALID_RESPONSE = '{"summary": "Healthy delivery flow.", "recommendations": ["Monitor cycle time."]}'

EVENTS = [
    {"event_type": "pr_opened", "event_id": "pr-1", "timestamp": "2026-01-01T09:00:00Z"},
    {"event_type": "pr_merged", "event_id": "pr-1", "timestamp": "2026-01-02T09:00:00Z"},
    {"event_type": "deployment", "timestamp": "2026-01-03T12:00:00Z"},
    {"event_type": "incident", "timestamp": "2026-01-04T12:00:00Z"},
]


class FlakyClient:
    """Raises the given errors in order, then returns VALID_RESPONSE."""

    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def complete(self, prompt, timeout_seconds):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return VALID_RESPONSE


# calculate_metrics

def test_metrics_happy_path():
    assert calculate_metrics(EVENTS) == {
        "merged_prs": 1,
        "average_pr_cycle_time_hours": 24.0,
        "deployments": 1,
        "incidents": 1,
    }


def test_metrics_empty_events():
    assert calculate_metrics([]) == {
        "merged_prs": 0,
        "average_pr_cycle_time_hours": None,
        "deployments": 0,
        "incidents": 0,
    }


def test_metrics_ignores_merge_without_open_or_before_open():
    events = [
        {"event_type": "pr_merged", "event_id": "pr-2", "timestamp": "2026-01-02T09:00:00Z"},
        {"event_type": "pr_opened", "event_id": "pr-3", "timestamp": "2026-01-05T09:00:00Z"},
        {"event_type": "pr_merged", "event_id": "pr-3", "timestamp": "2026-01-04T09:00:00Z"},
    ]
    metrics = calculate_metrics(events)
    assert metrics["merged_prs"] == 2
    assert metrics["average_pr_cycle_time_hours"] is None


def test_metrics_normalizes_timezones():
    events = [
        {"event_type": "pr_opened", "event_id": "pr-1", "timestamp": "2026-01-01T09:00:00+02:00"},
        {"event_type": "pr_merged", "event_id": "pr-1", "timestamp": "2026-01-01T09:00:00Z"},
    ]
    assert calculate_metrics(events)["average_pr_cycle_time_hours"] == 2.0


@pytest.mark.parametrize(
    "event",
    [
        "not a dict",
        {"event_type": "unknown", "timestamp": "2026-01-01T09:00:00Z"},
        {"event_type": "deployment", "timestamp": "not a date"},
        {"event_type": "deployment", "timestamp": "2026-01-01T09:00:00"},  # no timezone
        {"event_type": "deployment"},  # missing timestamp
        {"event_type": "pr_opened", "timestamp": "2026-01-01T09:00:00Z"},  # missing id
        {"event_type": "deployment", "event_id": 123, "timestamp": "2026-01-01T09:00:00Z"},
    ],
)
def test_metrics_rejects_invalid_events(event):
    with pytest.raises(InvalidEvent):
        calculate_metrics([event])


# parse_llm_response

def test_parse_valid_response():
    assert parse_llm_response(VALID_RESPONSE) == {
        "summary": "Healthy delivery flow.",
        "recommendations": ["Monitor cycle time."],
    }


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        "[]",
        '{"recommendations": []}',
        '{"summary": "ok", "recommendations": "nope"}',
        '{"summary": "ok", "recommendations": [1, 2]}',
    ],
)
def test_parse_rejects_invalid_response(response):
    with pytest.raises(InvalidLLMResponse):
        parse_llm_response(response)


# generate_team_insight

def test_generate_team_insight_happy_path():
    client = LLMClient(VALID_RESPONSE)  # also asserts no raw event ids leak into the prompt
    result = generate_team_insight("platform", EVENTS, client)

    assert result["team_id"] == "platform"
    assert result["metrics"]["merged_prs"] == 1
    assert result["insight"]["summary"] == "Healthy delivery flow."
    assert client.calls == 1


@pytest.mark.parametrize("team_id", ["", "   ", None])
def test_generate_rejects_bad_team_id(team_id):
    with pytest.raises(ValueError):
        generate_team_insight(team_id, EVENTS, LLMClient(VALID_RESPONSE))


def test_generate_rejects_non_list_events():
    with pytest.raises(ValueError):
        generate_team_insight("platform", "nope", LLMClient(VALID_RESPONSE))


def test_generate_retries_once_on_transient_error():
    client = FlakyClient([TimeoutError()])
    result = generate_team_insight("platform", EVENTS, client)

    assert result["insight"]["summary"] == "Healthy delivery flow."
    assert client.calls == 2


def test_generate_fails_after_second_transient_error():
    client = FlakyClient([TimeoutError(), ConnectionError()])
    with pytest.raises(RuntimeError):
        generate_team_insight("platform", EVENTS, client)
    assert client.calls == 2


def test_generate_does_not_retry_invalid_response():
    client = LLMClient("not json")
    with pytest.raises(InvalidLLMResponse):
        generate_team_insight("platform", EVENTS, client)
    assert client.calls == 1
