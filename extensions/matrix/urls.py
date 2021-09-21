'''
Matrix extension web pages
'''

from django.conf.urls import url

from .views import MatrixAllRoomsView, MatrixRoomsView, MatrixRoomView

urls = [
    url('^$', MatrixRoomsView.as_view()),
    url('^room/(?P<room_id>.+)$', MatrixRoomView.as_view()),
    url('^all$', MatrixAllRoomsView.as_view()),
]
