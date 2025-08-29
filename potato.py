from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import asyncio
import os
import hashlib
from glob import glob
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup, Tag
from rich import print
import json
import re
from pydantic import BaseModel, Field
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Generator,
    Awaitable,
    Generic,
    overload,
    Self,
    cast,
)
from typing import TypeVar

T = TypeVar("T")


class ToBeScraped(BaseModel):
    def __bool__(self) -> bool:
        return False


def _json_default(o: Any):
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


# --- Async HTTP client with simple logging --------------------------------------


async def _log_response(response: httpx.Response) -> None:
    print(
        f"[http] {response.request.method} {response.request.url} -> {response.status_code}"
    )


_async_client: httpx.AsyncClient | None = None
_error_log_path: str = "tmp-scrape-errors.jsonl"
_error_log_lock: asyncio.Lock | None = None


async def get_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            event_hooks={
                "response": [_log_response],
            },
        )
    return _async_client


async def aclose_client() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None


async def log_scrape_error(
    *,
    model: str,
    id: str,
    url: str,
    status: int,
    message: str | None = None,
) -> None:
    global _error_log_lock
    if _error_log_lock is None:
        _error_log_lock = asyncio.Lock()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "model": model,
        "id": id,
        "url": url,
        "status": status,
        "message": (message or "").strip(),
    }
    data = json.dumps(entry) + "\n"
    async with _error_log_lock:
        # Use a thread for file I/O to avoid blocking the loop
        await asyncio.to_thread(_append_text, _error_log_path, data)


def _append_text(path: str, data: str) -> None:
    with open(path, "a", encoding="utf-8") as fp:
        fp.write(data)


# Async cached property helper: usage -> value = await self.prop
T_async = TypeVar("T_async")


class async_cached_property(Generic[T_async]):  # noqa: N801
    def __init__(self, func: Callable[[Any], Awaitable[T_async]]):
        self.func = func
        self._attr = f"_{func.__name__}_cached"
        self._lock_attr = f"_{func.__name__}_lock"

    @overload
    def __get__(
        self, instance: None, owner: Any
    ) -> "async_cached_property[T_async]": ...

    @overload
    def __get__(self, instance: Any, owner: Any) -> Awaitable[T_async]: ...

    def __get__(self, instance: Any, owner: Any):  # type: ignore[override]
        if instance is None:
            return self

        async def getter() -> T_async:
            if hasattr(instance, self._attr):
                return getattr(instance, self._attr)
            lock = getattr(instance, self._lock_attr, None)
            if lock is None:
                lock = asyncio.Lock()
                setattr(instance, self._lock_attr, lock)
            async with lock:
                if hasattr(instance, self._attr):
                    return getattr(instance, self._attr)
                val = await self.func(instance)
                setattr(instance, self._attr, val)
                return val

        return getter()


UNSCRAPED = ToBeScraped()
ScrapableField = Annotated[T | None | ToBeScraped, Field(default=UNSCRAPED)]

BASE = "https://malegislature.gov"


