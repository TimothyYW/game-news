from datetime import datetime
import json
from urllib import request, response
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from ratelimit import limits, sleep_and_retry
from .decorator import supabase_auth_required

from core.supabase import get_supabase_client

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
    
def validate_auth_input(request, email, password):
    """Helper to handle basic validation logic."""
    if not email or not password:
        messages.error(request, "All fields are required.")
        return False
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Please enter a valid email address.")
        return False
    if len(password) < 6:
        messages.error(request, "Password must be at least 6 characters.")
        return False
    return True

# @sleep_and_retry
# @limits(calls=5, period=900)
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        if validate_auth_input(request, email, password):
            supabase = get_supabase_client()
            try:
                # 1. Auth attempt
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                print("--- LOGIN SUCCESSFUL ---")

                # 2. Convert to dict (for debug only)
                user_data = response.user.model_dump()
                session_data = response.session.model_dump()

                print("USER DATA:", json.dumps(user_data, indent=4, cls=DateTimeEncoder))
                print("SESSION DATA:", json.dumps(session_data, indent=4, cls=DateTimeEncoder))

                # 3. Session Management
                request.session.cycle_key()
                request.session['supabase_access_token'] = response.session.access_token
                request.session['user_email'] = response.user.email

                # 🔑 IMPORTANT: store Supabase user UUID for News
                request.session['supabase_user_id'] = response.user.id

                return redirect("news_list")

            except Exception as e:
                print(f"DEBUG Error: {e}")

                if isinstance(e, TypeError):
                    messages.error(request, "Server logging error, but you might be logged in.")
                else:
                    messages.error(request, "Invalid email or password.")

    return render(request, 'login.html', {
        'hide_navbar': True,
        "title": "Login - Web Game News",
        "description": "Securely login to your Web Game News account.",
    })

# @sleep_and_retry
# @limits(calls=5, period=900)
def register_view(request):
    if request.session.get('supabase_access_token'):
        return redirect('todos')

    if request.method == 'POST':
        display_name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if validate_auth_input(request, email, password):
            supabase = get_supabase_client()
            try:
                response = supabase.auth.sign_up({
                    "email": email, 
                    "password": password,
                    "options": {
                        "data": {
                            "display_name": display_name
                        }
                    }
                })
                
                # --- SAFE DEBUGGING ---
                print("--- DEBUG START ---")
                if response.user:
                    print(f"User Created: {response.user.id}")
                
                if response.session:
                    print("Session active (Auto-login enabled)")
                    # Safe way to print session if it exists
                    # print(json.dumps(response.session.model_dump(), indent=4))
                else:
                    print("No session: Email verification required.")
                print("--- DEBUG END ---")

                # --- SUCCESS LOGIC ---
                # Check if confirmation email was sent
                if response.user and not response.session:
                    messages.success(request, 'Registration successful! Please check your email for a verification link.')
                else:
                    # This triggers if you have "Confirm Email" turned OFF in Supabase settings
                    messages.success(request, 'Account created and logged in successfully!')
                    request.session['supabase_access_token'] = response.session.access_token
                
                return redirect('login')

            except Exception as e:
                print(f"Registration Error: {e}")
                # Clean error message for user display
                error_msg = str(e).split(':')[-1].strip() 
                messages.error(request, error_msg)

    return render(request, 'register.html', {
        'hide_navbar': True,
        "title": "Register - Web Game News",
        "description": "Register to access member-only content on Web Game News.",
    })
    
    
def logout_view(request):
    request.session.flush()
    return redirect("login")

@supabase_auth_required
def profile_view(request):
    user_id      = request.session.get("supabase_user_id")
    client       = get_supabase_client()

    profile_res = client.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = profile_res.data

    posts_res = client.table("news").select("*", count="exact", head=True).eq("author_id", user_id).execute()
    posts_count = posts_res.count or 0

    recent_posts_res = (
        client.table("news")
        .select("id, title, votes, created_at")
        .eq("author_id", user_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )

    recent_posts = []
    for post in (recent_posts_res.data or []):
        if post.get("created_at"):
            post["created_at"] = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
        recent_posts.append(post)

    if profile.get("created_at"):
        profile["created_at"] = datetime.fromisoformat(profile["created_at"].replace("Z", "+00:00"))

    return render(request, "profile.html", {
        "title": "Profile",
        "profile": profile,
        "posts_count": posts_count,
        "recent_posts": recent_posts,
    })


@supabase_auth_required
def settings_view(request):
    user_id      = request.session.get("supabase_user_id")
    client       = get_supabase_client()

    profile_res = client.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = profile_res.data

    if request.method == "POST":
        username   = (request.POST.get("username") or "").strip()
        bio        = (request.POST.get("bio") or "").strip()
        avatar     = request.FILES.get("avatar")

        if not username:
            messages.error(request, "Username is required")
            return redirect("settings")

        avatar_url = profile.get("avatar_url")
        if avatar:
            file_ext  = avatar.name.rsplit(".", 1)[-1].lower()
            file_name = f"avatars/{user_id}.{file_ext}"
            try:
                client.storage.from_("news_bucket").upload(
                    file_name,
                    avatar.read(),
                    {"content-type": avatar.content_type, "upsert": "true"},
                )
                avatar_url = client.storage.from_("news_bucket").get_public_url(file_name)
            except Exception as e:
                messages.error(request, f"Avatar upload failed: {str(e)}")
                return redirect("settings")

        try:
            client.table("profiles").update({
                "username":   username,
                "bio":        bio,
                "avatar_url": avatar_url,
            }).eq("id", user_id).execute()

            request.session["supabase_username"] = username

            messages.success(request, "Settings saved successfully")
            return redirect("settings")

        except Exception as e:
            messages.error(request, f"Update failed: {str(e)}")
            return redirect("settings")

    return render(request, "settings.html", {
        "title": "Settings",
        "profile": profile,
    })