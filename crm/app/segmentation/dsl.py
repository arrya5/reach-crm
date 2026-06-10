"""Filter DSL → SQLAlchemy query translation.

The AI agent never writes SQL. It emits a small, declarative ``FilterDSL``
(validated by Pydantic) describing an audience; this module compiles that into
a parameterised SQLAlchemy query. The benefits we lean on in review:

* **No injection / no hallucinated columns** — only whitelisted fields/ops run.
* **Portable** — relative-date conditions ("ordered > 60 days ago") are
  translated into absolute timestamp cutoffs computed in Python, so the same
  DSL runs unchanged on SQLite (local/test) and Postgres (prod).
* **Explainable** — ``describe()`` renders a human sentence the UI shows back
  to the marketer for confirmation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Select, and_, func, or_, select

from ..models import Customer, Order

NUMERIC_OPS = {"gt", "gte", "lt", "lte", "eq"}
# Fields the agent may reference, and which operators each supports.
ALLOWED_FIELDS: dict[str, set[str]] = {
    "city": {"eq", "in", "contains"},
    "gender": {"eq", "in"},
    "signup_days_ago": {"gt", "gte", "lt", "lte"},
    "last_order_days_ago": {"gt", "gte", "lt", "lte"},
    "first_order_days_ago": {"gt", "gte", "lt", "lte"},
    "total_spend": NUMERIC_OPS,
    "order_count": NUMERIC_OPS,
    "avg_order_value": NUMERIC_OPS,
    "category": {"in", "eq"},
    "product": {"contains"},
}
DAYS_AGO_FIELDS = {"signup_days_ago", "last_order_days_ago", "first_order_days_ago"}


class Condition(BaseModel):
    field: str
    op: Literal["gt", "gte", "lt", "lte", "eq", "in", "contains"]
    value: Any

    @field_validator("field")
    @classmethod
    def _known_field(cls, v: str) -> str:
        if v not in ALLOWED_FIELDS:
            raise ValueError(
                f"unknown field '{v}'. allowed: {sorted(ALLOWED_FIELDS)}"
            )
        return v

    def validate_op(self) -> None:
        if self.op not in ALLOWED_FIELDS[self.field]:
            raise ValueError(
                f"op '{self.op}' not allowed for field '{self.field}'"
            )


class FilterDSL(BaseModel):
    match: Literal["all", "any"] = "all"
    conditions: list[Condition] = Field(default_factory=list)

    def model_post_init(self, _ctx) -> None:
        for c in self.conditions:
            c.validate_op()


# --- aggregate subquery (per-customer order rollups) ----------------------

def _order_aggregates():
    """Subquery of per-customer order metrics, joined into the main query."""
    return (
        select(
            Order.customer_id.label("customer_id"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.amount), 0.0).label("total_spend"),
            func.max(Order.ordered_at).label("last_order_at"),
            func.min(Order.ordered_at).label("first_order_at"),
        )
        .group_by(Order.customer_id)
        .subquery()
    )


def _days_ago_cutoff(days: float, now: datetime) -> datetime:
    return now - timedelta(days=days)


def build_query(dsl: FilterDSL, now: datetime | None = None) -> Select:
    """Compile a FilterDSL into a ``select(Customer)`` query."""
    now = now or datetime.now(timezone.utc)
    agg = _order_aggregates()

    avg_order_value = func.coalesce(agg.c.total_spend / func.nullif(agg.c.order_count, 0), 0.0)

    clauses = []
    for c in dsl.conditions:
        clauses.append(_compile_condition(c, agg, avg_order_value, now))

    combiner = and_ if dsl.match == "all" else or_
    query = select(Customer).outerjoin(agg, agg.c.customer_id == Customer.id)
    if clauses:
        query = query.where(combiner(*clauses))
    return query


def _compile_condition(c: Condition, agg, avg_order_value, now: datetime):
    f, op, val = c.field, c.op, c.value

    # Relative-date fields: translate "N days ago" into a timestamp cutoff.
    # More days ago == older == earlier timestamp, so comparisons invert.
    if f in DAYS_AGO_FIELDS:
        col = {
            "signup_days_ago": Customer.created_at,
            "last_order_days_ago": agg.c.last_order_at,
            "first_order_days_ago": agg.c.first_order_at,
        }[f]
        cutoff = _days_ago_cutoff(float(val), now)
        return {
            "gt": col < cutoff,    # older than N days
            "gte": col <= cutoff,
            "lt": col > cutoff,    # within the last N days
            "lte": col >= cutoff,
        }[op]

    if f in {"total_spend", "order_count", "avg_order_value"}:
        col = {
            "total_spend": agg.c.total_spend,
            "order_count": agg.c.order_count,
            "avg_order_value": avg_order_value,
        }[f]
        return _numeric(col, op, val)

    if f == "city":
        if op == "in":
            return Customer.city.in_(val)
        if op == "contains":
            return Customer.city.ilike(f"%{val}%")
        return Customer.city == val

    if f == "gender":
        return Customer.gender.in_(val) if op == "in" else Customer.gender == val

    if f == "category":
        vals = val if isinstance(val, list) else [val]
        return Customer.id.in_(
            select(Order.customer_id).where(Order.category.in_(vals))
        )

    if f == "product":
        return Customer.id.in_(
            select(Order.customer_id).where(Order.product_name.ilike(f"%{val}%"))
        )

    raise ValueError(f"unhandled field {f}")  # pragma: no cover


def _numeric(col, op: str, val):
    return {
        "gt": col > val,
        "gte": col >= val,
        "lt": col < val,
        "lte": col <= val,
        "eq": col == val,
    }[op]


# --- human-readable rendering --------------------------------------------

_OP_WORDS = {"gt": ">", "gte": "≥", "lt": "<", "lte": "≤", "eq": "=", "in": "in", "contains": "contains"}


def describe(dsl: FilterDSL) -> str:
    if not dsl.conditions:
        return "all customers"
    joiner = " AND " if dsl.match == "all" else " OR "
    parts = [f"{c.field} {_OP_WORDS[c.op]} {c.value}" for c in dsl.conditions]
    return joiner.join(parts)
