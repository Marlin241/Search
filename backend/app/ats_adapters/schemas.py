from pydantic import BaseModel


class FormField(BaseModel):
    name: str
    label: str
    field_type: str
    required: bool
    options: list[str] | None = None
    value: str | None = None
    is_custom: bool = False


class DiscoveredForm(BaseModel):
    submit_url: str
    fields: list[FormField]
    hidden_fields: dict[str, str] = {}
