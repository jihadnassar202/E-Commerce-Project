from django.urls import path
from . import views
urlpatterns = [
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/update/<int:product_id>/", views.cart_update, name="cart_update"),
    path("cart/remove/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("cart/increment/<int:product_id>/", views.cart_increment, name="cart_increment"),
    path("cart/decrement/<int:product_id>/", views.cart_decrement, name="cart_decrement"),
    path("checkout/", views.checkout, name="checkout"),
    path("success/<int:order_id>/", views.order_success, name="order_success"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("my-orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/", views.orders_list, name="orders_list"),
    path("orders/item/<int:item_id>/update-status/", views.order_item_update_status, name="order_item_update_status"),
]