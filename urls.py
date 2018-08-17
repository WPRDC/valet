from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^ajax/get_results/$', views.get_results, name='get_results'),
    url(r'^$', views.index, name='index'),
]
