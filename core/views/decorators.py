'''
decorators for checking views access rights
'''

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.decorators import available_attrs

__all__ = ['login_required', 'require_group']

def require_group(group_id):
    '''
    Decorator to make a view only accept users from a given group.
    '''
    def decorator(func):
        @wraps(func, assigned=available_attrs(func)) # python2 compat
        def inner(request, *args, **kwargs):
            try:
                user = request.user
            except AttributeError:
                raise PermissionDenied
            if not user.is_member_of(group_id):
                raise PermissionDenied
            return func(request, *args, **kwargs)
        return inner
    return decorator
