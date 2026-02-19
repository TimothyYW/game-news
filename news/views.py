import uuid
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from .models import News
from .forms import NewsForm
from core.supabase import get_supabase_client
from datetime import datetime
from accounts.decorator import supabase_auth_required
from core.utils import parse_supabase_data

def news_list(request):
    res = (
        get_supabase_client()
        .table("news")
        .select("*, profiles(username)")  
        .order("created_at", desc=True)
        .execute()
    )

    news = []
    for item in res.data or []:
        profile = item.pop("profiles", None)
        item["author_username"] = profile["username"] if profile else "Unknown"

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
    client = get_supabase_client()
    
    res = client.table("news").select("*, profiles(username, avatar_url)").eq("id", str(pk)).single().execute()
    
    if not res.data:
        raise Http404("News not found")
    
    item = res.data
    profile = item.pop("profiles", None)
    item["author_username"] = profile["username"] if profile else "Unknown"
    item["author_avatar"] = profile.get("avatar_url") if profile else None
    
    item = parse_supabase_data(item, "created_at", "updated_at")
    
    comments_res = (
        client.table("comments")
        .select("*, profiles(username, avatar_url)")
        .eq("news_id", str(pk))
        .is_("parent_id", "null")
        .order("votes", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    
    comments = []
    for comment in (comments_res.data or []):
        profile = comment.pop("profiles", None)
        comment["author_username"] = profile["username"] if profile else "Unknown"
        comment["author_avatar"] = profile.get("avatar_url") if profile else None
        comment = parse_supabase_data(comment, "created_at", "updated_at")
        
        replies_res = (
            client.table("comments")
            .select("*, profiles(username, avatar_url)")
            .eq("parent_id", comment["id"])
            .order("votes", desc=True)
            .order("created_at", desc=True)
            .execute()
        )
        
        replies = []
        for reply in (replies_res.data or []):
            r_profile = reply.pop("profiles", None)
            reply["author_username"] = r_profile["username"] if r_profile else "Unknown"
            reply["author_avatar"] = r_profile.get("avatar_url") if r_profile else None
            reply = parse_supabase_data(reply, "created_at", "updated_at")
            replies.append(reply)
        
        comment["replies"] = replies
        comments.append(comment)
    
    return render(request, "detail.html", {
        "item": item,
        "comments": comments,
        "comments_count": len(comments) + sum(len(c.get("replies", [])) for c in comments),
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

    title       = (request.POST.get("title") or "").strip()
    content     = (request.POST.get("content") or "").strip()
    image       = request.FILES.get("image")
    user_id     = request.session.get("supabase_user_id")

    if not user_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if not title:
        return JsonResponse({"error": "Title is required"}, status=400)
    if not content:
        return JsonResponse({"error": "Content is required"}, status=400)

    supabase = get_supabase_client()

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
    client       = get_supabase_client()

    res  = client.table("news").select("*").eq("id", str(pk)).single().execute()
    news = res.data

    if not news:
        return JsonResponse({"error": "Not found"}, status=404)

    if news["author_id"] != user_id:
        return JsonResponse({"error": "Forbidden"}, status=403)

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

        image_url    = news.get("image_url")   
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
        result = client.rpc("handle_vote", {
            "p_news_id": str(pk),
            "p_user_id": user_id,
            "p_value":   value,
        }).execute()

        new_votes = result.data.get("votes") 

    except Exception as e:
        return JsonResponse({"error": f"Vote failed: {str(e)}"}, status=500)

    return JsonResponse({"success": True, "votes": new_votes})


@supabase_auth_required
def comment_create(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    user_id      = request.session.get("supabase_user_id")
    client       = get_supabase_client()
    
    content   = (request.POST.get("content") or "").strip()
    parent_id = request.POST.get("parent_id")
    
    if not content:
        return JsonResponse({"error": "Content is required"}, status=400)
    
    # Insert comment
    try:
        result = client.table("comments").insert({
            "news_id":   str(pk),
            "author_id": user_id,
            "parent_id": parent_id if parent_id else None,
            "content":   content,
        }).execute()
    except Exception as e:
        return JsonResponse({"error": f"Failed to post comment: {str(e)}"}, status=500)
    
    if not result.data:
        return JsonResponse({"error": "Comment creation failed"}, status=500)
    
    return redirect("news_detail", pk=pk)


@supabase_auth_required
def comment_vote(request, comment_id):
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
        result = client.rpc("handle_comment_vote", {
            "p_comment_id": str(comment_id),
            "p_user_id":    user_id,
            "p_value":      value,
        }).execute()
        
        new_votes = result.data.get("votes")
    except Exception as e:
        return JsonResponse({"error": f"Vote failed: {str(e)}"}, status=500)
    
    return JsonResponse({"success": True, "votes": new_votes})