from __future__ import annotations

from datetime import datetime
from enum import Enum
from functools import cache
from typing import Sequence
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import Field
from pydantic_cacheable_model import CacheId
from tqdm import tqdm
from typing_extensions import Self

from ji_async_http_utils.httpx import http_get, run_in_lifespan
from .utils.base_model import BaseModel
from .utils.scrape_utils import (
    ScrapableField,
    ScrapableModel,
)


class UncomputableIdError(Exception):
    pass


class MALegislatureAPIModel(ScrapableModel):
    CACHE_ROOT = "malegislature-api-cache"
    BASE_URL = "https://malegislature.gov"


class MALegislatureAPIModelWithExtraScrapableDetails(MALegislatureAPIModel):
    Details: str | None = None

    @property
    def detail_url(self) -> str | None:
        if self.Details:
            return self.Details.replace("http://", "https://")
        return None

    async def scrape(self, *, use_cache: bool = True) -> None:
        await super().scrape(use_cache=use_cache)
        if (
            self.unscraped_fields()
            and self.detail_url
            and (
                response := await self.http_get(
                    id=self.id,
                    url=self.detail_url,
                    headers={"Accept": "application/json"},
                    raise_on_status_except_for=[400, 404, 500],
                )
            )
        ):
            for field, value in response.json().items():
                setattr(self, field, value)
            self.cache()


