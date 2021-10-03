'''
Matrix extension web pages
'''

from django.conf.urls import url
from django.views.generic.base import RedirectView

from .views import (MatrixRoomAddAdminView, MatrixRoomCloseView,
                    MatrixRoomsView, MatrixRoomView, MatrixUserView)

urls = [
    url(r'^$',
        RedirectView.as_view(url='room/')),
    url('^room/$', MatrixRoomsView.as_view()),
    url('^room/(?P<room_id>[^/]+)/$', MatrixRoomView.as_view()),
    url('^room/(?P<room_id>[^/]+)/close$', MatrixRoomCloseView.as_view()),
    url('^room/(?P<room_id>[^/]+)/add_admin$',
        MatrixRoomAddAdminView.as_view()),
    url('^user/(?P<user_id>.+)$', MatrixUserView.as_view()),
]
