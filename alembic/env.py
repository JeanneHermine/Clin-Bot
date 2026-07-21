import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# allow importing app package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# read .env if present
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# set sqlalchemy.url from env if available
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    # fallback to settings if available
    try:
        from app.config import settings

        db_url = settings.database_url
    except Exception:
        db_url = None

if db_url:
    config.set_main_option('sqlalchemy.url', db_url)

# add your model's MetaData object here for 'autogenerate' support
from app import models

target_metadata = models.Base.metadata


def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
