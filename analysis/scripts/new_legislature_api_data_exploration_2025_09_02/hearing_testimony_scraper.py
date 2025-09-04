from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import Field
from rich import print
from tqdm import tqdm

from .ai import LLMInputModel, LLMOutputModel, parse_all
from .malegislature_api_scraper import Hearing
from .utils.async_utils import http_get, run_in_lifespan
from .utils.base_model import CacheableModel
from .utils.doc_reader import DocumentRef
from .utils.reports import report_for
from .utils.tagging import ShouldMatch, ShouldMatchOneOf, TaggableModel, keyword_regex

BILL_ID_PAT = r"[HS]\.?\d+"
DASH_SEP_PAT = r"\s+[-–]\s+"
OPTIONAL_DASH_SEP_PAT = r"\s*[-–]?\s*"


class ParsedWrittenTestimony(LLMOutputModel):
    testimony: str
    """The testimony text, exactly as it appeared."""

    position: Literal["oppose", "endorse", "neutral"]
    """The position the testimony is taking on the bill or issue."""

    house_bill_ids: list[str]
    """
    The house bill IDs the testimony is for. 
    
    House bill numbeIDsrs will resemble the pattern 'H.?\\d+' or a similar variant.

    Bill ID strings must be written in the form 'H\\d+'.
    """

    senate_bill_ids: list[str]
    """
    The senate bill ID the testimony is for.
    
    Senate bill IDs will resemble the pattern 'S.?\\d+' or a similar variant.
    
    Senate Bill ID strings must be written in the form 'H\\d+'.
    """

    testimony_topic: str | None = None
    """
    A brief phrase explaining what topic the testimony is about.
    
    This is a fallback solely to be used for when no bill IDs can be inferred from the testimony.
    """


class ParsedTestimonyFile(LLMOutputModel):
    authors: list[str]
    """
    The individual(s) who submitted the testimony. If the text does not specify any individual 
    authors, then this field's list should be empty.
    """

    organizations: list[str]
    """
    The organization(s) that submitted or sponsored the testimony. If the text does not specify an author 
    organization, then this field's list should be empty.
    """

    testimonies: list[ParsedWrittenTestimony]
    """A list of testimonies that appear in the file."""

    submission_date: datetime | None
    """The date the testimony was written/submited, if explicitly stated"""


