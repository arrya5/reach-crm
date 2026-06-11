"""Seed the CRM with realistic, simulated SUGAR Cosmetics data.

Run:  python -m app.seed         (from the crm/ directory)

We deliberately engineer distinct behavioural cohorts (active / lapsed /
churned / VIP / one-time) so that natural-language segments like "win back
customers who bought matte lipstick but haven't ordered in 60 days" return
meaningful, demo-able audiences rather than uniform noise.

This is fully synthetic data for a take-home demo and is not affiliated with
SUGAR Cosmetics.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from .db import SessionLocal, engine, init_db
from .models import Customer, Order

random.seed(42)  # reproducible runs

CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune",
    "Kolkata", "Ahmedabad", "Jaipur", "Lucknow", "Chandigarh", "Surat",
]
FIRST_NAMES = [
    "Aanya", "Diya", "Isha", "Kavya", "Meera", "Nisha", "Priya", "Riya",
    "Saanvi", "Tara", "Aarav", "Kabir", "Vihaan", "Rohan", "Arjun", "Ananya",
    "Sneha", "Pooja", "Neha", "Simran", "Aditya", "Ishaan", "Zara", "Myra",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Gupta", "Mehta",
    "Singh", "Kapoor", "Joshi", "Desai", "Rao", "Bose", "Chopra", "Malhotra",
]

# category -> representative products with rough price bands (INR)
CATALOG = {
    "lipstick": [("Matte Attack Liquid Lipstick", 499), ("Smudge Me Not Lipstick", 599),
                 ("Nothing Else Matte-rs Lipstick", 549)],
    "foundation": [("Ace Of Face Foundation Stick", 899), ("Skin Foundation Drops", 999)],
    "skincare": [("Vitamin C Serum", 699), ("Hydrating Moisturiser", 549),
                 ("Sunscreen SPF50", 449)],
    "eyes": [("Stroke Of Genius Eyeliner", 399), ("Lash Mob Mascara", 599),
             ("Blend The Rules Eyeshadow Palette", 1299)],
    "nails": [("Tip Tac Toe Nail Lacquer", 199)],
    "fragrance": [("Eau De Sugar Perfume", 1199)],
}
CATEGORIES = list(CATALOG)
TAG_POOL = ["new", "vip", "discount-lover", "skincare-fan", "makeup-fan", "fragrance"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pick_order(now: datetime, max_days_ago: int, min_days_ago: int = 0) -> tuple:
    category = random.choices(
        CATEGORIES, weights=[30, 18, 22, 15, 8, 7], k=1
    )[0]
    product, base = random.choice(CATALOG[category])
    amount = round(base * random.uniform(0.9, 1.6), 2)  # qty / variant spread
    days_ago = random.randint(min_days_ago, max_days_ago)
    ordered_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))
    return category, product, amount, ordered_at


async def seed(n_customers: int = 1000) -> None:
    await init_db()
    now = _now()

    async with SessionLocal() as session:
        existing = await session.get(Customer, 1)
        if existing is not None:
            print("Data already present — skipping seed. (Delete reach.db to reseed.)")
            return

        customers: list[Customer] = []
        for i in range(n_customers):
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            handle = name.lower().replace(" ", ".")
            cust = Customer(
                name=name,
                email=f"{handle}{i}@example.com",
                phone=f"+9198{random.randint(10000000, 99999999)}",
                city=random.choice(CITIES),
                gender=random.choices(["female", "male", "other"], weights=[78, 18, 4])[0],
                tags=random.sample(TAG_POOL, k=random.randint(0, 2)),
                created_at=now - timedelta(days=random.randint(15, 720)),
            )
            session.add(cust)
            customers.append(cust)
        await session.flush()  # assign ids

        # Cohorts drive recency/frequency so segments are meaningful.
        # (weight, label, n_orders_range, recency_window_days)
        cohorts = [
            (0.18, "active",   (3, 9),  (0, 25)),    # recent, frequent
            (0.15, "vip",      (8, 20), (0, 40)),    # high frequency & spend
            (0.22, "lapsed",   (2, 6),  (61, 150)),  # haven't ordered in ~2-5 months
            (0.20, "churned",  (1, 4),  (180, 540)), # long gone
            (0.15, "one_time", (1, 1),  (10, 300)),  # single purchase
            (0.10, "new",      (1, 2),  (0, 14)),    # just arrived
        ]
        labels = [c[1] for c in cohorts]
        weights = [c[0] for c in cohorts]

        total_orders = 0
        for cust in customers:
            label = random.choices(labels, weights=weights, k=1)[0]
            _, _, (lo, hi), (rmin, rmax) = next(c for c in cohorts if c[1] == label)
            n_orders = random.randint(lo, hi)
            # Most recent order falls in the cohort's recency window; older
            # orders trail back from there.
            recency = random.randint(rmin, rmax)
            for k in range(n_orders):
                # spread earlier orders further back in time, clamped to ~2y
                span = recency + k * random.randint(20, 90)
                min_days = min(span, 700)
                category, product, amount, ordered_at = _pick_order(
                    now, max_days_ago=min_days + 30, min_days_ago=min_days
                )
                session.add(Order(
                    customer_id=cust.id,
                    amount=amount,
                    category=category,
                    product_name=product,
                    ordered_at=ordered_at,
                ))
                total_orders += 1

        await session.commit()
        print(f"Seeded {len(customers)} customers and {total_orders} orders.")


async def _main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()  # dispose within the same loop for a clean exit


if __name__ == "__main__":
    asyncio.run(_main())
