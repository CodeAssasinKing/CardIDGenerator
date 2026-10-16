from pydantic import BaseModel, Field


class DataSchema(BaseModel):
    name: str = Field(default="", max_length=100, description="Имя сотрудника или полное имя")
    surname: str = Field(default="", max_length=100, description="Фамилия сотрудника (может быть пустой)")
    id: int = Field(default=1, description="ID сотрудника / бейджа")
    phone: str | None = Field(default=None, max_length=50, description="Номер телефона сотрудника (опционально)")
    website: str | None = Field(default=None, max_length=100, description="Ссылка на сайт (опционально)")
    full_name: str | None = Field(default=None, max_length=150, description="Полное ФИО в одну строку (опционально)")
