"""Modality-neutral message parts (P1 uses text and audio_ref)."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from xymphony_contracts.enums import ContentPartType


class ContentPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: ContentPartType
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
