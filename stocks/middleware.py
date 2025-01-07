# middleware.py
from django.http import JsonResponse
from django.urls import Resolver404


class Handle404Middleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Resolver404:
            return JsonResponse(
                {
                    "error": "Page not found",
                    "details": "The requested URL does not exist.",
                },
                status=404,
            )
