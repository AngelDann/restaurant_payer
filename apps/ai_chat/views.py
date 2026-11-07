from django.shortcuts import render


def chat_index(request):
    return render(request, "ai_chat/index.html")


def partial_ping(request):
    if request.htmx:
        return render(request, "partials/ping.html")
    return render(request, "ai_chat/index.html")
