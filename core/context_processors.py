def supabase_auth(request):
    return {
        "is_authenticated": bool(request.session.get("supabase_user_id")),
        "user_email": request.session.get("user_email"),
        "user_id":          request.session.get("supabase_user_id"),
    }