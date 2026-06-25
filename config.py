import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Read configuration from environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
