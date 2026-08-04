from pydantic import BaseModel


class CVParseResult(BaseModel):
    text: str
    has_tables: bool
    has_multi_column: bool
    has_images: bool
    detected_sections: set[str]
