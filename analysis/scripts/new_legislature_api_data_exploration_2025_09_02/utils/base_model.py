from pydantic import BaseModel as PydanticBaseModel
from pydantic_cacheable_model import CacheableModel as PydanticCacheableModel


class BaseModel(PydanticBaseModel):
    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }


class CacheableModel(BaseModel, PydanticCacheableModel):
    @property
    def id(self) -> str:
        return self.cache_id
