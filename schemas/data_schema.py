from pydantic import BaseModel,Field


class DataSchema(BaseModel):
    name : str = Field(max_length=20)
    surname : str = Field(max_length=20)
    id : int