class ScrapableModel(BaseModel):
    list_endpoint: ClassVar[str] = "/"
    # Map inbound JSON keys -> model field names (for collisions/aliases)
    field_alias_map: ClassVar[dict[str, str]] = {}

    model_config = {"validate_assignment": True}

    @property
    def scrapable_fields(self) -> list[str]:
        return [
            field
            for field, info in self.__class__.__pydantic_fields__.items()
            if info.default is UNSCRAPED
        ]

    @property
    def unscraped_fields(self) -> list[str]:
        return [
            field
            for field in self.scrapable_fields
            if getattr(self, field) is UNSCRAPED
        ]

    @property
    def id(self) -> str:
        raise NotImplementedError

    @classmethod
    def cache_dirname(cls) -> str:
        return (
            "tmp-"
            # converts the ClassName to class-name (kebab case)
            + re.sub(r"(?<!^)(?=[A-Z])", "-", cls.__name__).lower()
        )

    @classmethod
    def _id_to_filename(cls, *, id: str) -> str:
        # Use a stable, filesystem-safe filename derived from the id
        digest = hashlib.sha256(id.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    @classmethod
    def _instance_cache_path(cls, *, id: str) -> str:
        return os.path.join(cls.cache_dirname(), cls._id_to_filename(id=id))

    @classmethod
    def _load_cached_instance(cls, *, id: str) -> Self | None:
        path = cls._instance_cache_path(id=id)
        if os.path.exists(path):
            with open(path, "r") as fp:
                return cls(**json.load(fp))
        return None

    @classmethod
    def _load_all_cached(cls) -> list[Self]:
        dirname = cls.cache_dirname()
        if not os.path.isdir(dirname):
            # Backward compatibility: load from legacy single-file cache if present
            legacy_file = f"{dirname}.json"
            if os.path.exists(legacy_file):
                try:
                    with open(legacy_file, "r") as fp:
                        return [cls(**i) for i in json.load(fp)]
                except Exception:
                    return []
            return []
        items: list[Self] = []
        for f in glob(os.path.join(dirname, "*.json")):
            with open(f, "r") as fp:
                items.append(cls(**json.load(fp)))
        return items

    @classmethod
    async def scrape_all(cls, check_api: bool = True, concurrency: int = 8) -> None:
        items = await cls.load_all(check_api=check_api)

        sem = asyncio.Semaphore(max(1, concurrency))

        async def runner(item: Self) -> None:
            async with sem:
                await item.scrape()

        await asyncio.gather(*(runner(i) for i in items))

    @classmethod
    async def load_all(
        cls, *, check_api: bool = True, overwrite_from_api: bool = False
    ) -> list[Self]:
        if not check_api:
            return cls._load_all_cached()

        # Fetch the authoritative list from the API
        client = await get_client()
        resp = await client.get(
            f"{BASE}{cls.list_endpoint}", headers={"Accept": "application/json"}
        )
        resp.raise_for_status()

        api_items = [cls(**i) for i in resp.json()]
        results: list[Self] = []
        new_items: list[Self] = []

        cache_dir = cls.cache_dirname()
        os.makedirs(cache_dir, exist_ok=True)

        # Merge: prefer cached instances unless overwrite is requested
        for item in api_items:
            if overwrite_from_api:
                results.append(item)
                continue

            cached = cls._load_cached_instance(id=item.id)
            if cached is not None:
                results.append(cached)
            else:
                results.append(item)
                new_items.append(item)

        # Include cached instances not present in the API list
        if not overwrite_from_api and os.path.isdir(cache_dir):
            api_hash_names = {cls._id_to_filename(id=i.id) for i in api_items}

            all_cached_files = {
                os.path.basename(p) for p in glob(os.path.join(cache_dir, "*.json"))
            }
            items_we_have_but_api_doesnt = all_cached_files - api_hash_names
            if items_we_have_but_api_doesnt:
                for fname in items_we_have_but_api_doesnt:
                    with open(os.path.join(cache_dir, fname), "r") as fp:
                        results.append(cls(**json.load(fp)))

        # Persist cache updates: overwrite all or only new ones
        if overwrite_from_api:
            cls.save_items(results)
        elif new_items:
            cls.save_items(new_items)

        return results

    @classmethod
    async def get(
        cls, *, id: str, not_found_ok: bool = False, check_api: bool = False
    ) -> Self | None:
        # Try direct cache lookup first to minimize I/O
        obj = cls._load_cached_instance(id=id)
        if not obj and check_api:
            await cls.load_all(check_api=True)
            obj = cls._load_cached_instance(id=id)
        if not obj and not not_found_ok:
            raise ValueError(f"Could not find {cls.__name__}({id})")
        return obj

    @classmethod
    def save_items(cls, data: list[Self]) -> None:
        for instance in data:
            instance.save()

    def save(self) -> None:
        os.makedirs(self.cache_dirname(), exist_ok=True)
        jsondata = {
            k: (v.value if isinstance(v, Enum) else v)
            for k, v in self.model_dump().items()
            if v is not UNSCRAPED
        }
        path = self._instance_cache_path(id=self.id)
        with open(path, "w") as fp:
            json.dump(obj=jsondata, fp=fp, indent=2, default=_json_default)

        for field in self.scrapable_fields:
            parsed_value = getattr(self, field)
            if isinstance(parsed_value, ScrapableModel):
                parsed_value.save()
            elif (
                isinstance(parsed_value, list)
                and len(parsed_value) > 0
                and isinstance(parsed_value[0], ScrapableModel)
            ):
                for nested in cast(list[ScrapableModel], parsed_value):
                    nested.save()

    def get_scrapers(
        self, except_for: list[str] | None = None
    ) -> Generator[Callable[[], None], None, None]:
        for field in set(self.unscraped_fields) - set(except_for or []):
            if getter := getattr(self, f"scrape_{field}", None):
                yield getter

    async def scrape(self) -> None:
        for getter in self.get_scrapers():
            # Expect async scrape_* methods; await them
            await getter()  # type: ignore[misc]
            self.save()


class CanBeScrapedFromADetailUrl(ScrapableModel):
    Details: str | None = None

    @property
    def detail_url(self) -> str | None:
        return self.Details

    async def scrape(
        self, except_for: tuple[type[ScrapableModel], ...] = tuple()
    ) -> None:
        async def _scrape(v: ScrapableModel):
            if isinstance(v, CanBeScrapedFromADetailUrl):
                await v.scrape(except_for=except_for + (self.__class__,))
            else:
                await v.scrape()

        if self.detail_url:
            existing = await self.get(id=self.id)
            if existing:
                for field in self.unscraped_fields:
                    setattr(self, field, getattr(existing, field))
            if not self.unscraped_fields:
                return
            client = await get_client()
            response = await client.get(
                self.detail_url, headers={"Accept": "application/json"}
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in {400, 404}:
                    await log_scrape_error(
                        model=self.__class__.__name__,
                        id=self.id,
                        url=self.detail_url,
                        status=status,
                        message=exc.response.text[:500],
                    )
                    # Mark fields as unavailable for this item and continue
                    for field in self.unscraped_fields:
                        setattr(self, field, UNSCRAPED)
                    self.save()
                    return
                raise

            for field, value in cast(dict[str, Any], response.json()).items():
                target = type(self).field_alias_map.get(field, field)
                # Only set if it's a declared field; ignore unknowns
                if target in type(self).__pydantic_fields__:
                    setattr(self, target, value)
            self.save()
        else:
            for field in self.unscraped_fields:
                setattr(self, field, None)
        for field, value in self:
            if isinstance(value, ScrapableModel) and not isinstance(value, except_for):
                await _scrape(value)
            elif (
                isinstance(value, list)
                and len(value) > 0
                and isinstance(value[0], ScrapableModel)
            ):
                for item in cast(list[ScrapableModel], value):
                    await _scrape(item)

        await super().scrape()


class LegislativeMember(CanBeScrapedFromADetailUrl):
    GeneralCourtNumber: int
    MemberCode: str

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
    Committees: ScrapableField[list[Committee]]

    @property
    def id(self) -> str:
        return self.MemberCode


class BillSponsorTypeEnum(Enum):
    LEGISLATIVE_MEMBER = 1
    COMMITTEE = 2
    PUBLIC_REQUEST = 3
    SPECIAL_REQUEST = 4


class BillSponsorSummary(BaseModel):
    Id: str | None
    Name: str
    Type: BillSponsorTypeEnum
    ResponseDate: datetime


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


class Committee(CanBeScrapedFromADetailUrl):
    list_endpoint = "/api/Committees"

    @property
    def id(self) -> str:
        # Prefer CommitteeCode when present; otherwise fall back to Details or a
        # composite using court number and name.
        if self.CommitteeCode:
            return self.CommitteeCode
        if self.Details:
            return self.Details
        name: str | None = None
        if getattr(self, "ShortName", UNSCRAPED) is not UNSCRAPED and self.ShortName:
            name = self.ShortName
        elif getattr(self, "FullName", UNSCRAPED) is not UNSCRAPED and self.FullName:
            name = self.FullName
        if name:
            return f"{self.GeneralCourtNumber}-{name}"
        raise ValueError(f"Could not compute unique Id for Committee {self}")

    CommitteeCode: str | None = None
    GeneralCourtNumber: int

    FullName: ScrapableField[str]
    ShortName: ScrapableField[str]
    Description: ScrapableField[str]
    Branch: ScrapableField[str]
    SenateChairperson: ScrapableField[LegislativeMember]
    HouseChairperson: ScrapableField[LegislativeMember]
    DocumentsBeforeCommittee: ScrapableField[list[Document]]
    ReportedOutDocuments: ScrapableField[list[Document]]
    Hearings: ScrapableField[list[Hearing]]


class CommitteeVote(BaseModel):
    Date: datetime

    Question: str | None = None
    Bill: Document | None = None
    Committee_: Committee | None = Field(default=None, validation_alias="Committee")
    Vote: list[CommitteeVoteRecord] | None = None

    # inbound JSON uses key "Committee"
    field_alias_map: ClassVar[dict[str, str]] = {"Committee": "Committee_"}


class CommitteeRecommendation(BaseModel):
    Action: str | None = None
    FiscalAmounts: list[FiscalAmount] | None = None
    Committee_: Committee | None = Field(default=None, validation_alias="Committee")
    Votes: list[CommitteeVote] | None = None

    field_alias_map: ClassVar[dict[str, str]] = {"Committee": "Committee_"}


class RollCall(CanBeScrapedFromADetailUrl):
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


class Amendment(CanBeScrapedFromADetailUrl):
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
        return f"{BASE}/api/GeneralCourts/{self.GeneralCourtNumber}/Documents/{self.ParentBillNumber}/Branches/{self.Branch}/Amendments/{self.AmendmentNumber}"

    @property
    def id(self) -> str:
        if self.Details:
            return self.Details
        if self.ParentBillNumber and self.Branch and self.AmendmentNumber:
            return f"{self.GeneralCourtNumber}-{self.ParentBillNumber}-{self.Branch}-{self.AmendmentNumber}"
        raise ValueError(f"Could not compute unique Id for Amendment {self}")


class Document(CanBeScrapedFromADetailUrl):
    list_endpoint = "/api/Documents"

    BillNumber: str | None
    IsDocketBookOnly: bool
    GeneralCourtNumber: int
    DocketNumber: str | None = None
    Title: str | None = None
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

    @property
    def id(self) -> str:
        id = self.Details or self.Title
        if not id:
            raise ValueError(f"Could not compute unique Id for Document {self}")
        return id


class AgendaItem(BaseModel):
    Topic: str | None = None
    StartTime: datetime | None = None
    EndTime: datetime | None = None
    DocumentsInAgenda: list[Document] | None = None


class HearingRescheduled(BaseModel):
    Status: str | None = None
    EventDate: datetime | None = None
    StartTime: datetime | None = None
    Location_: Location | None = Field(default=None, validation_alias="Location")


class Location(BaseModel):
    LocationName: str | None = None
    AddressLine1: str | None = None
    AddressLine2: str | None = None
    City: str | None = None
    State: str | None = None
    ZipCode: str | None = None


class Hearing(CanBeScrapedFromADetailUrl):
    list_endpoint = "/api/Hearings"

    EventId: int

    # scraped from hearing detail API
    Name: ScrapableField[str]
    Status: ScrapableField[str]
    EventDate: ScrapableField[datetime]
    StartTime: ScrapableField[datetime]
    Description: ScrapableField[str]
    HearingHost: ScrapableField[Committee]
    HearingAgendas: ScrapableField[list[AgendaItem]]
    RescheduledHearing: ScrapableField[list[HearingRescheduled]]
    Location: ScrapableField[list[Location]]

    # scraped from hearing detail HTML page instead
    document_urls: ScrapableField[list[str]]
    testimony_instructions: ScrapableField[str]

    soup: ClassVar[async_cached_property[BeautifulSoup]]

    @property
    def id(self) -> str:
        # EventId is unique for hearings
        return str(self.EventId)

    @async_cached_property
    async def soup(self) -> BeautifulSoup:
        client = await get_client()
        resp = await client.get(f"{BASE}/Events/Hearings/Detail/{self.EventId}")
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    async def scrape_document_urls(self) -> None:
        """Scrape hearing document urls from the hearing details page.

        Assumptions:
        - Testimony links appear in the first column of the table inside <div id="documentsSection">
        """
        soup = await self.soup
        if docs_div := soup.find(id="documentsSection"):
            assert isinstance(docs_div, Tag)
            self.document_urls = [
                urljoin(BASE, str(a.get("href") or ""))
                for a in docs_div.select(
                    "table.agendaTable tbody tr td:first-child a[href]"
                )
            ]

    async def scrape_testimony_instructions(self) -> None:
        # breakpoint()
        pass


# ------------------------------ Script Entrypoint ------------------------------


async def _main() -> None:
    # Explicit list of models to scrape
    models: list[type[ScrapableModel]] = [Document, Hearing, Committee]
    for cls in models:
        print(f"\nScraping {cls.__name__} from {cls.list_endpoint} ...")
        await cls.scrape_all(check_api=True, concurrency=8)
    await aclose_client()


if __name__ == "__main__":
    asyncio.run(_main())
