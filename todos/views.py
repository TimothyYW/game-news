from django.shortcuts import render

# Create your views here.
def todos(request):
    return render(request, 'index.html', {
        # add seo dynamic
        "title": "Top Browser RPGs in 2026",
        "description": "Ranking the most played RPG browser games in 2026.",
        "og_image": "https://cdn.example.com/images/rpg.jpg",
    })