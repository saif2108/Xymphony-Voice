import pytest
from pydantic import ValidationError

from xymphony_contracts import LLMBinding, STTBinding, TTSBinding


def test_valid_provider_bindings() -> None:
    llm = LLMBinding(provider_key="openai_compatible", model="gpt-4o-mini")
    stt = STTBinding(provider_key="deepgram", model="nova-2")
    tts = TTSBinding(provider_key="cartesia", voice_ref="speaker-1")
    assert llm.model == "gpt-4o-mini"
    assert stt.provider_key == "deepgram"
    assert tts.voice_ref == "speaker-1"


def test_provider_key_must_be_slug() -> None:
    with pytest.raises(ValidationError):
        LLMBinding(provider_key="OpenAI", model="x")
    with pytest.raises(ValidationError):
        LLMBinding(provider_key="sk-abc", model="x")
    with pytest.raises(ValidationError):
        STTBinding(provider_key="", model="x")


def test_params_must_not_contain_secrets() -> None:
    with pytest.raises(ValidationError):
        LLMBinding(
            provider_key="openai_compatible",
            model="gpt-4o-mini",
            params={"api_key": "secret"},
        )
    with pytest.raises(ValidationError):
        TTSBinding(
            provider_key="elevenlabs",
            voice_ref="v1",
            params={"token": "x"},
        )


def test_empty_model_or_voice_rejected() -> None:
    with pytest.raises(ValidationError):
        LLMBinding(provider_key="ollama", model="")
    with pytest.raises(ValidationError):
        TTSBinding(provider_key="piper", voice_ref="")


def test_bindings_are_frozen() -> None:
    llm = LLMBinding(provider_key="gemini", model="flash")
    with pytest.raises(ValidationError):
        llm.model = "other"  # type: ignore[misc]


def test_llm_request_generation_fields_validation() -> None:
    from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole

    req = LLMRequest(
        provider_key="openai",
        model="gpt-4o",
        messages=(LLMMessage(role=LLMRole.USER, content="hi"),),
        temperature=0.8,
        top_p=0.95,
        max_output_tokens=100,
    )
    assert req.temperature == 0.8
    assert req.top_p == 0.95
    assert req.max_output_tokens == 100

    # Temperature bounds
    with pytest.raises(ValidationError):
        LLMRequest(
            provider_key="openai",
            model="gpt-4o",
            messages=(),
            temperature=-0.1,
        )
    with pytest.raises(ValidationError):
        LLMRequest(
            provider_key="openai",
            model="gpt-4o",
            messages=(),
            temperature=2.1,
        )

    # Top_p bounds
    with pytest.raises(ValidationError):
        LLMRequest(
            provider_key="openai",
            model="gpt-4o",
            messages=(),
            top_p=-0.1,
        )
    with pytest.raises(ValidationError):
        LLMRequest(
            provider_key="openai",
            model="gpt-4o",
            messages=(),
            top_p=1.1,
        )

    # Max output tokens bounds
    with pytest.raises(ValidationError):
        LLMRequest(
            provider_key="openai",
            model="gpt-4o",
            messages=(),
            max_output_tokens=0,
        )
