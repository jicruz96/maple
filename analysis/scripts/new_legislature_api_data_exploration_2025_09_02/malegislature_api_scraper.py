from __future__ import annotations

from datetime import datetime
from enum import Enum
from functools import cache
from typing import Sequence
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import Field
from pydantic_cacheable_model import CacheKey
from tqdm import tqdm
from typing_extensions import Self

from ji_async_http_utils.httpx import request, run_in_lifespan
from .utils.base_model import BaseModel
from .utils.base_model import (
    ScrapeableApiModel,
)
from pydantic_scrapeable_api_model import ScrapeableField
from pydantic_cacheable_model import CacheKeyComputationError


class MALegislatureAPIModel(ScrapeableApiModel):
    CACHE_ROOT = "malegislature-api-cache"
    BASE_URL = "https://malegislature.gov"


class MALegislatureAPIModelWithExtraScrapableDetails(MALegislatureAPIModel):
    Details: str | None = None

    @property
    def detail_url(self) -> str | None:
        if self.Details:
            return self.Details.replace("http://", "https://")
        return None


class LegislativeMember(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/LegislativeMembers"

    MemberCode: CacheKey[str]
    GeneralCourtNumber: int

    Name: ScrapeableField[str]
    LeadershipPosition: ScrapeableField[str]
    Branch: ScrapeableField[str]
    District: ScrapeableField[str]
    Party: ScrapeableField[str]
    EmailAddress: ScrapeableField[str]
    RoomNumber: ScrapeableField[str]
    PhoneNumber: ScrapeableField[str]
    FaxNumber: ScrapeableField[str]
    SponsoredBills: ScrapeableField[list[Document]]
    CoSponsoredBills: ScrapeableField[list[Document]]
    Committees: ScrapeableField[list[CommitteeModel]]


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

    FullName: ScrapeableField[str]
    ShortName: ScrapeableField[str]
    Description: ScrapeableField[str]
    Branch: ScrapeableField[str]
    SenateChairperson: ScrapeableField[LegislativeMember]
    HouseChairperson: ScrapeableField[LegislativeMember]
    DocumentsBeforeCommittee: ScrapeableField[list[Document]]
    ReportedOutDocuments: ScrapeableField[list[Document]]
    Hearings: ScrapeableField[list[Hearing]]

    @property
    def cache_id(self) -> str:
        if self.Details:
            return self.Details
        if self.CommitteeCode:
            id = f"{self.CommitteeCode}"
        elif self.ShortName:
            id = f"{self.ShortName}"
        elif self.FullName:
            id = f"{self.FullName}"
        else:
            raise CacheKeyComputationError(
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
    def cache_id(self) -> str:
        if not self.Bill:
            raise CacheKeyComputationError(f"{self}")
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
    EventId: CacheKey[int]
    list_endpoint = "/api/SpecialEvents"
    Location: LocationModel | None = None


class RollCall(MALegislatureAPIModelWithExtraScrapableDetails):
    GeneralCourtNumber: int
    RollCallNumber: int

    Branch: ScrapeableField[str]
    QuestionMotion: ScrapeableField[str]
    Yeas: ScrapeableField[list[LegislativeMember]]
    Nays: ScrapeableField[list[LegislativeMember]]
    Absent: ScrapeableField[list[LegislativeMember]]
    DownloadUrl: ScrapeableField[str]

    @property
    def cache_id(self) -> str:
        return f"{self.GeneralCourtNumber}-{self.RollCallNumber}"


class Amendment(MALegislatureAPIModelWithExtraScrapableDetails):
    GeneralCourtNumber: int
    AmendmentNumber: str | None = None
    ParentBillNumber: str | None = None
    Branch: str | None = None

    Bill: ScrapeableField[Document]
    Sponsor: ScrapeableField[BillSponsorSummary]
    Category: ScrapeableField[str]
    Action: ScrapeableField[str]
    RollCall: ScrapeableField[list[RollCall]]
    Title: ScrapeableField[str]
    RedraftNumber: ScrapeableField[int]
    IsFurther: ScrapeableField[bool]
    Text: ScrapeableField[str]

    @property
    def detail_url(self) -> str | None:
        if not (self.ParentBillNumber and self.Branch and self.AmendmentNumber):
            return None
        return f"{self.BASE_URL}/api/GeneralCourts/{self.GeneralCourtNumber}/Documents/{self.ParentBillNumber}/Branches/{self.Branch}/Amendments/{self.AmendmentNumber}"

    @property
    def cache_id(self) -> str:
        if self.Details:
            return self.Details
        if self.ParentBillNumber and self.Branch and self.AmendmentNumber:
            return f"{self.GeneralCourtNumber}-{self.ParentBillNumber}-{self.Branch}-{self.AmendmentNumber}"
        raise CacheKeyComputationError(
            f"Could not compute unique Id for Amendment {self}"
        )


class Document(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/Documents"

    BillNumber: str | None
    IsDocketBookOnly: bool
    GeneralCourtNumber: int
    DocketNumber: str | None = None
    Title: str | None = None
    BillHistory: str | None = None
    PrimarySponsor: ScrapeableField[BillSponsorSummary]
    Cosponsors: ScrapeableField[list[BillSponsorSummary]]
    JointSponsor: ScrapeableField[BillSponsorSummary]
    LegislationTypeName: ScrapeableField[str]
    Pinslip: ScrapeableField[str]
    DocumentText: ScrapeableField[str]
    EmergencyPreamble: ScrapeableField[str]
    RollCalls: ScrapeableField[list[RollCall]]
    Attachments: ScrapeableField[list[Attachment]]
    CommitteeRecommendations: ScrapeableField[list[CommitteeRecommendation]]
    Amendments: ScrapeableField[list[Amendment]]

    document_history: ScrapeableField[list[DocumentHistoryAction]]

    @property
    def cache_id(self) -> str:
        if self.Details:
            return self.Details
        if self.BillNumber:
            return f"{self.GeneralCourtNumber}-{self.BillNumber}"
        if self.DocketNumber:
            return f"{self.GeneralCourtNumber}-{self.DocketNumber}"
        if self.Title:
            return f"{self.GeneralCourtNumber}-{self.Title}"

        raise CacheKeyComputationError(
            f"Could not compute unique Id for Document {self}"
        )

    async def scrape_document_history(self) -> None:
        if self.BillHistory and (
            resp := await request(
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
    return BeautifulSoup((await request(url)).text, "html.parser")


class Hearing(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/Hearings"

    EventId: CacheKey[int]

    # scraped from hearing detail API
    Name: ScrapeableField[str]
    Status: ScrapeableField[str]
    EventDate: ScrapeableField[datetime]
    StartTime: ScrapeableField[datetime]
    Description: ScrapeableField[str]
    HearingHost: ScrapeableField[CommitteeModel]
    HearingAgendas: ScrapeableField[list[AgendaItem]]
    RescheduledHearing: ScrapeableField[list[HearingRescheduled] | HearingRescheduled]
    Location: ScrapeableField[LocationModel]

    # scraped from hearing detail HTML page
    document_urls: ScrapeableField[list[str]]
    testimony_instructions: ScrapeableField[str]

    async def scrape_detail(self, *, use_cache: bool = True) -> None:
        await self.scrape_testimony_instructions()  # NOTE: hack
        await super().scrape_detail(use_cache=use_cache)

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
    Number: CacheKey[int]
    FirstYear: int
    SecondYear: int
    Name: str | None = None


class GeneralLawBase(MALegislatureAPIModelWithExtraScrapableDetails):
    Code: str | None = None
    Name: ScrapeableField[str]

    @property
    def cache_id(self) -> str:
        if self.Details:
            return self.Details
        if self.Code:
            return self.Code
        raise CacheKeyComputationError(
            f"Could not compute unique Id for {type(self).__name__} {self}"
        )


class GeneralLawPart(GeneralLawBase):
    list_endpoint = "/api/Parts"

    FirstChapter: ScrapeableField[int]
    LastChapter: ScrapeableField[int]
    Chapters: ScrapeableField[list[GeneralLawChapter]]


class GeneralLawChapter(GeneralLawBase):
    list_endpoint = "/api/Chapters"

    IsRepealed: ScrapeableField[bool]
    StrickenText: ScrapeableField[str]
    Part: ScrapeableField[GeneralLawPart]
    Sections: ScrapeableField[list[GeneralLawSection]]


class GeneralLawSection(GeneralLawBase):
    ChapterCode: str | None = None

    IsRepealed: ScrapeableField[bool]
    Text: ScrapeableField[str]
    Chapter: ScrapeableField[GeneralLawChapter]
    Part: ScrapeableField[GeneralLawPart]


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
    def cache_id(self) -> str:
        if self.Details:
            return self.Details
        jc = str(self.GeneralCourtNumber)
        jsd = self.JournalSessionDate or ""
        ij = "1" if self.IsJoint else "0"
        if jc and jsd:
            return f"{jc}-{jsd}-{ij}"
        raise CacheKeyComputationError(
            f"Could not compute unique Id for {type(self).__name__} {self}"
        )


class HouseJournal(JournalBase):
    list_endpoint = "/api/HouseJournals"

    DownloadUrl: str | None = None
    SessionDate: datetime | None = None
    RollCallRange: str | None = None


class SenateJournal(JournalBase, MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/SenateJournals"

    DownloadUrl: ScrapeableField[str]
    SessionDate: ScrapeableField[datetime]


class Leadership(MALegislatureAPIModel):
    Member: LegislativeMember | None = None
    Position: CacheKey[str]


class Report(MALegislatureAPIModel):
    list_endpoint = "/api/Reports"

    Date: datetime
    Name: str | None = None
    SubmittedBy: str | None = None
    DownloadUrl: str | None = None

    @property
    def cache_id(self) -> str:
        return str(self.Date.date())


class Session(MALegislatureAPIModel, Event):
    list_endpoint = "/api/Sessions"

    EventId: CacheKey[int]
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
    def cache_id(self) -> str:
        if self.ChapterNumber:
            return f"{self.Year}-{self.ChapterNumber}"
        if self.Title:
            return self.Title
        raise CacheKeyComputationError(
            f"Could not compute unique Id for SessionLaw {self}"
        )


class City(MALegislatureAPIModel):
    list_endpoint = "/api/Documents/SupportedCities"

    name: CacheKey[str]
    documents: ScrapeableField[list[Document]]

    @classmethod
    def response_to_models(cls, resp: httpx.Response) -> Sequence[Self]:
        return [cls(name=i) for i in resp.json()]  # pyright: ignore[reportCallIssue]

    async def scrape_documents(self) -> None:
        url = f"{self.BASE_URL}/api/Cities/{self.name}/Documents"
        resp = await self.request(
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
    for doc in await Document.scrape_list(check_api=False, use_cache=True):
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
