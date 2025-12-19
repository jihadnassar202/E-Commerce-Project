from django.urls import path
from . import views
urlpatterns = [
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("success/<int:order_id>/", views.order_success, name="order_success"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("my-orders/<int:order_id>/", views.order_detail, name="order_detail"),
]