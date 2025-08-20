from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class QuotaUnit(Enum):
    area = "area"
    filesize = "filesize"


class Profile(BaseModel):
    earthdata_username: str
    title: Optional[str] = None
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


class Grant(BaseModel):
    id: int
    grant_number: str
    start_date: datetime.date | None
    end_date: datetime.date | None
