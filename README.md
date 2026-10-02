# Team Insights

Turns a list of engineering events (PRs, deployments, incidents) into aggregated
team metrics, then asks an LLM for a short summary and recommendations.

## Structure

```
app/
  main.py            # calculate_metrics, build_prompt, parse_llm_response, generate_team_insight
  schemas/
    event.py         # Event validation (InvalidEvent)
    llm.py           # LLMClient stub (InvalidLLMResponse)
tests/
  test_main.py
```

## Requirements

- Python 3.10+
- pytest (`pip install pytest`)

## Run

```bash
python app/main.py
```

This prints the result for a sample set of events, using a stub LLM client.

## Test

```bash
python -m pytest
```

## Input

Each event is a dict:

| field        | required                               | notes                                 |
|--------------|----------------------------------------|---------------------------------------|
| `event_type` | yes                                    | `pr_opened`, `pr_merged`, `deployment`, `incident` |
| `timestamp`  | yes                                    | ISO 8601 with timezone (e.g. `2026-01-01T09:00:00Z`) |
| `event_id`   | for `pr_opened` / `pr_merged`          | string                                |

Invalid events raise `InvalidEvent`.

## Output

```json
{
  "team_id": "platform",
  "metrics": {
    "merged_prs": 1,
    "average_pr_cycle_time_hours": 24.0,
    "deployments": 1,
    "incidents": 1
  },
  "insight": {
    "summary": "Healthy delivery flow.",
    "recommendations": ["Monitor cycle time."]
  }
}
```

## Design decisions

- **Cycle time** is the average time from `pr_opened` to `pr_merged`, in hours,
  rounded to 2 decimals. Merges with no matching open, or that happen before
  the open, are still counted in `merged_prs` but left out of the average.
  If there is no valid pair, the average is `null`.
- **Timestamps** are normalized to UTC. Timestamps without a timezone are rejected.
- **LLM resilience:** a 5 s timeout per call. Timeout or connection errors are
  retried once, then a `RuntimeError` is raised. A malformed response
  (`InvalidLLMResponse`) is not retried.
- **LLM client:** `generate_team_insight` takes any object with a
  `complete(prompt, timeout_seconds)` method. `schemas/llm.py` holds a stub that
  returns a fixed response.
