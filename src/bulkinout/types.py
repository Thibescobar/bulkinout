"""Shared JSON-compatible types used at serialization boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from typing_extensions import TypeAliasType

JsonScalar: TypeAlias = str | int | float | bool | None
if TYPE_CHECKING:
    JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
else:
    JsonValue = TypeAliasType(
        "JsonValue",
        JsonScalar | list["JsonValue"] | dict[str, "JsonValue"],
    )
JsonObject: TypeAlias = dict[str, JsonValue]
