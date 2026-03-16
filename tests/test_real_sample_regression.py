from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.real_sample_loader import load_real_sample


@pytest.fixture(scope="module")
def real_sample() -> dict:
    return load_real_sample()


def test_real_sample_articles_preserve_direct_links(real_sample: dict) -> None:
    assert real_sample["articles"], "saved real sample should include articles"
    for article in real_sample["articles"]:
        assert article.url.startswith("http"), "each saved article must preserve the original article URL"
        assert article.source.strip(), "each saved article must preserve source name"


def test_real_sample_preview_story_traceability(real_sample: dict) -> None:
    stories = real_sample["preview_payload"].get("stories", [])
    assert stories, "saved preview should include story rows"
    for story in stories:
        assert story.get("source_name"), "each preview story should include a source_name"
        assert str(story.get("original_url") or "").startswith("http"), "each preview story should include a direct original_url"


def test_real_sample_regression_metrics(real_sample: dict) -> None:
    payload = real_sample["preview_payload"]
    assert payload.get("county_first_local_selection") is True
    assert payload.get("geo_tagged_county", 0) >= 1
    assert payload.get("written_source_credits_emitted") is True
    assert payload.get("article_count", 0) >= payload.get("story_count", 0)
