from datetime import datetime
import json
from urllib import request, response
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from ratelimit import limits, sleep_and_retry

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