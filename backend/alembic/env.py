from alembic import context
from sqlalchemy import engine_from_config, pool
from app.models import Base
from app.config import Settings
config=context.config
config.set_main_option('sqlalchemy.url',Settings.from_env().database_url.replace('%','%%'))
target_metadata=Base.metadata

def offline():
    context.configure(url=config.get_main_option('sqlalchemy.url'),target_metadata=target_metadata,literal_binds=True,dialect_opts={'paramstyle':'named'})
    with context.begin_transaction():context.run_migrations()

def online():
    engine=engine_from_config(config.get_section(config.config_ini_section),prefix='sqlalchemy.',poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=target_metadata,render_as_batch=connection.dialect.name=='sqlite')
        with context.begin_transaction():context.run_migrations()
if context.is_offline_mode():offline()
else:online()
