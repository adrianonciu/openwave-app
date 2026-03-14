from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class TtsBudgetEstimateData:
    provider: str
    presenter_name: str
    segment_count: int
    estimated_total_characters: int
    estimated_required_credits: int
    remaining_credits: int | None
    budget_check_performed: bool
    within_budget: bool | None

    def to_dict(self) -> dict[str, object | None]:
        return {
            "provider": self.provider,
            "presenter_name": self.presenter_name,
            "segment_count": self.segment_count,
            "estimated_total_characters": self.estimated_total_characters,
            "estimated_required_credits": self.estimated_required_credits,
            "remaining_credits": self.remaining_credits,
            "budget_check_performed": self.budget_check_performed,
            "within_budget": self.within_budget,
        }


class TtsBudgetExceededError(RuntimeError):
    def __init__(self, estimate: TtsBudgetEstimateData, message: str | None = None) -> None:
        self.estimate = estimate
        super().__init__(
            message
            or (
                "Estimated TTS cost exceeds the available provider budget for this bulletin. "
                "Try a shorter bulletin, reduce story count, or switch to a lower-cost voice/test mode."
            )
        )


class TtsBudgetService:
    _ELEVENLABS_SUBSCRIPTION_URL = 'https://api.elevenlabs.io/v1/user/subscription'
    _QUOTA_STATUS_MARKERS = ('quota_exceeded', 'credits remaining', 'exceeds your quota')

    def estimate_budget(
        self,
        *,
        provider_name: str,
        presenter_name: str,
        prepared_segment_texts: list[str],
        elevenlabs_api_key: str | None = None,
    ) -> TtsBudgetEstimateData:
        estimated_total_characters = sum(len(text) for text in prepared_segment_texts)
        estimated_required_credits = estimated_total_characters
        remaining_credits: int | None = None
        budget_check_performed = False
        within_budget: bool | None = None

        if provider_name == 'elevenlabs' and elevenlabs_api_key and elevenlabs_api_key.strip():
            remaining_credits = self._fetch_elevenlabs_remaining_credits(elevenlabs_api_key)
            budget_check_performed = remaining_credits is not None
            if remaining_credits is not None:
                within_budget = estimated_required_credits <= remaining_credits

        return TtsBudgetEstimateData(
            provider=provider_name,
            presenter_name=presenter_name,
            segment_count=len(prepared_segment_texts),
            estimated_total_characters=estimated_total_characters,
            estimated_required_credits=estimated_required_credits,
            remaining_credits=remaining_credits,
            budget_check_performed=budget_check_performed,
            within_budget=within_budget,
        )

    def raise_if_budget_exceeded(self, estimate: TtsBudgetEstimateData) -> None:
        if estimate.budget_check_performed and estimate.within_budget is False:
            raise TtsBudgetExceededError(
                estimate,
                (
                    "This bulletin is likely to exceed the available TTS quota before audio generation starts. "
                    "Try a shorter bulletin, reduce story count, or switch to a lower-cost voice/test mode."
                ),
            )

    def parse_quota_error(
        self,
        *,
        provider_name: str,
        error_message: str,
        fallback_estimate: TtsBudgetEstimateData,
    ) -> TtsBudgetExceededError | None:
        normalized_message = error_message.lower()
        if provider_name != 'elevenlabs':
            return None
        if not any(marker in normalized_message for marker in self._QUOTA_STATUS_MARKERS):
            return None

        payload = self._extract_json_payload(error_message)
        detail = payload.get('detail') if isinstance(payload.get('detail'), dict) else {}
        nested_message = detail.get('message') if isinstance(detail, dict) else None
        resolved_remaining = self._extract_first_int(
            nested_message or error_message,
            r'You have\s+(\d+)\s+credits remaining',
        )
        resolved_required = self._extract_first_int(
            nested_message or error_message,
            r'while\s+(\d+)\s+credits are required',
        )

        estimate = TtsBudgetEstimateData(
            provider=fallback_estimate.provider,
            presenter_name=fallback_estimate.presenter_name,
            segment_count=fallback_estimate.segment_count,
            estimated_total_characters=fallback_estimate.estimated_total_characters,
            estimated_required_credits=(
                resolved_required
                if resolved_required is not None
                else fallback_estimate.estimated_required_credits
            ),
            remaining_credits=(
                resolved_remaining
                if resolved_remaining is not None
                else fallback_estimate.remaining_credits
            ),
            budget_check_performed=True,
            within_budget=False,
        )
        return TtsBudgetExceededError(
            estimate,
            (
                "OpenWave could not generate audio because the TTS provider quota is too low for this briefing. "
                "Try a shorter bulletin, reduce story count, or switch to a lower-cost voice/test mode."
            ),
        )

    def _fetch_elevenlabs_remaining_credits(self, api_key: str) -> int | None:
        request = urllib.request.Request(
            url=self._ELEVENLABS_SUBSCRIPTION_URL,
            headers={
                'Accept': 'application/json',
                'xi-api-key': api_key,
            },
            method='GET',
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8', errors='ignore'))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        if not isinstance(payload, dict):
            return None

        character_limit = self._coerce_int(payload.get('character_limit'))
        character_count = self._coerce_int(payload.get('character_count'))
        if character_limit is not None and character_count is not None:
            return max(character_limit - character_count, 0)

        remaining_credits = self._coerce_int(payload.get('remaining_credits'))
        if remaining_credits is not None:
            return max(remaining_credits, 0)

        credits_remaining = self._coerce_int(payload.get('credits_remaining'))
        if credits_remaining is not None:
            return max(credits_remaining, 0)

        return None

    def _extract_json_payload(self, error_message: str) -> dict[str, object]:
        match = re.search(r'(\{.*\})', error_message)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _extract_first_int(self, value: str, pattern: str) -> int | None:
        match = re.search(pattern, value)
        if not match:
            return None
        return self._coerce_int(match.group(1))

    def _coerce_int(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None
