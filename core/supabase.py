from supabase import create_client, Client
from django.conf import settings

def get_supabase_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# import os
# from supabase import create_client, Client

# def get_supabase() -> Client:
#     url = os.environ.get("SUPABASE_URL")
#     key = os.environ.get("SUPABASE_KEY")
#     return create_client(url, key)