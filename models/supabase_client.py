import os
from supabase import create_client


def get_supabase_client():
    """Create and return a Supabase client using environment variables."""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL and SUPABASE_KEY must be set in environment')
    return create_client(url, key)
