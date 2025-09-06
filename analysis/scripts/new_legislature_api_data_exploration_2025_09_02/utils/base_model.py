from pydantic import BaseModel as PydanticBaseModel
from pydantic_cacheable_model import CacheableModel as PydanticCacheableModel
from pydantic_scrapeable_api_model import (
    ScrapeableApiModel as PydanticScrapeableApiModel,
)


class BaseModel(PydanticBaseModel):
    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }


class CacheableModel(BaseModel, PydanticCacheableModel):
    @property
    def id(self) -> str:
        return self.cache_key


class ScrapeableApiModel(PydanticScrapeableApiModel, CacheableModel):
    pass
