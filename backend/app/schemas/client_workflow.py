from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PersonDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    first_name: str = Field(min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone_number: str = Field(min_length=7, max_length=64, pattern=r'^[+0-9() .\-]+$')
    location: str = Field(min_length=1, max_length=500)

    @field_validator('first_name','middle_name','last_name','phone_number','location',mode='before')
    @classmethod
    def trim_profile_fields(cls,value):
        return value.strip() if isinstance(value,str) else value

    @field_validator('phone_number')
    @classmethod
    def valid_phone(cls,value):
        if sum(c.isdigit() for c in value)<7: raise ValueError('Enter at least seven phone-number digits.')
        return value

    @property
    def full_name(self):
        return ' '.join(x for x in (self.first_name, self.middle_name, self.last_name) if x)


class PasswordLogin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=80, pattern=r'^[A-Za-z0-9._@+-]+$')
    password: str = Field(min_length=1, max_length=256, repr=False)

    @field_validator('username',mode='before')
    @classmethod
    def normalize_username(cls, value):
        return value.strip().lower() if isinstance(value,str) else value


class ManagedAccountCreate(PasswordLogin, PersonDetails):
    password: str = Field(min_length=15, max_length=256, repr=False)
    confirm_password: str = Field(min_length=15,max_length=256,repr=False)
    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    role: Literal['DESIGNER', 'CLIENT'] = 'CLIENT'

    @model_validator(mode='after')
    def structured_name(self):
        if self.password!=self.confirm_password:raise ValueError('The passwords do not match.')
        self.display_name = self.full_name
        return self


class ManagedAccountUpdate(PersonDetails):
    model_config = ConfigDict(extra='forbid')
    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    role: Literal['ADMIN', 'DESIGNER', 'CLIENT']
    username: str | None = Field(default=None, min_length=3, max_length=80, pattern=r'^[A-Za-z0-9._@+-]+$')
    password: str | None = Field(default=None, min_length=15, max_length=256, repr=False)
    confirm_password: str | None = Field(default=None,min_length=15,max_length=256,repr=False)
    disabled: bool = False
    expected_revision: int = Field(ge=0)

    @model_validator(mode='after')
    def structured_name(self):
        if self.password!=self.confirm_password:raise ValueError('The passwords do not match.')
        self.display_name = self.full_name
        return self

    @field_validator('username',mode='before')
    @classmethod
    def normalize_username(cls, value):
        return value.strip().lower() if isinstance(value,str) and value.strip() else None


class AccountDelete(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0)


class CredentialUpdate(PasswordLogin):
    password: str = Field(min_length=15, max_length=256, repr=False)
    current_password: str | None = Field(default=None, max_length=256, repr=False)
    confirm_password: str = Field(min_length=15,max_length=256,repr=False)

    @model_validator(mode='after')
    def matching_passwords(self):
        if self.password!=self.confirm_password:raise ValueError('The passwords do not match.')
        return self


class LinkAccount(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str | None = Field(default=None, max_length=256, repr=False)


class ContactEmailUpdate(LinkAccount):
    email: str | None = Field(default=None, max_length=320)


class ProjectAllocation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    client_id: int = Field(gt=0)
    designer_id: int = Field(gt=0)
    allocated_budget: Decimal | None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    expected_details_revision: str | None=Field(default=None,pattern=r'^[a-f0-9]{64}$')


class PublicationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    layout_version_ids: list[int] = Field(min_length=1, max_length=100)
    estimate_id: int = Field(gt=0)
