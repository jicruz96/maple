from collections import Counter, defaultdict
from typing import Any

import click
from rich import print

from .hearing_testimony_scraper import (
    HearingDocument,
    create_hearing_documents_report,
    scrape_hearing_documents,
)
from .malegislature_api_scraper import (
    CommitteeVote,
    Document,
    LegislativeMember,
    scrape_malegislature_api,
)
from ji_async_http_utils.httpx import run_in_lifespan
from .utils.reports import report_for


@click.group()
def cli() -> None:
    """Utilities for scraping and analyzing hearing details."""
    pass


@click.option(
    "--show",
    type=int,
    default=0,
    help="Print N hearing documents in the report.",
)
@cli.command("hearing-documents-report")
@run_in_lifespan
async def hearing_documents_report(show: int):
    await create_hearing_documents_report(show)


@click.option(
    "--no-cache",
    is_flag=True,
    help="Don't use cache",
)
@cli.command("scrape-hearing-documents")
def scrape_hearing_documents_cmd(no_cache: bool):
    scrape_hearing_documents(use_cache=not no_cache)


cli.command("scrape-api")(scrape_malegislature_api)


@cli.command("see-parsed-testimonies")
def see_parsed_testimonies() -> None:
    print([doc for doc in HearingDocument.load_all_cached() if doc.parsed])


@cli.command("committee-vote-report")
@run_in_lifespan
async def committee_vote_report():
    # 1) Load cached data
    docs = await Document.scrape_list(check_api=False, use_cache=True)
    votes = await CommitteeVote.scrape_list(check_api=False, use_cache=True)
    members_by_id = {
        m.id: m.Name if isinstance(m.Name, str) else m.id
        for m in await LegislativeMember.scrape_list(check_api=False, use_cache=True)
    }

    # 2) Number of unique committee recommendations
    per_action = defaultdict[str, int](int)
    for doc in docs:
        if isinstance(doc.CommitteeRecommendations, list):
            for rec in doc.CommitteeRecommendations:
                per_action[rec.Action.strip() if rec.Action else "Unknown"] += 1

    # 3) votes per legislature branch (inferred from committee code)
    per_branch = Counter(
        [
            {"S": "Senate", "H": "House", "J": "Joint"}.get(cc[0], cc)
            for cc in [
                vote.Committee.CommitteeCode
                if vote.Committee and vote.Committee.CommitteeCode
                else "Unknown"
                for vote in votes
            ]
        ]
    )

    # 4) votes per committee
    per_committee = Counter(
        [v.Committee.id if v.Committee else "Unknown" for v in votes]
    )

    # 5) votes per bill
    per_bill = Counter([v.Bill.id if v.Bill else "Unknown" for v in votes])

    # 6) Votes per legislative member
    votes_by_member: Counter[str] = Counter()

    for vote in votes:
        for record in vote.Vote or []:
            for vote_list in [
                record.Favorable,
                record.Adverse,
                record.ReserveRight,
                record.NoVoteRecorded,
            ]:
                for m in vote_list or []:
                    votes_by_member[members_by_id[m.id]] += 1

    def top(counter: Counter[Any], n: int = 20) -> list[tuple[Any, int]]:
        return counter.most_common(n)

    print("Committee Votes Report")
    print(
        {
            "docs_with_recs": report_for(
                docs,
                where=lambda doc: bool(doc.CommitteeRecommendations),
                show=0,
            ),
            "unique_recommendation_actions": {
                "count": len(per_action),
                "actions": per_action,
            },
            "recommendations_per_branch_top": top(per_branch, 10),
            "recommendations_per_committee_top": top(per_committee, 200),
            "recommendations_per_bill_top": top(per_bill, 20),
            "votes_per_member": top(votes_by_member, 2000),
        }
    )


if __name__ == "__main__":
    cli()
