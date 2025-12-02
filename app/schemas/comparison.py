from pydantic import BaseModel, Field
from uuid import UUID


class HTMLComparisonRequest(BaseModel):
    html_content_1: str = Field(..., description="The first HTML content string.")
    html_content_2: str = Field(..., description="The second HTML content string.")


class VersionComparisonRequest(BaseModel):
    version_id_1: UUID = Field(..., description="The ID of the first version to compare.")
    version_id_2: UUID = Field(..., description="The ID of the second version to compare.") 