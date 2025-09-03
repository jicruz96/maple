from typing import Callable, Generic, TypedDict, TypeVar

T = TypeVar("T")


def pct(part: int, whole: int) -> str:
    return "0.0%" if whole == 0 else f"{(part / whole) * 100:.1f}%"


class Report(TypedDict, Generic[T], total=False):
    count: int
    pct: str
    items: list[T]


def report_for(
    docs: list[T],
    *,
    where: Callable[[T], bool],
    show: int = 20,
) -> Report[T]:
    items = list(filter(where, docs))
    report = Report[T](
        count=len(items),
        pct=pct(len(items), len(docs)),
    )
    if show:
        report["items"] = items[:show]
    return report
