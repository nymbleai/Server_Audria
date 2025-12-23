from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class ResidenceBase(BaseModel):
    id: str
    zipCode: str = ""
    city: str = ""
    state: str = ""
    fromYear: str = ""
    toYear: str = ""
    notes: str = ""


class WorkHistoryBase(BaseModel):
    id: str
    job: str = ""
    fromYear: str = ""
    toYear: str = ""
    notes: str = ""


class PersonalInfoBase(BaseModel):
    interests: str = ""
    personalityTraits: str = ""
    spiritualPractices: str = ""
    comfortItems: str = ""
    preferredGreeting: str = ""
    favoriteSongs: str = ""
    healthConditions: str = ""
    sensitivities: str = ""
    sensoryPreferences: str = ""


class DailyRoutineBase(BaseModel):
    wakeTime: str = ""
    napTime: str = ""
    sleepTime: str = ""


class PersonDetailsData(BaseModel):
    """
    All data is stored as JSONB in the person_details.data column.
    This includes:
    - residences: Array of residence objects
    - workHistory: Array of work history objects (stored as JSONB)
    - personalInfo: Personal information object (stored as JSONB)
    - dailyRoutine: Daily routine object (stored as JSONB)
    """
    residences: List[ResidenceBase] = []
    workHistory: List[WorkHistoryBase] = []  # Stored as JSONB array
    personalInfo: PersonalInfoBase = PersonalInfoBase()  # Stored as JSONB object
    dailyRoutine: DailyRoutineBase = DailyRoutineBase()  # Stored as JSONB object


# Person Schemas
class PersonBase(BaseModel):
    name: str
    generation: Optional[str] = None


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    generation: Optional[str] = None


class PersonResponse(PersonBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Person Details Schemas
class PersonDetailsBase(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


class PersonDetailsCreate(PersonDetailsBase):
    person_id: UUID


class PersonDetailsUpdate(BaseModel):
    data: Optional[Dict[str, Any]] = None


class PersonDetailsResponse(PersonDetailsBase):
    id: UUID
    person_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Combined response with person and details
class PersonWithDetailsResponse(PersonResponse):
    details: Optional[PersonDetailsResponse] = None

