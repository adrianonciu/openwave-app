from __future__ import annotations

import json
from pathlib import Path

from app.models.story_summary_policy import (
    StorySummaryPolicy,
    StorySummaryPolicyBundle,
    StorySummaryPolicyExample,
)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "story_summary_policy.json"


class StorySummaryPolicyService:
    def __init__(self) -> None:
        raw_data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self._bundle = StorySummaryPolicyBundle(
            policy=StorySummaryPolicy(**raw_data["policy"]),
            examples=[StorySummaryPolicyExample(**item) for item in raw_data["examples"]],
        )

    def get_policy_bundle(self) -> StorySummaryPolicyBundle:
        return self._bundle

    def get_policy(self) -> StorySummaryPolicy:
        return self._bundle.policy

    def get_examples(self) -> list[StorySummaryPolicyExample]:
        return self._bundle.examples

    def get_examples_by_category(self, category: str) -> list[StorySummaryPolicyExample]:
        return [
            example for example in self._bundle.examples if example.category == category
        ]
