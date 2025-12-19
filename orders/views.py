from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from products.models import Product
from .models import Order, OrderItem

def _get_cart(session):
    cart = session.get("cart")
    if cart is None:
        cart = {}
        session["cart"] = cart
    return cart

def cart_detail(request):
    cart = _get_cart(request.session)

    product_ids = list(cart.keys())
    products = Product.objects.filter(id__in=product_ids).select_related("category")

    items = []
    total = Decimal("0.00")
    for p in products:
        qty = int(cart.get(str(p.id), 0)) if str(p.id) in cart else int(cart.get(p.id, 0))
        # normalize keys to string
        qty = int(cart.get(str(p.id), cart.get(p.id, 0)))
        line_total = (p.price * qty) if qty else Decimal("0.00")
        items.append({"product": p, "quantity": qty, "line_total": line_total})
        total += line_total

    return render(request, "orders/cart_detail.html", {"items": items, "total": total})

def cart_add(request, product_id):
    if request.method != "POST":
        return redirect("product_detail", pk=product_id)

    product = get_object_or_404(Product, pk=product_id, is_active=True)
    cart = _get_cart(request.session)

    pid = str(product.id)
    cart[pid] = int(cart.get(pid, 0)) + 1

    request.session.modified = True
    messages.success(request, f"Added {product.name} to cart.")
    return redirect("cart_detail")

def cart_remove(request, product_id):
    if request.method != "POST":
        return redirect("cart_detail")

    cart = _get_cart(request.session)
    pid = str(product_id)

    if pid in cart:
        del cart[pid]
        request.session.modified = True
        messages.success(request, "Removed item from cart.")
    return redirect("cart_detail")

@login_required
def checkout(request):
    cart = _get_cart(request.session)
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("product_list")

    if request.method == "POST":
        product_ids = list(cart.keys())
        products = Product.objects.filter(id__in=product_ids)

        # create order
        order = Order.objects.create(user=request.user, is_paid=False)

        for p in products:
            qty = int(cart.get(str(p.id), 0))
            if qty <= 0:
                continue
            OrderItem.objects.create(
                order=order,
                product=p,
                quantity=qty,
                price_at_purchase=p.price,
            )

        # clear cart
        request.session["cart"] = {}
        request.session.modified = True

        messages.success(request, f"Order #{order.pk} created ✅")
        return redirect("order_success", order_id=order.pk)

    return render(request, "orders/checkout.html")

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, "orders/order_success.html", {"order": order})
