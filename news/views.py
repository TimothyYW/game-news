from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from .models import News
from .forms import NewsForm
from core.supabase import get_supabase_client
from datetime import datetime
from accounts.decorator import supabase_auth_required

@supabase_auth_required
def news_list(request):
    res = get_supabase_client().table('news').select('*').order('created_at', desc=True).execute()
    news = res.data or []
    
    # Convert strings to Python datetime objects
    for item in news:
        if item.get('updated_at'):
            # Convert ISO string to datetime object
            item['updated_at'] = datetime.fromisoformat(item['updated_at'])
        if item.get('created_at'):
            item['created_at'] = datetime.fromisoformat(item['created_at'])

    return render(request, 'list.html', {
        "title": "Web Game News",
        "description": "Browse the latest news posts.",
        'news': news})

def news_detail(request, pk):
    res = get_supabase_client().table("news").select("*").eq("id", str(pk)).single().execute()

    if not res.data:
        raise Http404("News not found")

    return render(request, "detail.html", {
        "item": res.data
    })

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

def news_update(request, pk):
    if(request.method == 'POST'):
        form = NewsForm(request.POST)
        if form.is_valid():
            get_supabase_client().table('news').update({
                'title': form.cleaned_data['title'],
                'content': form.cleaned_data['content'],
            }).eq('id', str(pk)).execute()
            
            return redirect('news_list')
    else:
        res = get_supabase_client().table('news').select('*').eq('id', str(pk)).single().execute()
        item = res.data
        form = NewsForm(initial={
            'title': item['title'],
            'content': item['content'],
        })
    return render(request, 'form.html', {
        "title": "Update - Web Game News",
        "description": "Update an existing news post.",
        'form': form
    })

def news_delete(request, pk):
    if request.method == "POST":
        get_supabase_client().table("news").delete().eq("id", str(pk)).execute()
    return redirect("news_list")

