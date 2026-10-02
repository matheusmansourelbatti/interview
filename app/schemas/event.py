from datetime import datetime, timezone
from typing import Any


class InvalidEvent(ValueError):
    pass

class Event():

    def __init__(self):
        self.SUPPORTED_TYPES = {
            "pr_opened",
            "pr_merged",
            "deployment",
            "incident",
        }

    def parse_timestamp(self, value: Any) -> datetime:
        if not isinstance(value, str):
            raise InvalidEvent("timestamp must be a string")

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidEvent(f"invalid timestamp: {value}") from exc

        if parsed.tzinfo is None:
            raise InvalidEvent("timestamp must include a timezone")

        return parsed.astimezone(timezone.utc)

    def validate(self, event: Any) -> tuple[str, datetime, str | None]:
        if not isinstance(event, dict):
            raise InvalidEvent("each event must be an object")

        event_type = event.get("type")
        if event_type not in self.SUPPORTED_TYPES:
            raise InvalidEvent(f"unsupported event type: {event_type}")

        timestamp = self.parse_timestamp(event.get("timestamp"))

        event_id = event.get("id")
        requires_id = event_type in {"pr_opened", "pr_merged"}

        if requires_id and not isinstance(event_id, str):
            raise InvalidEvent(f"{event_type} requires a string id")

        if event_id is not None and not isinstance(event_id, str):
            raise InvalidEvent("id must be a string when provided")
