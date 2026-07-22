"""
Snowflake connection with dual authentication:
  1. st.secrets["snowflake"][key] — for Cloud deployment
  2. os.environ["SNOWFLAKE_*"] — for local dev (existing dbt setup)

This dual approach lets the same code work locally (using Windows env vars)
and on Streamlit Cloud (using deployed secrets) without code changes.

Uses snowflake-connector-python (plain connector, not Snowpark).
Lightweight — just SQL execution + pandas DataFrames, no distributed compute.
"""

import os
import streamlit as st
import snowflake.connector


def get_secret(key: str, default: str | None = None) -> str:
    """
    Retrieve a Snowflake credential with fallback logic.

    Priority:
      1. st.secrets["snowflake"][key] (for Cloud deployment)
      2. os.environ[f"SNOWFLAKE_{key.upper()}"] (for local dev)
      3. default parameter (if provided)

    Missing secrets.toml is normal in local development - any failure in
    st.secrets lookup falls through to env vars silently.

    Args:
        key: credential key (e.g., "account", "user", "password", "schema")
        default: fallback value if neither st.secrets nor env var provides it.
                 Only use for non-secret config (e.g., schema="GOLD").

    Returns:
        Credential value

    Raises:
        ValueError: if no source (secrets, env var, or default) provides the key
    """
    # Try Streamlit secrets first (works on Streamlit Cloud).
    # Any failure here - missing file, missing key, etc. - just means
    # "not available", so fall through to env vars.
    try:
        return st.secrets["snowflake"][key]
    except Exception:
        pass

    # Fall back to environment variable (for local dev with existing dbt setup)
    env_key = f"SNOWFLAKE_{key.upper()}"
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value

    # Use default if provided
    if default is not None:
        return default

    # No source found — raise a clear error
    raise ValueError(
        f"Missing credential '{key}'. Set it in "
        f".streamlit/secrets.toml or as env var {env_key}."
    )


@st.cache_resource
def get_connection():
    """
    Get cached Snowflake connection. Initialized once per session, reused
    across all page reruns. Returns a snowflake.connector.SnowflakeConnection.
    """
    connection = snowflake.connector.connect(
        account=get_secret("account"),
        user=get_secret("user"),
        password=get_secret("password"),
        role=get_secret("role"),
        warehouse=get_secret("warehouse"),
        database=get_secret("database"),
        # schema is a destination, not a credential. This app always queries
        # the gold layer, so it defaults to "GOLD". Real credentials (account,
        # user, password, etc.) must be provided explicitly — no silent defaults.
        schema=get_secret("schema", default="GOLD"),
    )
    return connection


@st.cache_data(ttl=3600)
def run_query(query: str):
    """
    Execute a SQL query and return cached results as a pandas DataFrame.

    Caching strategy:
      - @st.cache_data hashes the query string to build the cache key.
      - Same SQL string = same cached result (1-hour TTL).
      - Connection is fetched INSIDE the cached function (not passed in)
        so that connection objects (which aren't hashable) don't break caching.

    Every widget interaction (filter click, date change) runs the whole
    script, but cached queries return instantly without hitting Snowflake.

    Args:
        query: SQL string

    Returns:
        pandas DataFrame with query results
    """
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        # fetch_pandas_all() returns a pandas DataFrame directly
        return cursor.fetch_pandas_all()
    finally:
        if cursor:
            cursor.close()