class LegislativeMember(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/LegislativeMembers"

    GeneralCourtNumber: int
    MemberCode: CacheId[str]

    Name: ScrapableField[str]
    LeadershipPosition: ScrapableField[str]
    Branch: ScrapableField[str]
    District: ScrapableField[str]
    Party: ScrapableField[str]
    EmailAddress: ScrapableField[str]
    RoomNumber: ScrapableField[str]
    PhoneNumber: ScrapableField[str]
    FaxNumber: ScrapableField[str]
    SponsoredBills: ScrapableField[list[Document]]
    CoSponsoredBills: ScrapableField[list[Document]]
    Committees: ScrapableField[list[CommitteeModel]]


class BillSponsorTypeEnum(Enum):
    LEGISLATIVE_MEMBER = 1
    COMMITTEE = 2
    PUBLIC_REQUEST = 3
    SPECIAL_REQUEST = 4


class BillSponsorSummary(BaseModel):
    Details: str | None = None
    Id: str | None
    Name: str
    Type: BillSponsorTypeEnum
    ResponseDate: datetime | None


class Attachment(BaseModel):
    Description: str | None = None
    DownloadUrl: str | None = None


class FiscalAmount(BaseModel):
    FiscalType: str | None = None
    Amount: str | None = None


class CommitteeVoteRecord(BaseModel):
    Favorable: list[LegislativeMember] | None = None
    Adverse: list[LegislativeMember] | None = None
    ReserveRight: list[LegislativeMember] | None = None
    NoVoteRecorded: list[LegislativeMember] | None = None


class CommitteeModel(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/Committees"

    GeneralCourtNumber: int | None
    CommitteeCode: str | None = None

    FullName: ScrapableField[str]
    ShortName: ScrapableField[str]
    Description: ScrapableField[str]
    Branch: ScrapableField[str]
    SenateChairperson: ScrapableField[LegislativeMember]
    HouseChairperson: ScrapableField[LegislativeMember]
    DocumentsBeforeCommittee: ScrapableField[list[Document]]
    ReportedOutDocuments: ScrapableField[list[Document]]
    Hearings: ScrapableField[list[Hearing]]

    @property
    def id(self) -> str:
        if self.Details:
            return self.Details
        if self.CommitteeCode:
            id = f"{self.CommitteeCode}"
        elif self.ShortName:
            id = f"{self.ShortName}"
        elif self.FullName:
            id = f"{self.FullName}"
        else:
            raise UncomputableIdError(
                f"Could not compute unique Id for Committee {self}"
            )
        if self.GeneralCourtNumber:
            id = f"{self.GeneralCourtNumber}-{id}"
        return id


class CommitteeVote(MALegislatureAPIModel):
    Date: datetime

    Question: str | None = None
    Bill: Document | None = None
    Committee: CommitteeModel | None = None
    Vote: list[CommitteeVoteRecord] | None = None

    @property
    def id(self) -> str:
        if not self.Bill:
            raise UncomputableIdError(f"{self}")
        return f"{self.Bill.id}-{self.Date.isoformat()}"


class CommitteeRecommendation(BaseModel):
    Action: str | None = None
    FiscalAmounts: list[FiscalAmount] | None = None
    Committee: CommitteeModel | None = None
    Votes: list[CommitteeVote] | None = None


class Event(BaseModel):
    EventId: int
    Name: str | None = None
    Status: str | None = None
    EventDate: datetime | None = None
    StartTime: datetime | None = None
    Description: str | None = None


class SpecialEvent(MALegislatureAPIModel, Event):
    EventId: CacheId[int]
    list_endpoint = "/api/SpecialEvents"
    Location: LocationModel | None = None


class RollCall(MALegislatureAPIModelWithExtraScrapableDetails):
    GeneralCourtNumber: int
    RollCallNumber: int

    Branch: ScrapableField[str]
    QuestionMotion: ScrapableField[str]
    Yeas: ScrapableField[list[LegislativeMember]]
    Nays: ScrapableField[list[LegislativeMember]]
    Absent: ScrapableField[list[LegislativeMember]]
    DownloadUrl: ScrapableField[str]

    @property
    def id(self) -> str:
        return f"{self.GeneralCourtNumber}-{self.RollCallNumber}"


class Amendment(MALegislatureAPIModelWithExtraScrapableDetails):
    GeneralCourtNumber: int
    AmendmentNumber: str | None = None
    ParentBillNumber: str | None = None
    Branch: str | None = None

    Bill: ScrapableField[Document]
    Sponsor: ScrapableField[BillSponsorSummary]
    Category: ScrapableField[str]
    Action: ScrapableField[str]
    RollCall: ScrapableField[list[RollCall]]
    Title: ScrapableField[str]
    RedraftNumber: ScrapableField[int]
    IsFurther: ScrapableField[bool]
    Text: ScrapableField[str]

    @property
    def detail_url(self) -> str | None:
        if not (self.ParentBillNumber and self.Branch and self.AmendmentNumber):
            return None
        return f"{self.BASE_URL}/api/GeneralCourts/{self.GeneralCourtNumber}/Documents/{self.ParentBillNumber}/Branches/{self.Branch}/Amendments/{self.AmendmentNumber}"

    @property
    def id(self) -> str:
        if self.Details:
            return self.Details
        if self.ParentBillNumber and self.Branch and self.AmendmentNumber:
            return f"{self.GeneralCourtNumber}-{self.ParentBillNumber}-{self.Branch}-{self.AmendmentNumber}"
        raise UncomputableIdError(f"Could not compute unique Id for Amendment {self}")


class Document(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/Documents"

    BillNumber: str | None
    IsDocketBookOnly: bool
    GeneralCourtNumber: int
    DocketNumber: str | None = None
    Title: str | None = None
    BillHistory: str | None = None
    PrimarySponsor: ScrapableField[BillSponsorSummary]
    Cosponsors: ScrapableField[list[BillSponsorSummary]]
    JointSponsor: ScrapableField[BillSponsorSummary]
    LegislationTypeName: ScrapableField[str]
    Pinslip: ScrapableField[str]
    DocumentText: ScrapableField[str]
    EmergencyPreamble: ScrapableField[str]
    RollCalls: ScrapableField[list[RollCall]]
    Attachments: ScrapableField[list[Attachment]]
    CommitteeRecommendations: ScrapableField[list[CommitteeRecommendation]]
    Amendments: ScrapableField[list[Amendment]]

    document_history: ScrapableField[list[DocumentHistoryAction]]

    @property
    def id(self) -> str:
        if self.Details:
            return self.Details
        if self.BillNumber:
            return f"{self.GeneralCourtNumber}-{self.BillNumber}"
        if self.DocketNumber:
            return f"{self.GeneralCourtNumber}-{self.DocketNumber}"
        if self.Title:
            return f"{self.GeneralCourtNumber}-{self.Title}"

        raise UncomputableIdError(f"Could not compute unique Id for Document {self}")

    async def scrape_document_history(self) -> None:
        if self.BillHistory and (
            resp := await http_get(
                self.BillHistory,
                headers={"Accept": "application/json"},
                raise_on_status_except_for=[404],
            )
        ):
            self.document_history = [DocumentHistoryAction(**i) for i in resp.json()]
        else:
            self.document_history = []


class AgendaItem(BaseModel):
    Topic: str | None = None
    StartTime: datetime | None = None
    EndTime: datetime | None = None
    DocumentsInAgenda: list[Document] | None = None


class HearingRescheduled(BaseModel):
    Status: str | None = None
    EventDate: datetime | None = None
    StartTime: datetime | None = None
    Location: LocationModel | None = Field(default=None)


class LocationModel(BaseModel):
    LocationName: str | None = None
    AddressLine1: str | None = None
    AddressLine2: str | None = None
    City: str | None = None
    State: str | None = None
    ZipCode: str | None = None


@cache
async def get_soup(url: str) -> BeautifulSoup:
    return BeautifulSoup((await http_get(url)).text, "html.parser")


class Hearing(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/Hearings"

    EventId: CacheId[int]

    # scraped from hearing detail API
    Name: ScrapableField[str]
    Status: ScrapableField[str]
    EventDate: ScrapableField[datetime]
    StartTime: ScrapableField[datetime]
    Description: ScrapableField[str]
    HearingHost: ScrapableField[CommitteeModel]
    HearingAgendas: ScrapableField[list[AgendaItem]]
    RescheduledHearing: ScrapableField[list[HearingRescheduled] | HearingRescheduled]
    Location: ScrapableField[LocationModel]

    # scraped from hearing detail HTML page
    document_urls: ScrapableField[list[str]]
    testimony_instructions: ScrapableField[str]

    async def scrape(self, *, use_cache: bool = True) -> None:
        await self.scrape_testimony_instructions()  # NOTE: hack
        await super().scrape(use_cache=use_cache)

    async def scrape_document_urls(self) -> None:
        """Scrape hearing document urls from the hearing details page.

        Assumptions:
        - Testimony links appear in the first column of the table inside <div id="documentsSection">
        """
        soup = await get_soup(f"{self.BASE_URL}/Events/Hearings/Detail/{self.EventId}")
        if docs_div := soup.find(id="documentsSection"):
            assert isinstance(docs_div, Tag)
            self.document_urls = [
                urljoin(self.BASE_URL, str(a.get("href") or ""))
                for a in docs_div.select(  # pyright: ignore[reportUnknownMemberType]
                    "table.agendaTable tbody tr td:first-child a[href]"
                )
            ]

    async def scrape_testimony_instructions(self) -> None:
        # breakpoint()
        pass


class GeneralCourt(MALegislatureAPIModel):
    Number: CacheId[int]
    FirstYear: int
    SecondYear: int
    Name: str | None = None


class GeneralLawBase(MALegislatureAPIModelWithExtraScrapableDetails):
    Code: str | None = None
    Name: ScrapableField[str]

    @property
    def id(self) -> str:
        if self.Details:
            return self.Details
        if self.Code:
            return self.Code
        raise UncomputableIdError(
            f"Could not compute unique Id for {type(self).__name__} {self}"
        )


class GeneralLawPart(GeneralLawBase):
    list_endpoint = "/api/Parts"

    FirstChapter: ScrapableField[int]
    LastChapter: ScrapableField[int]
    Chapters: ScrapableField[list[GeneralLawChapter]]


class GeneralLawChapter(GeneralLawBase):
    list_endpoint = "/api/Chapters"

    IsRepealed: ScrapableField[bool]
    StrickenText: ScrapableField[str]
    Part: ScrapableField[GeneralLawPart]
    Sections: ScrapableField[list[GeneralLawSection]]


class GeneralLawSection(MALegislatureAPIModelWithExtraScrapableDetails):
    ChapterCode: str | None = None

    IsRepealed: ScrapableField[bool]
    Text: ScrapableField[str]
    Chapter: ScrapableField[GeneralLawChapter]
    Part: ScrapableField[GeneralLawPart]


class DocumentHistoryAction(BaseModel):
    Date: datetime
    Branch: str | None = None
    Action: str | None = None


class JournalBase(MALegislatureAPIModel):
    GeneralCourtNumber: int
    IsJoint: bool
    Details: str | None = None
    JournalSessionDate: str | None = None

    @property
    def id(self) -> str:
        if self.Details:
            return self.Details
        jc = str(self.GeneralCourtNumber)
        jsd = self.JournalSessionDate or ""
        ij = "1" if self.IsJoint else "0"
        if jc and jsd:
            return f"{jc}-{jsd}-{ij}"
        raise UncomputableIdError(
            f"Could not compute unique Id for {type(self).__name__} {self}"
        )


class HouseJournal(JournalBase):
    list_endpoint = "/api/HouseJournals"

    DownloadUrl: str | None = None
    SessionDate: datetime | None = None
    RollCallRange: str | None = None


class SenateJournal(JournalBase, MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/SenateJournals"

    DownloadUrl: ScrapableField[str]
    SessionDate: ScrapableField[datetime]


class Leadership(MALegislatureAPIModel):
    Member: LegislativeMember | None = None
    Position: CacheId[str]


class Report(MALegislatureAPIModel):
    list_endpoint = "/api/Reports"

    Date: datetime
    Name: str | None = None
    SubmittedBy: str | None = None
    DownloadUrl: str | None = None

    @property
    def id(self) -> str:
        return str(self.Date.date())


class Session(MALegislatureAPIModel, Event):
    list_endpoint = "/api/Sessions"

    EventId: CacheId[int]
    GeneralCourtNumber: int
    LocationName: str | None = None


class SessionLaw(MALegislatureAPIModel):
    list_endpoint = "/api/SessionLaws"

    Year: int
    ChapterNumber: str | None = None
    Type: str | None = None
    ApprovalType: str | None = None
    Title: str | None = None
    Status: str | None = None
    ApprovedDate: str | None = None
    ChapterText: str | None = None
    OriginBill: Document | None = None

    @property
    def id(self) -> str:
        if self.ChapterNumber:
            return f"{self.Year}-{self.ChapterNumber}"
        if self.Title:
            return self.Title
        raise UncomputableIdError(f"Could not compute unique Id for SessionLaw {self}")


class City(MALegislatureAPIModel):
    list_endpoint = "/api/Documents/SupportedCities"

    name: CacheId[str]
    documents: ScrapableField[list[Document]]

    @classmethod
    def _response_to_models(cls, resp: httpx.Response) -> Sequence[Self]:
        return [cls(name=i) for i in resp.json()]  # pyright: ignore[reportCallIssue]

    async def scrape_documents(self) -> None:
        url = f"{self.BASE_URL}/api/Cities/{self.name}/Documents"
        resp = await self.http_get(
            id=self.id,
            url=url,
            headers={"Accept": "application/json"},
            raise_on_status_except_for=[400, 404],
        )
        if resp is None:
            self.documents = []
            return

        self.documents = [Document(**i) for i in resp.json()]


@run_in_lifespan
async def scrape_malegislature_api() -> None:
    await Leadership.scrape_all("/api/Branches/House/Leadership")
    await Leadership.scrape_all("/api/Branches/Senate/Leadership")
    models: list[type[MALegislatureAPIModel]] = [
        City,
        CommitteeModel,
        Document,
        GeneralLawChapter,
        GeneralLawPart,
        Hearing,
        HouseJournal,
        LegislativeMember,
        Report,
        SenateJournal,
        Session,
        SessionLaw,
        SpecialEvent,
    ]
    for model in models:
        await model.scrape_all(check_api=True)

    # get votes
    vote_endpoints: set[str] = set()
    for doc in await Document.fetch_all(check_api=False, use_cache=True):
        if isinstance(doc.CommitteeRecommendations, list):
            for rec in doc.CommitteeRecommendations:
                if (
                    rec.Committee
                    and rec.Committee.CommitteeCode
                    and doc.BillNumber
                    and doc.GeneralCourtNumber
                ):
                    vote_endpoints.add(
                        f"/api/Committees/{rec.Committee.CommitteeCode}/Documents/{doc.BillNumber}/CommitteeVotes"
                    )

    successful = 0
    for endpoint in tqdm(vote_endpoints):
        try:
            await CommitteeVote.scrape_all(endpoint)
            successful += 1
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400:
                raise

    print(f"{successful}/{len(vote_endpoints)}")


if __name__ == "__main__":
    scrape_malegislature_api()
