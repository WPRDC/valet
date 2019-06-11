from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^ajax/get_dates/$', views.get_dates, name='get_dates'),
    url(r'^ajax/get_features/$', views.get_features, name='get_features'),
    url(r'^ajax/get_results/$', views.get_results, name='get_results'),
    url(r'^public/$', views.public, name='public'),
    url(r'^nonpublic/$', views.nonpublic, name='nonpublic'),
    url(r'^login/$', views.nonpublic, name='force_login'),
    url(r'^logout/$', views.logout_view, name='logout'),
    url(r'^logff/$', views.logout_view, name='logout'),
    url(r'^$', views.index, name='index'),
]
