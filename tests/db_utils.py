from contextlib import contextmanager
from pathlib import Path
import tempfile


@contextmanager
def temporary_database():
    import database.matchups as matchups
    import database.queries as queries
    import database.rosters as rosters
    import database.storage as storage

    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    path = Path(handle.name)
    previous = (storage.DB_PATH, queries.DB_PATH, matchups.DB_PATH, rosters.DB_PATH)
    storage.DB_PATH = queries.DB_PATH = matchups.DB_PATH = rosters.DB_PATH = path
    try:
        storage.initialize_database()
        yield path
    finally:
        storage.DB_PATH, queries.DB_PATH, matchups.DB_PATH, rosters.DB_PATH = previous
        path.unlink(missing_ok=True)
