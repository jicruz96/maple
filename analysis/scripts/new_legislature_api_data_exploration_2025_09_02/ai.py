from abc import abstractmethod
from functools import lru_cache
import asyncio
import hashlib
import json
from pathlib import Path
from typing import ClassVar, TypeVar, Sequence
from tqdm import tqdm

from openai import AsyncOpenAI
from openai.types import ChatModel
from pydantic import BaseModel, ValidationError


class LLMOutputModel(BaseModel):
    model_config = {"use_attribute_docstrings": True}


class LLMInputModel(BaseModel):
    llm_response_model: ClassVar[type[LLMOutputModel] | None] = None
    parsed: LLMOutputModel | None = None

    @property
    def can_ask_llm(self) -> bool:
        return self.llm_response_model is not None

    @property
    @abstractmethod
    def system(self) -> str | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def user(self) -> str | None:
        raise NotImplementedError

    async def parse(self, use_cache: bool = True) -> LLMOutputModel | None:
        if (
            not self.can_ask_llm
            or not (llm_response_model := self.llm_response_model)
            or not (system := self.system)
            or not (user := self.user)
        ):
            return

        def get_cache_file_path() -> Path:
            m = hashlib.sha256()
            m.update(system.encode())
            m.update(user.encode())
            m.update(str(llm_response_model.model_json_schema()).encode())
            cache_hash = m.hexdigest()
            cache_dir = Path(".ai_cache")
            cache_dir.mkdir(exist_ok=True)
            return cache_dir / f"{cache_hash}.json"

        cache_file = get_cache_file_path()
        if use_cache and cache_file.exists():
            with cache_file.open() as f:
                data = json.load(f)["data"]
            try:
                parsed = llm_response_model(**data)
                self.parsed = parsed
                return parsed
            except ValidationError:
                print(f"Cache data for {cache_file} is invalid, re-parsing...")
        data = await ask_chatgpt(
            system=system,
            user=user,
            output_model=llm_response_model,
        )
        self.parsed = data
        with cache_file.open("w") as f:
            json.dump(
                {
                    "data": data.model_dump(mode="json"),
                    "system": system,
                    "user": user,
                },
                f,
            )
        return data


T = TypeVar("T", bound=BaseModel)
M = TypeVar("M", bound="LLMInputModel")


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(max_retries=3)


async def ask_chatgpt(
    *,
    system: str,
    user: str,
    output_model: type[T],
    model: ChatModel = "gpt-5-mini",
) -> T:
    if data := (
        await get_openai_client().responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=output_model,
        )
    ).output_parsed:
        return data
    raise ValueError(
        f"Could not extract {output_model.__name__} information from text: {user}"
    )


async def parse_all(
    items: Sequence[M],
    *,
    concurrency: int = 5,
    use_cache: bool = True,
    raise_errors: bool = True,
    show_progress: bool = True,
    desc: str = "Parsing",
) -> list[M]:
    """Parse many LLMInputModel items concurrently with bounded concurrency.

    Returns the subset of items that produced a non-None parsed result. Each
    item is updated in-place (its `parsed` field is set).
    """
    sem = asyncio.Semaphore(max(1, concurrency))
    pbar = tqdm(total=len(items), desc=desc, unit="item") if show_progress else None

    async def runner(item: M) -> M | None:
        async with sem:
            try:
                await item.parse(use_cache=use_cache)
                return item
            except Exception:
                if raise_errors:
                    raise
                return None
            finally:
                if pbar is not None:
                    pbar.update(1)

    try:
        results = await asyncio.gather(*(runner(i) for i in items))
    finally:
        if pbar is not None:
            pbar.close()
    return [r for r in results if r and r.parsed]
