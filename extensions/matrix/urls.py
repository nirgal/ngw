'''
Matrix extension web pages
'''

from django.conf.urls import url

from .views import MatrixRoomsView

urls = [
    url('^$', MatrixRoomsView.as_view()),
]
