# -*- encoding: utf-8 -*-
'''
Response subclasses
'''

import json
from django.http import HttpResponse, Http404

class JsonHttpResponse(HttpResponse):
    '''
    HttpResponse subclass that json encode content, with default content_type
    '''
    def __init__(self, content, content_type='application/json', *args, **kwargs):
        super(JsonHttpResponse, self).__init__(json.dumps(content), content_type, *args, **kwargs)


