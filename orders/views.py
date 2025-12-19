from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from products.models import Product
from .models import Order, OrderItem


def _get_cart(session):
    """
    Cart stored in session as:
    session["cart"] = { "<product_id>": <qty>, ... }
    product_id keys are ALWAYS strings.
    """
    cart = session.get("cart")
    if cart is None:
        cart = {}
        session["cart"] = cart
    return cart


def cart_detail(request):
    cart = _get_cart(request.session)

    ids = [int(pid) for pid in cart.keys()] if cart else []
    products = Product.objects.filter(id__in=ids, is_active=True).select_related("category")

    items = []
    total = Decimal("0.00")

    for p in products:
        qty = int(cart.get(str(p.id), 0))
        line_total = p.price * qty
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
        ids = [int(pid) for pid in cart.keys()]
        products = Product.objects.filter(id__in=ids, is_active=True)

        order = Order.objects.create(user=request.user, is_paid=False)

        for p in products:
            qty = int(cart.get(str(p.id), 0))
            if qty > 0:
                OrderItem.objects.create(
                    order=order,
                    product=p,
                    quantity=qty,
                    price_at_purchase=p.price,
                )

        request.session["cart"] = {}
        request.session.modified = True

        messages.success(request, f"Order #{order.pk} created ✅")
        return redirect("order_success", order_id=order.pk)

    return render(request, "orders/checkout.html")


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("items__product"), pk=order_id, user=request.user)
    return render(request, "orders/order_success.html", {"order": order})

@login_required
def my_orders(request):
    qs = Order.objects.filter(user=request.user).order_by("-created_at")
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "orders/my_orders.html", {"page_obj": page_obj})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        user=request.user,
    )
    return render(request, "orders/order_detail.html", {"order": order})
