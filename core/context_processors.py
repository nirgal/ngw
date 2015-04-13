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
