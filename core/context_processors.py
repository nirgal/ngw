from django.conf import settings

from ngw.core.models import Config, Contact


def banner(request):
    """
    This context processor just add a "banner" key that's allways available
    """
    if hasattr(request, 'user') and request.user.is_authenticated():
        return {'banner': Config.objects.get(pk='banner').text}
    else:
        return ()


def contactcount(request):
    """
    This context processor just add a "contactcount" key
    """
    if hasattr(request, 'user') and request.user.is_authenticated():
        return {'contactcount': Contact.objects.count()}
    else:
        return ()


def extra_header_links(request):
    """
    This context processor just add a "extra_header_links" key
    """
    return {'extra_header_links': settings.EXTRA_BANNER_LINKS}
