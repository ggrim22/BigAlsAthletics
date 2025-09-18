from django.http import HttpResponse


class HTMXResponse(HttpResponse):
    """
    An HTTP response class with a status code of 204 and an 'HX-Trigger' header
    that is explicitly defined.
    """
    status_code = 204

    def __init__(self, *args, trigger: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        if trigger:
            self.headers['HX-Trigger'] = trigger