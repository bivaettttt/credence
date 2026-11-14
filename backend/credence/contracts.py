from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Label = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
]
Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1200)
]
Money = Annotated[int, Field(strict=True, gt=0, le=10**12)]
Nonnegative = Annotated[int, Field(strict=True, ge=0, le=10**12)]
Months = Annotated[int, Field(strict=True, ge=1, le=60)]
Revision = Annotated[int, Field(strict=True, ge=1)]
Role = Literal["APPLICANT", "CREDIT_ANALYST", "RISK_OFFICER", "ADMIN"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: Label
    password: Annotated[str, Field(min_length=1, max_length=128)]


class Account(Login):
    name: Label
    role: Role
    password: Annotated[str, Field(min_length=12, max_length=128)]


class Organization(Input):
    name: Label
    industry: Label
    profile: Label


class Product(Input):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9-]{1,20}$")]
    name: Label
    min_amount: Money
    max_amount: Money
    min_months: Months
    max_months: Months
    rate: Annotated[int, Field(strict=True, ge=0, le=10_000)]
    active: bool = True

    @model_validator(mode="after")
    def limits(self):
        if self.min_amount > self.max_amount or self.min_months > self.max_months:
            raise ValueError("Invalid ranges")
        return self


class ApplicationData(Input):
    amount: Money
    months: Months
    purpose: Label
    revenue: Money | None = None
    debt: Nonnegative | None = None
    profit: Annotated[int, Field(strict=True, ge=-(10**12), le=10**12)] | None = None
    age: Annotated[int, Field(strict=True, ge=0, le=1200)] | None = None


class NewApplication(ApplicationData):
    organization_id: UUID
    product_id: UUID


class EditApplication(ApplicationData):
    revision: Revision


class Document(Input):
    revision: Revision
    kind: Literal["FINANCIAL", "REGISTRATION", "SUPPORTING"]
    label: Label


class Command(Input):
    revision: Revision


class Explain(Command):
    reason: Reason


class Decision(Explain):
    choice: Literal["APPROVE", "REJECT"]


class ResponseInput(Command):
    choice: Literal["ACCEPT", "DECLINE"]


class LabClock(Command):
    at: AwareDatetime
