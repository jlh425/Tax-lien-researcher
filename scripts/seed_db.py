#!/usr/bin/env python3
"""Seed the database with reference data.

Usage:
    python scripts/seed_db.py
"""

import asyncio


async def seed():
    """Seed reference data into the database."""
    # TODO: Import engine, create session, insert:
    # - State classifications (lien vs deed vs hybrid)
    # - Default outreach templates
    # - Tier configurations per county
    print("Seeding database...")
    print("Done. (No models to seed yet)")


if __name__ == "__main__":
    asyncio.run(seed())
