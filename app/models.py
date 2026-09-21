"""Input contract shared by the two local interfaces."""
from datetime import date
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)

    tribunal: str = Field(min_length=1, max_length=16)
    processo: str | None = Field(default=None, validation_alias=AliasChoices('processo', 'process'))
    classe: int | None = Field(default=None, gt=0, strict=True, validation_alias=AliasChoices('classe', 'class'))
    assunto: int | None = Field(default=None, gt=0, strict=True, validation_alias=AliasChoices('assunto', 'subject'))
    movimento: int | None = Field(default=None, gt=0, strict=True, validation_alias=AliasChoices('movimento', 'movement'))
    company: str | None = None
    party: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    size: int = Field(default=10, ge=1, le=100, strict=True)
    search_after: list[Any] | None = None
    query: dict[str, Any] | None = None

    @model_validator(mode='after')
    def check_exclusive_query(self):
        if self.query is not None:
            simple = {'processo', 'classe', 'assunto', 'movimento', 'date_from', 'date_to', 'size', 'search_after'}
            if self.model_fields_set & simple:
                raise ValueError('query raw não pode ser combinada com filtros ou paginação externos.')
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError('date_from deve ser anterior ou igual a date_to.')
        return self


class DiscoverRequest(SearchRequest):
    limit: int = Field(default=100, ge=1, le=1000, strict=True)
    page_size: int = Field(default=100, ge=1, le=100, strict=True)

    @model_validator(mode='after')
    def managed_pagination(self):
        if self.model_fields_set & {'size', 'search_after'}:
            raise ValueError('Discovery administra size/search_after; use limit e page_size.')
        if self.query is not None and set(self.query) & {'size', 'search_after', 'from'}:
            raise ValueError('Query de discovery não aceita size/search_after/from; use limit e page_size.')
        return self


class ExtractFileRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_file: str = Field(min_length=1)
