from django.urls import path
from . import views

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("admin/", views.product_list_admin, name="product_list_admin"),
    path("new/", views.product_create, name="product_create"),
    path("<int:pk>/", views.product_detail, name="product_detail"),
    path("<int:pk>/edit/", views.product_update, name="product_update"),
    path("<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("api/list/", views.product_list_api, name="product_list_api"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/new/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_update, name="category_update"),
    path("categories/<int:pk>/deactivate/", views.category_deactivate, name="category_deactivate"),
]
