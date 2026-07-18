import os


# Tests replace the engine with a temporary SQLite database. The application
# itself still requires DATABASE_URL in every normal local or deployed run.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test-default.db")
