from django.shortcuts import redirect
from functools import wraps

def supabase_auth_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not getattr(request, 'supabase_user', None):
            return redirect('login')  # Ensure you have a URL named 'login'
        return view_func(request, *args, **kwargs)
    return _wrapped_view