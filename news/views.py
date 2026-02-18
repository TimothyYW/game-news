import uuid
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from .models import News
from .forms import NewsForm
from core.supabase import get_supabase_client
from datetime import datetime
from accounts.decorator import supabase_auth_required

def news_list(request):
    res = (
        get_supabase_client()
        .table("news")
        .select("*, profiles(username)")   # ✅ join author username
        .order("created_at", desc=True)
        .execute()
    )

    news = []
    for item in res.data or []:
        # --- Flatten author ---
        profile = item.pop("profiles", None)
        item["author_username"] = profile["username"] if profile else "Unknown"

        # --- Parse timestamps ---
        for field in ("created_at", "updated_at"):
            raw = item.get(field)
            if raw:
                item[field] = datetime.fromisoformat(raw)

        news.append(item)

    print("🚀 DEBUG: News List", news)
    return render(request, "list.html", {
        "title":       "Web Game News",
        "description": "Browse the latest news posts.",
        "news":        news,
    })

def news_detail(request, pk):
    res = get_supabase_client().table("news").select("*").eq("id", str(pk)).single().execute()

    if not res.data:
        raise Http404("News not found")

    return render(request, "detail.html", {
        "item": res.data
    })

@supabase_auth_required
def news_create(request):
    if request.method == 'POST':
        form = NewsForm(request.POST)
        if form.is_valid():
            user_id = request.session.get('supabase_user_id')
            
            get_supabase_client().table('news').insert({
                'title': form.cleaned_data['title'],
                'content': form.cleaned_data['content'],
                'author_id': user_id,
            }).execute()
            return redirect('news_list')
    else:
        form = NewsForm()
    return render(request, 'form.html', {
        "title": "Create - Web Game News",
        "description": "Create a new news post.",
        'form': form
    })

def news_api(request):
    VALID_FILTERS = {"new", "top", "hot", "best"}
    filter_type = request.GET.get("filter", "new")
    page        = int(request.GET.get("page", 1))
    page_size   = 10

    if filter_type not in VALID_FILTERS:
        return JsonResponse({"error": f"Invalid filter. Choose from: {', '.join(VALID_FILTERS)}"}, status=400)

    offset = (page - 1) * page_size
    client = get_supabase_client()

    count_query = client.table("news").select("*", count="exact", head=True)
    count_res   = count_query.execute()
    total       = count_res.count or 0

    query = client.table("news").select("*, profiles(username)")

    if filter_type == "new":
        query = query.order("created_at", desc=True)
    elif filter_type == "top":
        query = query.order("votes", desc=True)
    elif filter_type == "hot":
        query = query.order("views", desc=True)
    elif filter_type == "best":
        query = query.order("votes", desc=True).order("views", desc=True)

    res = query.range(offset, offset + page_size - 1).execute()

    news = []
    for item in (res.data or []):
        profile = item.pop("profiles", None)
        item["author_username"] = profile["username"] if profile else "Unknown"
        news.append(item)

    return JsonResponse({
        "news":     news,
        "page":     page,
        "has_more": (offset + page_size) < total,
    })

