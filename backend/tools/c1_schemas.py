"""
Pydantic schemas for 1C API responses.

1C endpoints used in this project:
- GetItems: returns a list of products (code/name/price), usually wrapped as {"items": [...]}
- GetDetailedItems: returns detailed product fields, usually wrapped as {"items": [...]}

Important notes:
- 1C sometimes returns numbers as strings with commas (e.g. "1,111") and/or NBSP in thousands (e.g. "6 000").
- We keep schemas tolerant: extra fields are allowed to avoid breaking when 1C adds new keys.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    computed_field,
    field_validator,
    model_validator,
)


def _clean_c1_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        # normalize NBSP and trim
        return value.replace("\u00A0", " ").strip()
    return str(value).strip()


def _parse_c1_decimal(value: Any) -> Optional[Decimal]:
    """
    Parses numbers that can come as:
    - int/float/Decimal
    - strings with comma decimal separator: "1,111"
    - strings with spaces/NBSP thousand separators: "6 000"
    """
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = _clean_c1_string(value)
    if not s:
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_c1_float(value: Any) -> Optional[float]:
    d = _parse_c1_decimal(value)
    return float(d) if d is not None else None


def _parse_c1_int(value: Any) -> Optional[int]:
    d = _parse_c1_decimal(value)
    if d is None:
        return None
    try:
        return int(d)
    except (ValueError, OverflowError):
        return None


class C1BaseModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        str_strip_whitespace=True,
    )


class C1Stock(C1BaseModel):
    """
    Normalized representation of 1C "Остатки".

    1C may send:
    - number (int/float) or numeric string: "1 953,333"
    - a text status like "По предзаказу"
    - nothing (field absent)

    We keep defaults so downstream formatting can safely use `stock.display`.
    """

    raw: Optional[str] = None
    qty: Optional[Decimal] = None
    # qty | preorder | text | unknown
    kind: str = "unknown"

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_any(cls, v: Any) -> Any:
        if isinstance(v, C1Stock):
            return v
        if isinstance(v, dict):
            return v

        s = _clean_c1_string(v)
        if not s:
            return {"raw": None, "qty": None, "kind": "unknown"}

        d = _parse_c1_decimal(s)
        if d is not None:
            return {"raw": s, "qty": d, "kind": "qty"}

        lower = s.lower()
        if "предзаказ" in lower:
            return {"raw": s, "qty": None, "kind": "preorder"}

        return {"raw": s, "qty": None, "kind": "text"}

    @computed_field  # type: ignore[misc]
    @property
    def display(self) -> str:
        if self.kind == "qty" and self.qty is not None:
            # Keep compact string without scientific notation.
            return format(self.qty, "f").rstrip("0").rstrip(".") or "0"
        if self.raw:
            return self.raw
        return "нет данных"


class C1ShortItem(C1BaseModel):
    """Item returned by GetItems."""

    name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Наименование", "name", "Name"),
    )
    price: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("Цена", "price", "Price"),
    )
    code: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Код", "code", "Code"),
    )
    stock: C1Stock = Field(
        default_factory=C1Stock,
        validation_alias=AliasChoices("Остатки", "остатки", "stock"),
    )

    @field_validator("name", "code", mode="before")
    @classmethod
    def _v_str(cls, v: Any) -> Optional[str]:
        return _clean_c1_string(v)

    @field_validator("price", mode="before")
    @classmethod
    def _v_price(cls, v: Any) -> Optional[float]:
        # prices usually come as int, but keep tolerant
        return _parse_c1_float(v)


class C1GetItemsResponse(C1BaseModel):
    items: list[C1ShortItem] = Field(default_factory=list)


class C1DetailedItem(C1BaseModel):
    """Item returned by GetDetailedItems (fields are mostly strings from 1C)."""

    code: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("Код", "code", "Code"),
    )
    name: Optional[str] = Field(default=None, validation_alias=AliasChoices("Наименование", "name", "Name"))
    price: Optional[float] = Field(default=None, validation_alias=AliasChoices("Цена", "price", "Price"))
    stock: C1Stock = Field(
        default_factory=C1Stock,
        validation_alias=AliasChoices("Остатки", "остатки", "stock"),
    )

    # Common catalog attributes
    popularity: Optional[int] = Field(default=None, validation_alias=AliasChoices("ПопулярностьОбщие", "popularity"))
    quantity_m3_common: Optional[float] = Field(default=None, validation_alias=AliasChoices("Количествовм3Общие", "quantity_m3_common"))
    quantity_m2_common: Optional[float] = Field(default=None, validation_alias=AliasChoices("Количествовм2Общие", "quantity_m2_common"))
    production_days_common: Optional[int] = Field(default=None, validation_alias=AliasChoices("СрокпроизводстваднОбщие", "production_days_common"))
    density_kg_m3_common: Optional[float] = Field(default=None, validation_alias=AliasChoices("Плотностькгм3Общие", "density_kg_m3_common"))

    treatment_type: Optional[str] = Field(default=None, validation_alias=AliasChoices("Типобработки", "treatment_type"))
    site_name: Optional[str] = Field(default=None, validation_alias=AliasChoices("Наименованиедлясайта", "site_name"))
    humidity: Optional[str] = Field(default=None, validation_alias=AliasChoices("Влажность", "humidity"))
    lumber_type: Optional[str] = Field(default=None, validation_alias=AliasChoices("Видпиломатериала", "lumber_type"))
    species: Optional[str] = Field(default=None, validation_alias=AliasChoices("Порода", "species"))

    thickness_mm: Optional[int] = Field(default=None, validation_alias=AliasChoices("Толщина", "thickness"))
    width_mm: Optional[int] = Field(default=None, validation_alias=AliasChoices("Ширина", "width"))
    length_mm: Optional[int] = Field(default=None, validation_alias=AliasChoices("Длина", "length"))

    # Unit conversion / coefficients
    unit1: Optional[str] = Field(default=None, validation_alias=AliasChoices("Дополнительнаяедизмерения1", "unit1"))
    coef_unit1: Optional[float] = Field(default=None, validation_alias=AliasChoices("Коэфдополнительнаяедизмерения1", "coef_unit1"))
    unit2: Optional[str] = Field(default=None, validation_alias=AliasChoices("Дополнительнаяедизмерения2", "unit2"))
    coef_unit2: Optional[float] = Field(default=None, validation_alias=AliasChoices("Коэфдополнительнаяедизмерения2", "coef_unit2"))
    unit3_common: Optional[str] = Field(default=None, validation_alias=AliasChoices("Дополнительнаяедизмерения3Общие", "unit3_common"))
    coef_unit3_common: Optional[float] = Field(default=None, validation_alias=AliasChoices("Коэфдополнительнаяедизмерения3Общие", "coef_unit3_common"))

    sort: Optional[str] = Field(default=None, validation_alias=AliasChoices("Сорт", "sort"))
    region_common: Optional[str] = Field(default=None, validation_alias=AliasChoices("РегионОбщие", "region_common"))
    qty_in_pack_common: Optional[int] = Field(default=None, validation_alias=AliasChoices("КоличествовупаковкеОбщие", "qty_in_pack_common"))

    @field_validator(
        "code",
        "name",
        "treatment_type",
        "site_name",
        "humidity",
        "lumber_type",
        "species",
        "unit1",
        "unit2",
        "unit3_common",
        "sort",
        "region_common",
        mode="before",
    )
    @classmethod
    def _v_str(cls, v: Any) -> Optional[str]:
        return _clean_c1_string(v)

    @field_validator("price", "quantity_m3_common", "quantity_m2_common", "density_kg_m3_common", "coef_unit1", "coef_unit2", "coef_unit3_common", mode="before")
    @classmethod
    def _v_float(cls, v: Any) -> Optional[float]:
        return _parse_c1_float(v)

    @field_validator("popularity", "production_days_common", "thickness_mm", "width_mm", "length_mm", "qty_in_pack_common", mode="before")
    @classmethod
    def _v_int(cls, v: Any) -> Optional[int]:
        return _parse_c1_int(v)


class C1GetDetailedItemsResponse(C1BaseModel):
    items: list[C1DetailedItem] = Field(default_factory=list)


def parse_get_items_payload(payload: Any) -> list[C1ShortItem]:
    """
    1C may return either:
    - {"items": [...]} (dict)
    - [...] (list)
    """
    if isinstance(payload, dict):
        return C1GetItemsResponse.model_validate(payload).items
    if isinstance(payload, list):
        return TypeAdapter(list[C1ShortItem]).validate_python(payload)
    return []


def parse_get_detailed_items_payload(payload: Any) -> list[C1DetailedItem]:
    if isinstance(payload, dict):
        return C1GetDetailedItemsResponse.model_validate(payload).items
    if isinstance(payload, list):
        return TypeAdapter(list[C1DetailedItem]).validate_python(payload)
    return []


