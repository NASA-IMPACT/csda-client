from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict
from stapi_pydantic import OrderParameters as StapiOrderParameters


class QuotaUnit(Enum):
    area = "area"
    filesize = "filesize"


class Profile(BaseModel):
    earthdata_username: str
    title: str | None
    first_name: str
    last_name: str
    funding_agency: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    research_area: str
    justification: str
    nda_signed: bool
    reduced_latency_data: bool
    reduced_latency_justification: str
    supporting_institution: str
    vendors: list[ProfileVendor]
    grants: list[Grant]


class ProfileVendor(BaseModel):
    vendor: str
    slug: str
    quota: int
    quota_unit: QuotaUnit
    approved: bool
    approved_date: datetime.date
    expiration_date: datetime.date
    notes: str
    preview_approved: bool


class Vendor(BaseModel):
    id: int
    name: str
    full_name: str
    slug: str
    has_tasking: bool


class Product(BaseModel):
    id: int
    slug: str
    name: str
    long_desc: str


class Grant(BaseModel):
    id: int
    grant_number: str
    start_date: datetime.date | None
    end_date: datetime.date | None


class CreateTaskingProposal(BaseModel):
    name: str
    products: list[CreateTaskingProductRequest]
    research_description: str
    tasking_justification: str
    grant: int


class CreateTaskingProductRequest(BaseModel):
    product: int
    n_proposed_granules: int


class TaskingProposal(BaseModel):
    id: int
    proposal_products: list[TaskingProductRequest]
    is_draft: bool
    grant: Grant
    user: str
    name: str
    research_description: str
    tasking_justification: str
    final_decision_type: str
    decision_details: str | None


class TaskingProductRequest(BaseModel):
    product: Product
    n_proposed_granules: int
    n_allocated_granules: int | None


class OrderParameters(StapiOrderParameters):
    model_config = ConfigDict(extra="allow")
