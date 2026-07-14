import os

import psycopg2
import psycopg2.extras


def get_connection():
    """Open a connection to Postgres using the DATABASE_URL environment variable."""
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
