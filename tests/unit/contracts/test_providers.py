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
