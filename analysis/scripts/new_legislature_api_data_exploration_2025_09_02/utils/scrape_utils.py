from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from glob import glob
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Literal,
    Sequence,
    TypeVar,
)
from typing_extensions import Self

import httpx
from pydantic import Field
from pydantic.main import IncEx
from rich import print  # pyright: ignore[reportUnusedImport]  # noqa: F401

from .async_utils import http_get
from .base_model import BaseModel
from .base_model import CacheableModel

T = TypeVar("T")


class UnscrapedType(BaseModel):
    def __bool__(self) -> bool:
        return False

    def __len__(self) -> int:
        return 0


ScrapableField = Annotated[
    T | None | UnscrapedType, Field(default_factory=UnscrapedType)
]

_error_log_lock: asyncio.Lock | None = None


class ScrapableModel(CacheableModel):
    BASE_URL: ClassVar[str] = ""
    list_endpoint: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any):
        assert bool(cls.BASE_URL)  # enforce existence of a url
        super().__init_subclass__(**kwargs)

    def unscraped_fields(self) -> list[str]:
        return [field for field, value in self if isinstance(value, UnscrapedType)]

    @classmethod
    async def scrape_all(
        cls,
        check_api: bool | str = True,
        *,
        use_cache: bool = True,
        concurrency: int = 10,
    ) -> None:
        items = await cls.fetch_all(check_api=check_api, use_cache=use_cache)

        sem = asyncio.Semaphore(max(1, concurrency))

        async def runner(item: Self) -> None:
            async with sem:
                await item.scrape(use_cache=use_cache)

        await asyncio.gather(*(runner(i) for i in items))

    @classmethod
    def _response_to_models(cls, resp: httpx.Response) -> Sequence[Self]:
        return [cls(**i) for i in resp.json()]

    @classmethod
    async def fetch_all(
        cls, check_api: bool | str, *, use_cache: bool | str
    ) -> list[Self]:
        if isinstance(check_api, str) and cls.list_endpoint:
            raise ValueError(
                f"cannot overwride {cls.__name__}(list_endpoint={cls.list_endpoint})"
            )
        existing = (
            {} if not use_cache else {item.id: item for item in cls.load_all_cached()}
        )
        if not check_api:
            return list(existing.values())

        if not cls.list_endpoint and not isinstance(check_api, str):
            raise ValueError(
                f"Cannot check API for {cls.__name__} because list_endpoint is "
                "not set and check_api did not provide an override"
            )
        endpoint = cls.list_endpoint if isinstance(check_api, bool) else check_api
        assert isinstance(endpoint, str)
        url = cls.BASE_URL + endpoint
        # print(f"\nScraping {cls.__name__} from {url!r} ...")
        resp = await cls.http_get(
            id="fetch_all",
            url=url,
            headers={"Accept": "application/json"},
            raise_on_status_except_for=[500, 502, 503, 504],
        )
        if resp is None:
            return list(existing.values())

        models = [existing.get(item.id, item) for item in cls._response_to_models(resp)]

        for model in models:
            model.cache()

        if cls.list_endpoint:
            existing_cache_files = set(
                glob(os.path.join(cls.cache_dir_path(), "*.json"))
            )
            stale_data = existing_cache_files - {m.cache_path for m in models}
            for fpath in stale_data:
                os.remove(fpath)

        return models

    @classmethod
    async def get(
        cls, *, id: str, not_found_ok: bool = False, check_api: bool = False
    ) -> Self | None:
        obj = cls.load(cache_id=id)
        if not obj and check_api:
            await cls.fetch_all(check_api=True, use_cache=True)  # hack
            obj = cls.load(cache_id=id)
        if not obj and not not_found_ok:
            raise ValueError(f"Could not find {cls.__name__}({id})")
        return obj

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        return {
            k: v
            for k, v in super()
            .model_dump(
                mode=mode,
                include=include,
                exclude=exclude,
                context=context,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                round_trip=round_trip,
                warnings=warnings,
                fallback=fallback,
                serialize_as_any=serialize_as_any,
            )
            .items()
            if k not in self.unscraped_fields()
        }

    async def scrape(self, *, use_cache: bool = True) -> None:
        if use_cache and (existing := await self.get(id=self.id, not_found_ok=True)):
            for field, val in existing:
                if field in self.unscraped_fields():
                    setattr(self, field, val)
        for field in self.unscraped_fields():
            if getter := getattr(self, f"scrape_{field}", None):
                await getter()
        self.cache()

    @classmethod
    async def log_scrape_error(cls, **data: str | int | None) -> None:
        row: dict[str, str | int | None] = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "model": cls.__name__,
            **data,
        }
        log_filepath = os.path.join(cls.CACHE_ROOT, "scrape-errors.jsonl")

        def _log_error() -> None:
            with open(log_filepath, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(row) + "\n")

        global _error_log_lock
        if _error_log_lock is None:
            _error_log_lock = asyncio.Lock()
        async with _error_log_lock:
            await asyncio.to_thread(_log_error)

    @classmethod
    async def http_get(
        cls,
        *,
        id: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        raise_on_status_except_for: Sequence[int] | None = None,
    ) -> httpx.Response | None:
        resp = await http_get(
            url,
            headers=headers or {},
            params=params or {},
            raise_on_status_except_for=raise_on_status_except_for,
        )
        if not resp.is_success:
            await cls.log_scrape_error(
                id=id,
                url=url,
                status=resp.status_code,
                message=resp.text[:500],
            )
            return None
        return resp
