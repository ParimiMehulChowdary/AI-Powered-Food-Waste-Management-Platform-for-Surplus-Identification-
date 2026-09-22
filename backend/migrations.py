"""Create the database schema from scratch.

Usage:
    python migrations.py            # create all tables
    python migrations.py --reset    # DROP all tables first, then recreate (destructive!)
"""

import sys

from database import Base, engine
from models import *  # noqa: F401,F403  (registers all ORM models with Base.metadata)


def main() -> None:
    reset = "--reset" in sys.argv
    if reset:
        Base.metadata.drop_all(engine)
        print("Dropped all tables.")
    Base.metadata.create_all(engine)
    tables = sorted(Base.metadata.tables.keys())
    print(f"Created {len(tables)} tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()