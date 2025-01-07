from django.conf.urls import handler404, handler500
from django.http import JsonResponse
from django.http import Http404
from django.urls import Resolver404, resolve
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    AuthenticationFailed,
    ValidationError,
)
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


# Custom handler for 404
def custom_404_handler(request, exception=None):
    return JsonResponse(
        {"error": "Resource not found", "details": "The requested URL does not exist."},
        status=404,
    )


# Custom handler for 500
def custom_500_handler(request):
    return JsonResponse(
        {
            "error": "Internal Server Error",
            "details": "An unexpected error occurred on the server.",
        },
        status=500,
    )


handler404 = custom_404_handler
handler500 = custom_500_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    logger.error(
        f"Exception occurred: {type(exc).__name__} - {str(exc)}", exc_info=True
    )

    if response is None:
        return Response(
            {
                "error": "Internal Server Error",
                "details": "An unexpected error occurred.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def set_response_data(error_message, status_code, details=None):
        response.data = {"error": error_message}
        if details:
            response.data["details"] = details
        response.status_code = status_code

    if isinstance(exc, NotFound):
        try:
            resolve(context["request"].path.rstrip("/"))
            set_response_data("Wrong URL format", status.HTTP_404_NOT_FOUND)
        except Resolver404:
            set_response_data("Resource not found", status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, PermissionDenied):
        set_response_data("Permission denied", status.HTTP_403_FORBIDDEN, str(exc))
    elif isinstance(exc, AuthenticationFailed):
        set_response_data(
            "Authentication failed", status.HTTP_401_UNAUTHORIZED, str(exc)
        )
    elif isinstance(exc, ValidationError):
        set_response_data("Invalid data", status.HTTP_400_BAD_REQUEST, exc.detail)
    elif isinstance(exc, Http404):
        set_response_data(
            "Wrong URL",
            status.HTTP_404_NOT_FOUND,
            "The requested URL does not exist",
        )
    else:
        logger.exception("Unhandled exception")
        set_response_data(
            "Internal Server Error",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Something went wrong",
        )

    return response
