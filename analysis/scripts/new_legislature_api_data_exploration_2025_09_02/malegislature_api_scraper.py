from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Sequence
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import Field
from pydantic_cacheable_model import CacheKey
from typing_extensions import Self

from ji_async_http_utils.aiohttp import request
from .utils.base_model import BaseModel, CacheableModel
from pydantic_scrapeable_api_model import (
    CustomScrapeField,
    DetailField,
    ScrapeableApiModel as PydanticScrapeableApiModel,
)
from pydantic_cacheable_model import CacheKeyComputationError
from async_lru import alru_cache


class MALegislatureAPIModel(PydanticScrapeableApiModel, CacheableModel):
    CACHE_ROOT = "malegislature-api-cache"
    BASE_URL = "https://malegislature.gov"


class MALegislatureAPIModelWithExtraScrapableDetails(MALegislatureAPIModel):
    Details: str | None = None

    @property
    def detail_endpoint(self) -> str | None:
        if self.Details:
            return self.Details.replace("http://", "https://")
        return None


class LegislativeMember(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/LegislativeMembers"

    MemberCode: CacheKey[str]
    GeneralCourtNumber: int

    Name: DetailField[str | None]
    LeadershipPosition: DetailField[str | None]
    Branch: DetailField[str | None]
    District: DetailField[str | None]
    Party: DetailField[str | None]
    EmailAddress: DetailField[str | None]
    RoomNumber: DetailField[str | None]
    PhoneNumber: DetailField[str | None]
    FaxNumber: DetailField[str | None]
    SponsoredBills: DetailField[list[Document] | None]
    CoSponsoredBills: DetailField[list[Document] | None]
    Committees: DetailField[list[CommitteeModel] | None]


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

    FullName: DetailField[str | None]
    ShortName: DetailField[str | None]
    Description: DetailField[str | None]
    Branch: DetailField[str | None]
    SenateChairperson: DetailField[LegislativeMember | None]
    HouseChairperson: DetailField[LegislativeMember | None]
    DocumentsBeforeCommittee: DetailField[list[Document] | None]
    ReportedOutDocuments: DetailField[list[Document] | None]
    Hearings: DetailField[list[Hearing] | None]

    @property
    def cache_key(self) -> str:
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
    def cache_key(self) -> str:
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

    Branch: DetailField[str | None]
    QuestionMotion: DetailField[str | None]
    Yeas: DetailField[list[LegislativeMember] | None]
    Nays: DetailField[list[LegislativeMember] | None]
    Absent: DetailField[list[LegislativeMember] | None]
    DownloadUrl: DetailField[str | None]

    @property
    def cache_key(self) -> str:
        return f"{self.GeneralCourtNumber}-{self.RollCallNumber}"


class Amendment(MALegislatureAPIModelWithExtraScrapableDetails):
    GeneralCourtNumber: int
    AmendmentNumber: str | None = None
    ParentBillNumber: str | None = None
    Branch: str | None = None

    Bill: DetailField[Document | None]
    Sponsor: DetailField[BillSponsorSummary | None]
    Category: DetailField[str | None]
    Action: DetailField[str | None]
    RollCall: DetailField[list[RollCall] | None]
    Title: DetailField[str | None]
    RedraftNumber: DetailField[int | None]
    IsFurther: DetailField[bool | None]
    Text: DetailField[str | None]

    @property
    def detail_endpoint(self) -> str | None:
        if not (self.ParentBillNumber and self.Branch and self.AmendmentNumber):
            return None
        return f"{self.BASE_URL}/api/GeneralCourts/{self.GeneralCourtNumber}/Documents/{self.ParentBillNumber}/Branches/{self.Branch}/Amendments/{self.AmendmentNumber}"

    @property
    def cache_key(self) -> str:
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
    PrimarySponsor: DetailField[BillSponsorSummary | None]
    Cosponsors: DetailField[list[BillSponsorSummary] | None]
    JointSponsor: DetailField[BillSponsorSummary | None]
    LegislationTypeName: DetailField[str | None]
    Pinslip: DetailField[str | None]
    DocumentText: DetailField[str | None]
    EmergencyPreamble: DetailField[str | None]
    RollCalls: DetailField[list[RollCall] | None]
    Attachments: DetailField[list[Attachment] | None]
    CommitteeRecommendations: DetailField[list[CommitteeRecommendation] | None]
    Amendments: DetailField[list[Amendment] | None]

    document_history: DetailField[list[DocumentHistoryAction]] = CustomScrapeField(
        "scrape_document_history"
    )

    @property
    def cache_key(self) -> str:
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

    async def scrape_document_history(
        self, session: aiohttp.ClientSession
    ) -> list[DocumentHistoryAction]:
        if self.BillHistory and (
            resp := await self.request(
                id="scrape_document_history",
                url=self.BillHistory,
                headers={"Accept": "application/json"},
                raise_on_status_except_for=[404],
                session=session,
            )
        ):
            return [DocumentHistoryAction(**i) for i in (await resp.json())]
        return []


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


@alru_cache(maxsize=1)
async def get_soup(url: str, session: aiohttp.ClientSession) -> BeautifulSoup:
    return BeautifulSoup(
        (await (await request(url=url, session=session)).read()).decode(), "html.parser"
    )


class Hearing(MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/Hearings"

    EventId: CacheKey[int]

    # scraped from hearing detail API
    Name: DetailField[str | None]
    Status: DetailField[str | None]
    EventDate: DetailField[datetime | None]
    StartTime: DetailField[datetime | None]
    Description: DetailField[str | None]
    HearingHost: DetailField[CommitteeModel | None]
    HearingAgendas: DetailField[list[AgendaItem] | None]
    RescheduledHearing: DetailField[
        list[HearingRescheduled] | HearingRescheduled | None
    ]
    Location: DetailField[LocationModel | None]

    # scraped from hearing detail HTML page
    document_urls: DetailField[list[str]] = CustomScrapeField("scrape_document_urls")

    @property
    def webpage_url(self) -> str:
        return f"{self.BASE_URL}/Events/Hearings/Detail/{self.EventId}"

    async def scrape_document_urls(self, session: aiohttp.ClientSession) -> list[str]:
        """Scrape hearing document urls from the hearing details page.

        Assumptions:
        - Testimony links appear in the first column of the table inside <div id="documentsSection">
        """
        soup = await get_soup(self.webpage_url, session=session)
        if docs_div := soup.find(id="documentsSection"):
            assert isinstance(docs_div, Tag)
            return [
                urljoin(self.BASE_URL, str(a.get("href") or ""))
                for a in docs_div.select(  # pyright: ignore[reportUnknownMemberType]
                    "table.agendaTable tbody tr td:first-child a[href]"
                )
            ]
        return []


class GeneralCourt(MALegislatureAPIModel):
    Number: CacheKey[int]
    FirstYear: int
    SecondYear: int
    Name: str | None = None


class GeneralLawBase(MALegislatureAPIModelWithExtraScrapableDetails):
    Code: str | None = None
    Name: DetailField[str | None]

    @property
    def cache_key(self) -> str:
        if self.Details:
            return self.Details
        if self.Code:
            return self.Code
        raise CacheKeyComputationError(
            f"Could not compute unique Id for {type(self).__name__} {self}"
        )


class GeneralLawPart(GeneralLawBase):
    list_endpoint = "/api/Parts"

    FirstChapter: DetailField[int | None]
    LastChapter: DetailField[int | None]
    Chapters: DetailField[list[GeneralLawChapter] | None]


class GeneralLawChapter(GeneralLawBase):
    list_endpoint = "/api/Chapters"

    IsRepealed: DetailField[bool | None]
    StrickenText: DetailField[str | None]
    Part: DetailField[GeneralLawPart | None]
    Sections: DetailField[list[GeneralLawSection] | None]


class GeneralLawSection(GeneralLawBase):
    ChapterCode: str | None = None

    IsRepealed: DetailField[bool | None]
    Text: DetailField[str | None]
    Chapter: DetailField[GeneralLawChapter | None]
    Part: DetailField[GeneralLawPart | None]


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
    def cache_key(self) -> str:
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

    @classmethod
    async def scrape_list(
        cls,
        check_api: bool | str,
        *,
        use_cache: bool,
        scrape_details: bool = True,
        session: aiohttp.ClientSession | None = None,
        raise_on_status_except_for: Sequence[int] | None = None,
    ) -> Sequence[Self]:
        return await super().scrape_list(
            check_api,
            use_cache=use_cache,
            scrape_details=scrape_details,
            raise_on_status_except_for=raise_on_status_except_for or [500],
            session=session,
        )


class HouseJournal(JournalBase):
    list_endpoint = "/api/HouseJournals"

    DownloadUrl: str | None = None
    SessionDate: datetime | None = None
    RollCallRange: str | None = None


class SenateJournal(JournalBase, MALegislatureAPIModelWithExtraScrapableDetails):
    list_endpoint = "/api/SenateJournals"

    DownloadUrl: DetailField[str | None]
    SessionDate: DetailField[datetime | None]


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
    def cache_key(self) -> str:
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
    def cache_key(self) -> str:
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
    documents: DetailField[list[Document]] = CustomScrapeField("scrape_documents")

    @classmethod
    async def process_list_response(
        cls, resp: aiohttp.ClientResponse
    ) -> Sequence[Self]:
        return [cls(name=i) for i in (await resp.json())]

    async def scrape_documents(self) -> list[Document]:
        url = f"{self.BASE_URL}/api/Cities/{self.name}/Documents"
        async with aiohttp.ClientSession() as session:
            resp = await self.request(
                id=self.id,
                url=url,
                headers={"Accept": "application/json"},
                raise_on_status_except_for=[400, 404],
                session=session,
            )

        if resp is None:
            return []

        return [Document(**i) for i in await resp.json()]


async def scrape_malegislature_api() -> None:
    # Ensure verbose logging for this scraper run
    import logging

    logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    await MALegislatureAPIModel.run(use_cache=True, check_api=True)
    async with aiohttp.ClientSession() as session:
        await Leadership.scrape_list(
            "/api/Branches/House/Leadership",
            use_cache=True,
            session=session,
        )
        await Leadership.scrape_list(
            "/api/Branches/Senate/Leadership",
            use_cache=True,
            session=session,
        )

        seen: set[str] = set()
        successful = 0
        for doc in await Document.scrape_list(
            check_api=False, use_cache=True, session=session
        ):
            if not isinstance(doc.CommitteeRecommendations, list):
                continue
            for rec in doc.CommitteeRecommendations:
                if (
                    rec.Committee
                    and rec.Committee.CommitteeCode
                    and doc.BillNumber
                    and doc.GeneralCourtNumber
                    and (
                        url
                        := f"/api/Committees/{rec.Committee.CommitteeCode}/Documents/{doc.BillNumber}/CommitteeVotes"
                    )
                    not in seen
                ):
                    seen.add(url)
                    try:
                        await CommitteeVote.scrape_list(
                            url,
                            use_cache=True,
                            session=session,
                        )
                        successful += 1
                    except aiohttp.ClientResponseError as exc:
                        if exc.code != 400:
                            raise

    print(f"{successful}/{len(seen)}")


if __name__ == "__main__":
    asyncio.run(scrape_malegislature_api())
