from django.urls import path

from . import views

app_name = 'census'

# the name parameter is used in {% url %} in the templates
urlpatterns = [
    path("", views.index, name='index'),
    path("listing/", views.ListingView.as_view(), name="listing"),
    path("map/", views.MapView.as_view(), name="map"),
    path("view/<int:pk>/", views.FarmView.as_view(), name="view"),
    path("create/", views.FarmCreateView.as_view(), name="create"),
    path("thanks/<int:farm_id>/", views.thanks, name="thanks"),
    path("update/<str:token>/", views.FarmUpdateView.as_view(), name="update"),
    path("cgu/", views.cgu, name='cgu')
]