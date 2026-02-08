from core.supabase import get_supabase_client

class SupabaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        supabase = get_supabase_client()
        token = request.session.get('supabase_access_token')
        
        request.supabase_user = None
        if token:
            try:
                # 3. Verify the token with Supabase
                user_response = supabase.auth.get_user(token)
                request.supabase_user = user_response.user
            except Exception:
                # Token expired or invalid
                request.session.pop('supabase_access_token', None)

        # 4. Continue to the view
        response = self.get_response(request)
        return response