"""
Rate limiting decorators for Django views
"""
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import render


def rate_limit(key_prefix, limit, period, message=None, methods=None):
    """
    Rate limit decorator that limits requests based on IP address

    Args:
        key_prefix (str): Prefix for the cache key (e.g., 'contact', 'add_item')
        limit (int): Maximum number of requests allowed
        period (int): Time period in seconds
        message (str): Custom error message to display
        methods (list): HTTP methods to rate limit (default: ['POST'] for forms)

    Example:
        @rate_limit('contact', limit=3, period=300)  # 3 POST requests per 5 minutes
        def contact_view(request):
            ...
    """
    if methods is None:
        methods = ['POST']

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return view_func(request, *args, **kwargs)

            ip = get_client_ip(request)
            cache_key = f'rate_limit_{key_prefix}_{ip}'

            request_count = cache.get(cache_key, 0)

            if request_count >= limit:
                error_message = message or 'Too many requests. Please wait a few minutes before trying again.'

                if request.headers.get('HX-Request'):
                    messages.error(request, error_message)
                    return HttpResponse(status=429)
                else:
                    messages.error(request, error_message)
                    if hasattr(view_func, 'rate_limit_template'):
                        template = view_func.rate_limit_template
                        context = view_func.rate_limit_context() if callable(getattr(view_func, 'rate_limit_context', None)) else {}
                        return render(request, template, context, status=429)
                    return HttpResponse('Too Many Requests', status=429)

            if request_count == 0:
                cache.set(cache_key, 1, period)
            else:
                cache.incr(cache_key)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def get_client_ip(request):
    """
    Get the client's IP address from the request
    Handles proxy headers (X-Forwarded-For) for Heroku/production
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip