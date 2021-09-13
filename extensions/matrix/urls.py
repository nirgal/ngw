'''
Matrix extension web pages
'''

from django.conf.urls import url

from .views import MatrixAllRoomsView, MatrixRoomsView

urls = [
    url('^$', MatrixRoomsView.as_view()),
    url('^all$', MatrixAllRoomsView.as_view()),
]
