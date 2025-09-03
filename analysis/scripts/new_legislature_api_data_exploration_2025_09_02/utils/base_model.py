from pydantic import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }
