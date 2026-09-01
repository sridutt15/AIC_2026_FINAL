"""LLM client tests: mocked Gemini transport — never hits the real API."""

from types import SimpleNamespace

import pytest

from app.core.llm.client import call_llm, estimate_cost_usd


class MockGeminiTransport:
    """SDK-shaped stub: .text + .usage_metadata, counts invocations."""

    def __init__(self, text="Do X because driver Y moved.", prompt_tokens=120, completion_tokens=45):
        self.text = text
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=prompt_tokens,
            candidates_token_count=completion_tokens,
        )
        self.calls = 0

    def generate_content(self, prompt: str):
        self.calls += 1
        self.last_prompt = prompt
        return self


def test_call_llm_parses_response_into_text_and_usage():
    """call_llm returns text + usage stats + deterministic cost estimate."""
    mock = MockGeminiTransport(text="Rebalance the mix toward gizmo.", prompt_tokens=210, completion_tokens=60)
    result = call_llm("some prompt", client=mock)
    assert result["text"] == "Rebalance the mix toward gizmo."
    assert result["prompt_tokens"] == 210
    assert result["completion_tokens"] == 60
    assert result["latency_ms"] >= 0
    assert result["cost_usd"] == pytest.approx(estimate_cost_usd(210, 60))
    assert mock.calls == 1
    assert mock.last_prompt == "some prompt"


def test_call_llm_is_the_only_llm_entrypoint():
    """The prompt is passed through unchanged — no hidden data injection."""
    mock = MockGeminiTransport()
    call_llm("exact prompt string", client=mock)
    assert mock.last_prompt == "exact prompt string"


def test_empty_response_raises():
    class EmptyTransport(MockGeminiTransport):
        def generate_content(self, prompt):
            self.calls += 1
            return SimpleNamespace(text="", usage_metadata=SimpleNamespace(
                prompt_token_count=1, candidates_token_count=0))

    with pytest.raises(RuntimeError):
        call_llm("prompt", client=EmptyTransport())


def test_cost_estimation_uses_published_rates():
    """Default rates: $0.10/Mtok input, $0.40/Mtok output."""
    assert estimate_cost_usd(1_000_000, 0) == pytest.approx(0.10)
    assert estimate_cost_usd(0, 1_000_000) == pytest.approx(0.40)
    assert estimate_cost_usd(500_000, 250_000) == pytest.approx(0.15)
