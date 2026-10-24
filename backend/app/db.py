from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base
from .config import Settings

class Database:
    def __init__(self, url, settings=None):
        self.settings = settings or Settings(database_url=url)
        if url.startswith('sqlite'):
            filename=make_url(url).database
            if filename and filename!=':memory:':Path(filename).expanduser().resolve().parent.mkdir(parents=True,exist_ok=True)
        kwargs = {'connect_args': {'check_same_thread': False, 'timeout': 30}} if url.startswith('sqlite') else {}
        if url in ('sqlite://','sqlite:///:memory:'):
            kwargs['poolclass'] = StaticPool
        self.engine=create_engine(url, future=True, **kwargs)
        if url.startswith('sqlite'):
            @event.listens_for(self.engine,'connect')
            def configure(connection, record):
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('PRAGMA journal_mode=WAL')
        self.session_factory=sessionmaker(bind=self.engine,expire_on_commit=False,future=True)
    def initialize(self):
        if self.settings.demo_database:
            Base.metadata.create_all(self.engine)
            return
        inspector=inspect(self.engine)
        available=set(inspector.get_table_names())
        for table in Base.metadata.sorted_tables:
            if table.name not in available or set(table.columns.keys())-{c['name'] for c in inspector.get_columns(table.name)}:
                raise RuntimeError('Database schema is not current; apply Alembic migrations before starting production')
    def session(self): return self.session_factory()

def get_database():
    settings=Settings.from_env()
    return Database(settings.database_url,settings)

SessionLocal = None  # Use Database.session_factory; tests and workers can inject an isolated database.