@supabase_auth_required
def news_api_create(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # --- Extract inputs ---
    title       = (request.POST.get("title") or "").strip()
    content     = (request.POST.get("content") or "").strip()
    image       = request.FILES.get("image")
    user_id     = request.session.get("supabase_user_id")

    # --- Auth ---
    if not user_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # --- Validation ---
    if not title:
        return JsonResponse({"error": "Title is required"}, status=400)
    if not content:
        return JsonResponse({"error": "Content is required"}, status=400)

    # --- Supabase client ---
    supabase = get_supabase_client()

    # --- Image upload (optional) ---
    image_url = None
    if image:
        file_ext  = image.name.rsplit(".", 1)[-1].lower()
        file_name = f"{uuid.uuid4()}.{file_ext}"
        try:
            supabase.storage.from_("news_bucket").upload(
                file_name,
                image.read(),
                {"content-type": image.content_type},
            )
            image_url = supabase.storage.from_("news_bucket").get_public_url(file_name)
        except Exception as e:
            return JsonResponse({"error": f"Image upload failed: {str(e)}"}, status=500)

    # --- DB insert ---
    try:
        result = supabase.table("news").insert({
            "title":     title,
            "content":   content,
            "author_id": user_id,
            "image_url": image_url,
        }).execute()
    except Exception as e:
        return JsonResponse({"error": f"Database insert failed: {str(e)}"}, status=500)

    if not result.data:
        return JsonResponse({"error": "Insert returned no data"}, status=500)

    return JsonResponse({"success": True, "message": "News created successfully"})

@supabase_auth_required
def news_update(request, pk):
    user_id      = request.session.get("supabase_user_id")
    access_token = request.session.get("supabase_access_token")
    client       = get_supabase_client()

    # --- Fetch existing post ---
    res  = client.table("news").select("*").eq("id", str(pk)).single().execute()
    news = res.data

    if not news:
        return JsonResponse({"error": "Not found"}, status=404)

    # --- Ownership check ---
    if news["author_id"] != user_id:
        return JsonResponse({"error": "Forbidden"}, status=403)

    # --- GET: pre-fill form ---
    if request.method == "GET":
        form = NewsForm(initial={
            "title":   news["title"],
            "content": news["content"],
        })
        return render(request, "form.html", {
            "form": form,
            "news": news,
            "title": "Update - Web Game News",
            "description": "Update an existing news post.",
        })

    # --- POST: validate and update ---
    if request.method == "POST":
        form = NewsForm(request.POST, request.FILES)

        if not form.is_valid():
            return render(request, "form.html", {
                "form": form,
                "news": news,
                "title": "Update - Web Game News",
                "description": "Update an existing news post.",
            })

        title   = form.cleaned_data["title"]
        content = form.cleaned_data["content"]
        image   = form.cleaned_data.get("image")

        # --- Handle image ---
        image_url    = news.get("image_url")   # keep existing by default
        remove_image = request.POST.get("remove_image") == "true"

        if remove_image:
            image_url = None

        elif image:
            file_ext  = image.name.rsplit(".", 1)[-1].lower()
            file_name = f"{uuid.uuid4()}.{file_ext}"
            try:
                client.storage.from_("news_bucket").upload(
                    file_name,
                    image.read(),
                    {"content-type": image.content_type},
                )
                image_url = client.storage.from_("news_bucket").get_public_url(file_name)
            except Exception as e:
                form.add_error(None, f"Image upload failed: {str(e)}")
                return render(request, "form.html", {
                    "form": form,
                    "news": news,
                    "title": "Edit Post",
                })

        # --- Update DB ---
        try:
            result = (
                client.table("news")
                .update({
                    "title":     title,
                    "content":   content,
                    "image_url": image_url,
                })
                .eq("id", str(pk))
                .execute()
            )
        except Exception as e:
            form.add_error(None, f"Update failed: {str(e)}")
            return render(request, "form.html", {
                "form": form,
                "news": news,
                "title": "Edit Post",
            })

        if not result.data:
            form.add_error(None, "Update returned no data, please try again.")
            return render(request, "form.html", {
                "form": form,
                "news": news,
                "title": "Edit Post",
            })

        return redirect("news_list")

    return JsonResponse({"error": "Method not allowed"}, status=405)


@supabase_auth_required
def news_delete(request, pk):
    if request.method == "POST":
        get_supabase_client().table("news").delete().eq("id", str(pk)).execute()
    return redirect("news_list")



@supabase_auth_required
def news_vote(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    user_id = request.session.get("supabase_user_id")
    client  = get_supabase_client()

    import json
    try:
        body  = json.loads(request.body)
        value = body.get("value")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if value not in (1, -1):
        return JsonResponse({"error": "Value must be 1 or -1"}, status=400)

    try:
        # Single atomic DB call — no race conditions
        result = client.rpc("handle_vote", {
            "p_news_id": str(pk),
            "p_user_id": user_id,
            "p_value":   value,
        }).execute()

        new_votes = result.data

    except Exception as e:
        return JsonResponse({"error": f"Vote failed: {str(e)}"}, status=500)

    return JsonResponse({"success": True, "votes": new_votes})