class HearingDocument(TaggableModel, CacheableModel, LLMInputModel):
    model_config = {"extra": "ignore"}
    TAG_PATTERNS = {
        "HearingPacket": ShouldMatch(r"Hearing Packet"),
        "Testimony": ShouldMatchOneOf(
            r"Written Testimony",
            keyword_regex(r"Oppose"),
            keyword_regex(r"Neutral"),
            keyword_regex(r"Support"),
        ),
        "BillSummary": ShouldMatchOneOf(
            keyword_regex(r"Summary"),
            # there's one instance of this misspelled title 👇
            keyword_regex(r"Bill Sumary"),
            # there's one instance of this misspelled title 👇
            r"Smmary",
        ),
        "BillSummaries": ShouldMatchOneOf(
            re.compile(r"Summaries", re.IGNORECASE),
        ),
        "BillId_AnAct": ShouldMatchOneOf(
            rf"^{BILL_ID_PAT}{OPTIONAL_DASH_SEP_PAT}An Act\b",
        ),
        "BillId_Resolve": ShouldMatchOneOf(
            rf"^{BILL_ID_PAT}{OPTIONAL_DASH_SEP_PAT}Resolve\b",
        ),
        "JustBillId": ShouldMatchOneOf(
            re.compile(rf"^\s*{BILL_ID_PAT}\s*$", re.IGNORECASE),
            # there's one instance of a misspelled title 👇
            r"S\.\.1711",
        ),
        "BillId_PlusSomethingElse": ShouldMatchOneOf(
            re.compile(rf"^{BILL_ID_PAT}{DASH_SEP_PAT}.+", re.IGNORECASE),
        ),
        "CommitteeVotes": ShouldMatchOneOf(
            rf"^{BILL_ID_PAT}{DASH_SEP_PAT}Votes of House Committee Members",
            rf"Votes of House Committee Members, {BILL_ID_PAT}",
            rf"^{BILL_ID_PAT}{DASH_SEP_PAT}House Committee Members Votes",
        ),
        "MeetingMinutes": ShouldMatchOneOf(
            r"Meeting Minutes$",
            r"Com Minutes$",
        ),
    }

    url: str = Field(repr=False)
    attachment_id: int
    title: str
    file_extension: str

    llm_response_model = ParsedTestimonyFile

    @property
    def id(self) -> str:
        return str(self.attachment_id)

    @property
    def system(self) -> str:
        return """
USER PROMPT DESCRIPTION:
The user will provide you with a the name and text of a attachment from a hearing of the Boston State Legislature.

The file attachment is supposed to be written testimony for one or more bills or issues being discussed in the hearing.

YOUR TASK:

Extract testimonies verbatim from the text and infer related metadata.

USER PROMPT FORMAT:

```
Title: <title>
Text:

<Text>
```
""".strip()

    @property
    def is_testimony(self) -> bool:
        return "Testimony" in self.tags

    @property
    def can_ask_llm(self) -> bool:
        return self.is_testimony and self.llm_response_model is not None

    @property
    def user(self) -> str | None:
        if self.is_testimony:
            return f"Title: {self.title}\nText:\n\n{self.ref.file_text}"

    @property
    def ref(self) -> DocumentRef:
        if not os.path.exists(self.filepath):
            raise ValueError(
                f"{self.filepath!r} doesn't exist. Hint: run .download() first."
            )
        return DocumentRef(self.filepath, use_text_backup=True)

    @property
    def filepath(self) -> str:
        return str(self.cache_path).removesuffix(".json") + self.file_extension

    def matches_pattern(self, pattern: str | re.Pattern[str]) -> bool:
        return bool(re.search(pattern, self.title))

    @classmethod
    def from_url(cls, url: str) -> "HearingDocument":
        if "%2B" in url:
            # handle bug in malegislature.gov downloads where
            # '+' signs in file title cause a 404.
            # oddly enough, the API  works if we remove them.
            url = url.replace("%2B", "")

        parsed = urlparse(url)
        q = parse_qs(parsed.query)
        return cls(
            url=url,
            attachment_id=int(q["attachmentId"][0]),
            title=q["Title"][0],
            file_extension=q["fileExtension"][0],
        )

    async def download(self, overwrite: bool = False) -> None:
        if overwrite or not os.path.exists(self.filepath):
            response = await http_get(self.url)
            content = response.read()
            with open(self.filepath, "wb") as fp:
                fp.write(content)


async def get_hearing_documents(*, check_api: bool, use_cache: bool):
    hearings = await Hearing.fetch_all(check_api=check_api, use_cache=use_cache)
    docs: list[HearingDocument] = []
    for hearing in hearings:
        if isinstance(hearing.document_urls, list):
            docs.extend(map(HearingDocument.from_url, hearing.document_urls))
    docs.sort(key=lambda doc: doc.id)
    return docs


async def create_hearing_documents_report(show: int):
    docs = await get_hearing_documents(check_api=False, use_cache=True)
    print("[bold]Hearing Documents Report[/bold]")
    print(
        {
            "total": len(docs),
            "file_extension_counts": Counter(doc.file_extension for doc in docs),
            "testimonies with scans": report_for(
                docs,
                where=lambda doc: doc.is_testimony and bool(doc.ref.ocr_text),
                show=show,
            ),
            "parsed": report_for(
                docs,
                where=lambda doc: doc.can_ask_llm,
                show=show,
            ),
            "tags": {
                "counts": {
                    tag: report_for(
                        docs,
                        where=lambda doc: tag in doc.tags,
                        show=0,
                    )
                    for tag in HearingDocument.TAG_PATTERNS
                },
                "unmatched": report_for(
                    docs,
                    where=lambda doc: not doc.tags,
                    show=show,
                ),
            },
        },
    )


@run_in_lifespan
async def scrape_hearing_documents(use_cache: bool):
    docs = [
        doc
        for doc in await get_hearing_documents(check_api=True, use_cache=use_cache)
        if doc.can_ask_llm
    ]
    for doc in tqdm(docs, desc="Downloading Hearing Documents"):
        # Ensure the document exists on disk before parsing
        await doc.download()
        # and save a text backup of it so it's cheaper to extract text in future runs
        doc.ref.save_text_backup()

    for doc in await parse_all(docs):
        doc.cache()


if __name__ == "__main__":
    scrape_hearing_documents(use_cache=True)
