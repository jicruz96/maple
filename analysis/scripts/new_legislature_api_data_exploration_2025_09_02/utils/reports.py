from typing import Any, Callable, Sequence, TypedDict


def pct(part: int, whole: int) -> str:
    return "0.0%" if whole == 0 else f"{(part / whole) * 100:.1f}%"


class Report(TypedDict, total=False):
    count: int
    pct: str
    items: list[Any]


def report_for(
    docs: Sequence[Any],
    *,
    where: Callable[[Any], bool],
    show: int = 20,
) -> Report:
    items = list(filter(where, docs))
    report = Report(
        count=len(items),
        pct=pct(len(items), len(docs)),
    )
    if show:
        report["items"] = items[:show]
    return report
