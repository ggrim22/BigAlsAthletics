"""Cache-busting {% static %} for development.

`runserver` serves /static/ through Django's own StaticFilesHandler, which
intercepts the request before middleware (so WhiteNoise's cache headers never
apply) and responds with only a Last-Modified header.  Browsers then fall back
to heuristic caching and can keep serving an edited stylesheet or script for a
long time, which looks exactly like "my CSS change did nothing".

Appending the file's mtime gives the asset a new URL whenever it changes, so the
browser is forced to refetch.  In production {% static %} already returns a
content-hashed URL, so this passes straight through.
"""

import os

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path):
    url = static(path)
    if not settings.DEBUG:
        return url

    try:
        absolute_path = finders.find(path)
    except Exception:
        return url

    if not absolute_path:
        return url
    if isinstance(absolute_path, (list, tuple)):
        absolute_path = absolute_path[0]

    try:
        stamp = int(os.path.getmtime(absolute_path))
    except OSError:
        return url

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={stamp}"
