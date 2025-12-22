from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

def bad_request(request, exception, *args, **kwargs):
    return Response(
        {"error": "Bad Request (400)", "message": str(exception)},
        status=status.HTTP_400_BAD_REQUEST
    )

def permission_denied(request, exception, *args, **kwargs):
    return Response(
        {"error": "Permission Denied (403)", "message": str(exception)},
        status=status.HTTP_403_FORBIDDEN
    )

def page_not_found(request, exception, *args, **kwargs):
    return Response(
        {"error": "Not Found (404)", "message": "The requested resource was not found."},
        status=status.HTTP_404_NOT_FOUND
    )

def server_error(request, *args, **kwargs):
    return Response(
        {"error": "Internal Server Error (500)", "message": "An unexpected error occurred."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'

class ValidationError(APIException):
    status_code = 400
    default_detail = 'Invalid input.'
    default_code = 'invalid_input'

class NotFound(APIException):
    status_code = 404
    default_detail = 'Not found.'
    default_code = 'not_found'