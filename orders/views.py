from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
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

    if product.stock <= 0:
        messages.error(request, f"{product.name} is sold out.")
        return redirect("product_detail", pk=product_id)

    cart = _get_cart(request.session)
    pid = str(product.id)
    current_qty = int(cart.get(pid, 0))

    if current_qty >= product.stock:
        messages.error(request, f"Only {product.stock} left in stock.")
        return redirect("cart_detail")

    cart[pid] = current_qty + 1
    request.session.modified = True
    messages.success(request, f"Added {product.name} to cart.")
    return redirect("cart_detail")


def cart_update(request, product_id):
    """
    Update quantity for a cart item.
    """
    if request.method != "POST":
        return redirect("cart_detail")

    cart = _get_cart(request.session)
    pid = str(product_id)
    if pid not in cart:
        return redirect("cart_detail")

    try:
        qty = int(request.POST.get("quantity", "1"))
    except ValueError:
        qty = 1

    if qty <= 0:
        del cart[pid]
        request.session.modified = True
        messages.success(request, "Item removed.")
        return redirect("cart_detail")

    product = get_object_or_404(Product, pk=product_id, is_active=True)
    if qty > product.stock:
        messages.error(request, f"Only {product.stock} left in stock.")
        qty = product.stock

    cart[pid] = qty
    request.session.modified = True
    messages.success(request, "Quantity updated.")
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

    ids = [int(pid) for pid in cart.keys()]
    products = list(Product.objects.filter(id__in=ids, is_active=True))

    # Build items for display regardless of method
    items = []
    total = Decimal("0.00")
    for p in products:
        qty = int(cart.get(str(p.id), 0))
        line_total = p.price * qty
        items.append({"product": p, "quantity": qty, "line_total": line_total})
        total += line_total

    if request.method == "POST":
        try:
            with transaction.atomic():
                locked_products = (
                    Product.objects.select_for_update()
                    .filter(id__in=ids, is_active=True)
                )
                locked_map = {p.id: p for p in locked_products}

                for pid_str, qty in cart.items():
                    pid = int(pid_str)
                    product = locked_map.get(pid)
                    if not product or product.stock < qty or product.stock <= 0:
                        messages.error(
                            request,
                            f"Insufficient stock for {product.name if product else 'item'}."
                        )
                        return redirect("cart_detail")

                order = Order.objects.create(
                    user=request.user,
                    status=Order.STATUS_PENDING,
                    is_paid=False,
                    total_amount=Decimal("0.00"),
                )

                running_total = Decimal("0.00")
                for pid_str, qty in cart.items():
                    pid = int(pid_str)
                    product = locked_map[pid]
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=qty,
                        price_at_purchase=product.price,
                    )
                    running_total += product.price * qty
                    product.stock -= qty
                    product.save(update_fields=["stock"])

                order.total_amount = running_total
                order.status = Order.STATUS_PAID  # mock payment success
                order.is_paid = True
                order.save(update_fields=["total_amount", "status", "is_paid"])

                request.session["cart"] = {}
                request.session.modified = True

                messages.success(request, f"Order #{order.pk} created ✅")
                return redirect("order_success", order_id=order.pk)
        except Exception:
            messages.error(request, "Could not complete checkout. Please try again.")
            return redirect("cart_detail")

    return render(request, "orders/checkout.html", {"items": items, "total": total})


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
