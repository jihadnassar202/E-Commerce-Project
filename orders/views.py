from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

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


def _get_cart_count(session):
    """Get total number of items in cart."""
    cart = _get_cart(session)
    return sum(int(qty) for qty in cart.values() if qty > 0)


def _calculate_cart_total(cart):
    """Calculate total price of all items in cart."""
    if not cart:
        return Decimal("0.00")

    ids = [int(pid) for pid in cart.keys()]
    products = Product.objects.filter(
        id__in=ids, is_active=True).only('id', 'price')
    product_map = {p.id: p.price for p in products}

    total = Decimal("0.00")
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        if pid in product_map:
            total += product_map[pid] * int(qty)

    return total


def cart_detail(request):
    cart = _get_cart(request.session)

    ids = [int(pid) for pid in cart.keys()] if cart else []
    products = Product.objects.filter(
        id__in=ids, is_active=True).select_related("category")

    items = []
    total = Decimal("0.00")

    for p in products:
        qty = int(cart.get(str(p.id), 0))
        line_total = p.price * qty
        items.append({"product": p, "quantity": qty, "line_total": line_total})
        total += line_total

    return render(request, "orders/cart_detail.html", {"items": items, "total": total})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)

    if product.stock <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f"{product.name} is sold out."
            }, status=400)
        messages.error(request, f"{product.name} is sold out.")
        return redirect("product_list")

    # Get quantity from form, default to 1
    try:
        qty_to_add = int(request.POST.get("quantity", "1"))
    except ValueError:
        qty_to_add = 1

    if qty_to_add <= 0:
        qty_to_add = 1

    cart = _get_cart(request.session)
    pid = str(product.id)
    current_qty = int(cart.get(pid, 0))
    new_qty = current_qty + qty_to_add

    if new_qty > product.stock:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f"Only {product.stock} left in stock."
            }, status=400)
        messages.error(request, f"Only {product.stock} left in stock.")
        return redirect("product_list")

    cart[pid] = new_qty
    request.session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f"Added {product.name} to cart.",
            'cart_count': _get_cart_count(request.session),
            'new_quantity': new_qty
        })

    messages.success(request, f"Added {product.name} to cart.")
    return redirect("product_list")


@require_POST
def cart_update(request, product_id):
    """
    Update quantity for a cart item.
    """
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


@require_POST
def cart_remove(request, product_id):
    cart = _get_cart(request.session)
    pid = str(product_id)

    if pid in cart:
        del cart[pid]
        request.session.modified = True

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Calculate updated totals
            cart_total = _calculate_cart_total(cart)
            return JsonResponse({
                'success': True,
                'message': 'Removed item from cart.',
                'cart_total': str(cart_total),
                'cart_count': _get_cart_count(request.session)
            })

        messages.success(request, "Removed item from cart.")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'message': 'Item not found in cart.'
        }, status=404)

    return redirect("cart_detail")


@require_POST
def cart_increment(request, product_id):
    """Increment quantity by 1."""
    cart = _get_cart(request.session)
    pid = str(product_id)

    if pid not in cart:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Item not found in cart.'
            }, status=404)
        return redirect("cart_detail")

    product = get_object_or_404(Product, pk=product_id, is_active=True)
    current_qty = int(cart.get(pid, 0))
    new_qty = current_qty + 1

    if new_qty > product.stock:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f"Only {product.stock} left in stock.",
                'quantity': current_qty,
                'max_quantity': product.stock
            }, status=400)
        messages.error(request, f"Only {product.stock} left in stock.")
        return redirect("cart_detail")

    cart[pid] = new_qty
    request.session.modified = True

    # Calculate updated totals
    line_total = product.price * new_qty
    cart_total = _calculate_cart_total(cart)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'quantity': new_qty,
            'line_total': str(line_total),
            'cart_total': str(cart_total),
            'cart_count': _get_cart_count(request.session),
            'max_quantity': product.stock
        })

    return redirect("cart_detail")


@require_POST
def cart_decrement(request, product_id):
    """Decrement quantity by 1, remove if reaches 0."""
    cart = _get_cart(request.session)
    pid = str(product_id)

    if pid not in cart:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Item not found in cart.'
            }, status=404)
        return redirect("cart_detail")

    product = get_object_or_404(Product, pk=product_id, is_active=True)
    current_qty = int(cart.get(pid, 0))
    new_qty = max(0, current_qty - 1)

    if new_qty == 0:
        del cart[pid]
        removed = True
    else:
        cart[pid] = new_qty
        removed = False

    request.session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Calculate updated totals
        cart_total = _calculate_cart_total(cart)
        if removed:
            return JsonResponse({
                'success': True,
                'removed': True,
                'message': 'Item removed from cart.',
                'cart_total': str(cart_total),
                'cart_count': _get_cart_count(request.session)
            })
        else:
            line_total = product.price * new_qty
            return JsonResponse({
                'success': True,
                'removed': False,
                'quantity': new_qty,
                'line_total': str(line_total),
                'cart_total': str(cart_total),
                'cart_count': _get_cart_count(request.session)
            })

    if removed:
        messages.success(request, "Item removed from cart.")
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
            messages.error(
                request, "Could not complete checkout. Please try again.")
            return redirect("cart_detail")

    return render(request, "orders/checkout.html", {"items": items, "total": total})


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related(
        "items__product"), pk=order_id, user=request.user)
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
