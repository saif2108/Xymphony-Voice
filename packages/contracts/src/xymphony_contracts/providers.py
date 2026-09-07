"""Provider *selection* contracts. Adapters live elsewhere; keys are opaque slugs."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

_SECRET_PARAM_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "password",
        "token",
        "access_token",
        "authorization",
        "private_key",
    }
)

PROVIDER_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def _reject_secret_params(params: dict[str, JsonValue]) -> dict[str, JsonValue]:
    for key in params:
        normalized = key.lower().replace("-", "_")
        if normalized in _SECRET_PARAM_NAMES:
            msg = "provider params must not contain credentials"
            raise ValueError(msg)
    return params


class LLMBinding(FrozenModel):
    """AgentVersion LLM selection. `provider_key` is a registry slug, not a vendor SDK type."""

    provider_key: str = Field(pattern=PROVIDER_KEY_PATTERN)
    model: str = Field(min_length=1, max_length=256)
    params: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def params_must_not_hold_secrets(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return _reject_secret_params(value)


class STTBinding(FrozenModel):
    provider_key: str = Field(pattern=PROVIDER_KEY_PATTERN)
    model: str = Field(min_length=1, max_length=256)
    params: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def params_must_not_hold_secrets(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return _reject_secret_params(value)


class TTSBinding(FrozenModel):
    provider_key: str = Field(pattern=PROVIDER_KEY_PATTERN)
    voice_ref: str = Field(min_length=1, max_length=256)
    params: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def params_must_not_hold_secrets(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return _reject_secret_params(value)
