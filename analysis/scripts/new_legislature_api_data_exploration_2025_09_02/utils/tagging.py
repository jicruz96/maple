from abc import abstractmethod
from functools import cached_property
import re
from typing import Callable, ClassVar

from pydantic import BaseModel, computed_field

TagMatcher = Callable[["TaggableModel"], bool]
TagPattern = str | re.Pattern[str]


class TaggableModel(BaseModel):
    TAG_PATTERNS: ClassVar[dict[str, TagMatcher]] = {}

    @computed_field
    @cached_property
    def tags(self) -> list[str]:
        return [tag for tag, matcher in self.TAG_PATTERNS.items() if matcher(self)]

    @abstractmethod
    def matches_pattern(self, pattern: TagPattern) -> bool:
        raise NotImplementedError


def keyword_regex(s: str) -> re.Pattern[str]:
    # Case-insensitive, allow underscore/dash or word boundary before/after
    return re.compile(rf"(?i)(?:\b|_|-){re.escape(s)}(?:\b|_|-)", re.IGNORECASE)


def ShouldMatch(*patterns: TagPattern) -> TagMatcher:
    return lambda doc: all(doc.matches_pattern(p) for p in patterns)


def ShouldMatchOneOf(*patterns: TagPattern) -> TagMatcher:
    return lambda doc: any(doc.matches_pattern(p) for p in patterns)
