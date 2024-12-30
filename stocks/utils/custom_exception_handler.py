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


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    logger.error(f"Exception occurred: {exc}", exc_info=True)

    if response is None:
        response = Response(
            {"error": "Unknown error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    elif isinstance(exc, NotFound):
        try:
            resolve(context["request"].path.rstrip("/"))
            response.data = {
                "error": "Wrong URL format",
                "details": "You may be missing a trailing slash at the end of the URL.",
            }
            response.status_code = status.HTTP_404_NOT_FOUND
        except Resolver404:
            response.data = {"error": "Resource not found", "details": str(exc)}
            response.status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, PermissionDenied):
        response.data = {"error": "Permission denied", "details": str(exc)}
        response.status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, AuthenticationFailed):
        response.data = {"error": "Authentication failed", "details": str(exc)}
        response.status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, ValidationError):
        response.data = {"error": "Invalid data", "details": exc.detail}
        response.status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, Http404):
        response.data = {
            "error": "Wrong URL",
            "details": "The requested URL does not exist",
        }
        response.status_code = status.HTTP_404_NOT_FOUND
    else:
        logger.exception("Unexpected exception occurred")
        response.data = {
            "error": "Internal Server Error",
            "details": "Something went wrong",
        }
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return response
