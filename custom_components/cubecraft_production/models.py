"""Typed pipeline records and transition rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .const import STAGES, USER_STAGE_TRANSITIONS


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Shipment:
    shipment_id: str
    tracking_number: str
    carrier: str = "USPS"
    status: str = "label_created"
    ship_date: str | None = None
    accepted_at: str | None = None
    refunded: bool = False
    tracking_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Shipment":
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})


@dataclass(slots=True)
class Order:
    order_id: int
    order_number: str
    created_at: str
    stage: str = "queued"
    assigned_to: str | None = None
    blocked: bool = False
    exception: str | None = None
    customer: dict[str, Any] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)
    shipping_method: str | None = None
    customer_note: str | None = None
    order_url: str | None = None
    shipments: list[Shipment] = field(default_factory=list)
    notes: list[dict[str, str]] = field(default_factory=list)
    updated_at: str = field(default_factory=utcnow)
    done_at: str | None = None
    completion_synced: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Order":
        normalized = dict(data)
        normalized["shipments"] = [Shipment.from_dict(item) for item in data.get("shipments", [])]
        return cls(**{key: normalized[key] for key in cls.__dataclass_fields__ if key in normalized})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def add_note(self, author: str, message: str) -> None:
        self.notes.append({"at": utcnow(), "author": author, "message": message})
        self.updated_at = utcnow()

    def can_move_to(self, stage: str) -> bool:
        return not self.blocked and stage in USER_STAGE_TRANSITIONS.get(self.stage, set())

    def all_active_shipments_accepted(self) -> bool:
        active = [shipment for shipment in self.shipments if not shipment.refunded]
        return bool(active) and all(shipment.accepted_at for shipment in active)

    def move_to(self, stage: str, author: str, note: str | None = None, *, automated: bool = False) -> None:
        if stage not in STAGES:
            raise ValueError(f"Unknown production stage: {stage}")
        if stage == "done":
            if not automated or self.stage != "awaiting_usps" or not self.all_active_shipments_accepted():
                raise ValueError("Only USPS acceptance may complete an order")
        elif not self.can_move_to(stage):
            raise ValueError(f"Cannot move {self.stage} to {stage}")
        old_stage = self.stage
        self.stage = stage
        self.updated_at = utcnow()
        if stage == "done":
            self.done_at = self.updated_at
        self.add_note(author, note or f"Stage changed from {old_stage} to {stage}")
