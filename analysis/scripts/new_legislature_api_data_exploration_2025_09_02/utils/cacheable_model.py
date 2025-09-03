from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from enum import Enum
from glob import glob
from typing import Any, ClassVar, Self

from pydantic import ValidationError
from rich import print

from .base_model import BaseModel


def _json_default(o: Any):
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


class CacheableModel(BaseModel):
    CACHE_ROOT: ClassVar[str] = ".cache"

    @property
    def id(self) -> str:
        raise NotImplementedError

    @classmethod
    def cache_dirname(cls) -> str:
        model_dir = re.sub(
            r"(?<!^)(?=[A-Z])", "-", cls.__name__.replace("Model", "")
        ).lower()
        return os.path.join(cls.CACHE_ROOT, model_dir)

    @classmethod
    def _id_to_filename(cls, *, id: str) -> str:
        digest = hashlib.sha256(id.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    @classmethod
    def get_cache_path(cls, *, id: str) -> str:
        return os.path.join(cls.cache_dirname(), cls._id_to_filename(id=id))

    @classmethod
    def load(cls, *, id: str) -> Self | None:
        path = cls.get_cache_path(id=id)
        if os.path.exists(path):
            with open(path, "r") as fp:
                data = json.load(fp)
            try:
                return cls(**data)
            except ValidationError as e:
                print(f"[warning] Could not load cached {cls.__name__}({id}): {e}")
                breakpoint()
        return None

    @classmethod
    def load_all_cached(cls) -> list[Self]:
        dirname = cls.cache_dirname()
        if not os.path.isdir(dirname):
            return []
        items: list[Self] = []
        for f in glob(os.path.join(dirname, "*.json")):
            with open(f, "r") as fp:
                items.append(cls(**json.load(fp)))
        return items

    @property
    def cache_path(self) -> str:
        return self.get_cache_path(id=self.id)

    def cache(self) -> None:
        os.makedirs(self.cache_dirname(), exist_ok=True)
        with open(self.cache_path, "w") as fp:
            json.dump(
                obj=self.model_dump(mode="json"),
                fp=fp,
                indent=2,
                default=_json_default,
            )
