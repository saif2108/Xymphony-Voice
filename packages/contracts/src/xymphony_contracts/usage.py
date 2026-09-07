"""Usage counters attached to LLM responses and session aggregates."""

from pydantic import BaseModel, ConfigDict, Field

from xymphony_contracts.enums import UsageUnit


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_units: int = Field(ge=0)
    output_units: int = Field(ge=0)
    unit: UsageUnit
    estimated_cost_usd: float | None = Field(default=None, ge=0)
