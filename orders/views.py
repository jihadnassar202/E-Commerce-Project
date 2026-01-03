from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from products.models import Product
from core.utils import is_seller
from .models import Order, OrderItem

# Currency precision: 2 decimal places
CURRENCY_PRECISION = Decimal("0.01")

# Cart expiry: 24 hours
CART_EXPIRY_HOURS = 24


def _quantize_currency(value):
    """Round Decimal value to 2 decimal places for currency."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CURRENCY_PRECISION, rounding=ROUND_HALF_UP)


def _get_cart(session):
    """
    Cart stored in session as:
    session["cart"] = { "<product_id>": <qty>, ... }
    session["cart_created_at"] = timestamp
    product_id keys are ALWAYS strings.
    """
    cart = session.get("cart")
    if cart is None:
        cart = {}
        session["cart"] = cart
        session["cart_created_at"] = timezone.now().isoformat()
    elif "cart_created_at" not in session:
        # Initialize timestamp for existing carts
        session["cart_created_at"] = timezone.now().isoformat()
    return cart


def _is_cart_expired(session):
    """Check if cart has expired (24 hours)."""
    cart_created_at_str = session.get("cart_created_at")
    if not cart_created_at_str:
        return False
    try:
        cart_created_at = datetime.fromisoformat(cart_created_at_str)
        if timezone.is_naive(cart_created_at):
            cart_created_at = timezone.make_aware(cart_created_at)
        expiry_time = cart_created_at + timedelta(hours=CART_EXPIRY_HOURS)
        return timezone.now() > expiry_time
    except (ValueError, TypeError):
        return False


def _validate_and_clean_cart(session):
    """
    Validate and clean cart to remove invalid states:
    - Remove items with negative or zero quantities
    - Remove items for products that don't exist or are inactive
    - Adjust quantities that exceed available stock
    Returns: (cleaned_cart, removed_items)
    """
    cart = _get_cart(session)
    if not cart:
        return cart, []

    # Get all product IDs from cart
    cart_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
    if not cart_ids:
        session["cart"] = {}
        return {}, []

    # Fetch all products in one query
    products = Product.objects.filter(
        id__in=cart_ids, is_active=True).only('id', 'stock')
    product_map = {p.id: p for p in products}

    cleaned_cart = {}
    removed_items = []

    for pid_str, qty_str in cart.items():
        try:
            pid = int(pid_str)
            qty = int(qty_str)
        except (ValueError, TypeError):
            # Invalid product ID or quantity format
            removed_items.append(pid_str)
            continue

        # Skip if product doesn't exist or is inactive
        if pid not in product_map:
            removed_items.append(pid_str)
            continue

        product = product_map[pid]

        # Remove items with invalid quantities
        if qty <= 0:
            removed_items.append(pid_str)
            continue

        # Adjust quantity if it exceeds stock
        if qty > product.stock:
            if product.stock > 0:
                cleaned_cart[pid_str] = product.stock
            else:
                removed_items.append(pid_str)
        else:
            cleaned_cart[pid_str] = qty

    # Update session if cart was modified
    if len(cleaned_cart) != len(cart) or any(pid_str not in cleaned_cart for pid_str in cart.keys()):
        session["cart"] = cleaned_cart
        session.modified = True

    return cleaned_cart, removed_items


def _get_cart_count(session):
    """Get total number of items in cart."""
    cart = _get_cart(session)
    count = 0
    for qty_str in cart.values():
        try:
            qty = int(qty_str)
            if qty > 0:
                count += qty
        except (ValueError, TypeError):
            continue
    return count


def _calculate_cart_total(cart):
    """Calculate total price of all items in cart."""
    if not cart:
        return Decimal("0.00")

    ids = []
    for pid_str in cart.keys():
        try:
            ids.append(int(pid_str))
        except (ValueError, TypeError):
            continue

    if not ids:
        return Decimal("0.00")

    products = Product.objects.filter(
        id__in=ids, is_active=True).only('id', 'price')
    product_map = {p.id: p.price for p in products}

    total = Decimal("0.00")
    for pid_str, qty_str in cart.items():
        try:
            pid = int(pid_str)
            qty = max(0, int(qty_str))  # Ensure non-negative
        except (ValueError, TypeError):
            continue

        if pid in product_map and qty > 0:
            line_total = _quantize_currency(product_map[pid] * qty)
            total += line_total

    return _quantize_currency(total)


def cart_detail(request):
    # Check if cart has expired
    if _is_cart_expired(request.session):
        request.session["cart"] = {}
        request.session["cart_created_at"] = timezone.now().isoformat()
        request.session.modified = True
        messages.warning(request, _("Your cart has expired and has been cleared. Items are reserved for 24 hours."))
        return redirect("product_list")
    
    # Validate and clean cart to remove invalid states
    cleaned_cart, removed_items = _validate_and_clean_cart(request.session)

    # Show message if items were removed
    if removed_items:
        messages.warning(
            request,
            _("Some items were removed from your cart due to invalid quantities or unavailable products.")
        )

    ids = [int(pid) for pid in cleaned_cart.keys()] if cleaned_cart else []
    products = Product.objects.filter(
        id__in=ids, is_active=True).select_related("category")

    items = []
    total = Decimal("0.00")

    for p in products:
        qty = int(cleaned_cart.get(str(p.id), 0))
        if qty > 0:  # Double-check quantity is valid
            line_total = _quantize_currency(p.price * qty)
            items.append({"product": p, "quantity": qty,
                         "line_total": line_total})
            total += line_total

    return render(request, "orders/cart_detail.html", {"items": items, "total": _quantize_currency(total)})


@require_POST
def cart_add(request, product_id):
    # Check if cart has expired, reset if so
    if _is_cart_expired(request.session):
        request.session["cart"] = {}
        request.session["cart_created_at"] = timezone.now().isoformat()
        request.session.modified = True
    
    product = get_object_or_404(Product, pk=product_id, is_active=True)

    # Ownership validation: prevent sellers from purchasing their own products
    if request.user.is_authenticated and product.owner == request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': _("You cannot purchase your own products.")
            }, status=400)
        messages.error(request, _("You cannot purchase your own products."))
        return redirect("product_detail", pk=product_id)

    if product.stock <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': _("%(product_name)s is sold out.") % {'product_name': product.name}
            }, status=400)
        messages.error(request, _("%(product_name)s is sold out.") % {'product_name': product.name})
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

    # Validate current quantity in cart
    try:
        current_qty = max(0, int(cart.get(pid, 0)))
    except (ValueError, TypeError):
        current_qty = 0

    new_qty = current_qty + qty_to_add

    # Validate new quantity
    if new_qty <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': _('Quantity must be greater than zero.')
            }, status=400)
        messages.error(request, _('Quantity must be greater than zero.'))
        return redirect("product_list")

    if new_qty > product.stock:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': _("Only %(stock)d left in stock.") % {'stock': product.stock}
            }, status=400)
        messages.error(request, _("Only %(stock)d left in stock.") % {'stock': product.stock})
        return redirect("product_list")

    cart[pid] = new_qty
    request.session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': _("Added %(product_name)s to cart.") % {'product_name': product.name},
            'cart_count': _get_cart_count(request.session),
            'new_quantity': new_qty
        })

    messages.success(request, _("Added %(product_name)s to cart.") % {'product_name': product.name})
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
    except (ValueError, TypeError):
        qty = 1

    # Validate quantity
    if qty <= 0:
        del cart[pid]
        request.session.modified = True
        messages.success(request, _("Item removed."))
        return redirect("cart_detail")

    product = get_object_or_404(Product, pk=product_id, is_active=True)

    # Ownership validation: prevent sellers from purchasing their own products
    if request.user.is_authenticated and product.owner == request.user:
        del cart[pid]
        request.session.modified = True
        messages.error(request, "You cannot purchase your own products. Item removed from cart.")
        return redirect("cart_detail")

    # Validate quantity doesn't exceed stock
    if qty > product.stock:
        if product.stock <= 0:
            del cart[pid]
            request.session.modified = True
            messages.error(
                request, _("%(product_name)s is sold out and has been removed from your cart.") % {'product_name': product.name})
        else:
            messages.error(
                request, _("Only %(stock)d left in stock for %(product_name)s. Quantity adjusted.") % {'stock': product.stock, 'product_name': product.name})
            qty = product.stock

    cart[pid] = qty
    request.session.modified = True
    messages.success(request, _("Quantity updated."))
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
                'message': _('Removed item from cart.'),
                'cart_total': str(cart_total),
                'cart_count': _get_cart_count(request.session)
            })

        messages.success(request, _("Removed item from cart."))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'message': _('Item not found in cart.')
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

    # Ownership validation: prevent sellers from purchasing their own products
    if request.user.is_authenticated and product.owner == request.user:
        del cart[pid]
        request.session.modified = True
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': _("You cannot purchase your own products. Item removed from cart."),
                'removed': True
            }, status=400)
        messages.error(request, _("You cannot purchase your own products. Item removed from cart."))
        return redirect("cart_detail")

    # Validate current quantity
    try:
        current_qty = max(0, int(cart.get(pid, 0)))
    except (ValueError, TypeError):
        current_qty = 0

    new_qty = current_qty + 1

    if new_qty > product.stock:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': _("Only %(stock)d left in stock.") % {'stock': product.stock},
                'quantity': current_qty,
                'max_quantity': product.stock
            }, status=400)
        messages.error(request, _("Only %(stock)d left in stock.") % {'stock': product.stock})
        return redirect("cart_detail")

    cart[pid] = new_qty
    request.session.modified = True

    # Calculate updated totals
    line_total = _quantize_currency(product.price * new_qty)
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

    # Validate current quantity
    try:
        current_qty = max(0, int(cart.get(pid, 0)))
    except (ValueError, TypeError):
        current_qty = 0

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
                'message': _('Item removed from cart.'),
                'cart_total': str(cart_total),
                'cart_count': _get_cart_count(request.session)
            })
        else:
            line_total = _quantize_currency(product.price * new_qty)
            return JsonResponse({
                'success': True,
                'removed': False,
                'quantity': new_qty,
                'line_total': str(line_total),
                'cart_total': str(cart_total),
                'cart_count': _get_cart_count(request.session)
            })

    if removed:
        messages.success(request, _("Item removed from cart."))
    return redirect("cart_detail")


@login_required
def checkout(request):
    # Check if cart has expired
    if _is_cart_expired(request.session):
        request.session["cart"] = {}
        request.session["cart_created_at"] = timezone.now().isoformat()
        request.session.modified = True
        messages.warning(request, _("Your cart has expired and has been cleared. Items are reserved for 24 hours."))
        return redirect("cart_detail")
    
    # Validate and clean cart before checkout
    cleaned_cart, removed_items = _validate_and_clean_cart(request.session)

    if not cleaned_cart:
        if removed_items:
            messages.warning(
                request, _("Your cart was cleared due to invalid items."))
        else:
            messages.error(request, _("Your cart is empty."))
        return redirect("product_list")

    ids = [int(pid) for pid in cleaned_cart.keys()]
    products = list(Product.objects.filter(id__in=ids, is_active=True))

    # Build items for display regardless of method
    items = []
    total = Decimal("0.00")
    for p in products:
        qty = int(cleaned_cart.get(str(p.id), 0))
        if qty > 0:  # Only include valid quantities
            line_total = _quantize_currency(p.price * qty)
            items.append({"product": p, "quantity": qty,
                         "line_total": line_total})
            total += line_total

    total = _quantize_currency(total)

    if request.method == "POST":
        errors = []

        try:
            with transaction.atomic():
                # Lock products for update to prevent race conditions
                locked_products = (
                    Product.objects.select_for_update()
                    .filter(id__in=ids, is_active=True)
                )
                locked_map = {p.id: p for p in locked_products}

                # Validate all products before processing
                for pid_str, qty_str in cleaned_cart.items():
                    try:
                        pid = int(pid_str)
                        qty = int(qty_str)
                    except (ValueError, TypeError):
                        errors.append(
                            _("Invalid quantity for product ID %(pid)s.") % {'pid': pid_str})
                        continue

                    if qty <= 0:
                        errors.append(
                            _("Invalid quantity (must be greater than zero) for product ID %(pid)s.") % {'pid': pid_str})
                        continue

                    product = locked_map.get(pid)

                    if not product:
                        errors.append(
                            _("Product ID %(pid)s is no longer available.") % {'pid': pid_str})
                        continue

                    # Ownership validation: prevent sellers from purchasing their own products
                    if request.user.is_authenticated and product.owner == request.user:
                        errors.append(
                            _("You cannot purchase your own product: %(product_name)s.") % {'product_name': product.name})
                        continue

                    if product.stock <= 0:
                        errors.append(_("%(product_name)s is sold out.") % {'product_name': product.name})
                    elif product.stock < qty:
                        errors.append(
                            _("%(product_name)s: Only %(stock)d available, but %(qty)d requested.") % {
                                'product_name': product.name, 'stock': product.stock, 'qty': qty
                            }
                        )

                # If there are any errors, show them all and abort
                if errors:
                    for error in errors:
                        messages.error(request, error)
                    return redirect("cart_detail")

                # All validations passed, create order
                order = Order.objects.create(
                    user=request.user,
                    status=Order.STATUS_PENDING,
                    is_paid=False,
                    total_amount=Decimal("0.00"),
                )

                running_total = Decimal("0.00")
                for pid_str, qty_str in cleaned_cart.items():
                    pid = int(pid_str)
                    qty = int(qty_str)
                    product = locked_map[pid]

                    line_total = _quantize_currency(product.price * qty)
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=qty,
                        price_at_purchase=product.price,
                    )
                    running_total += line_total
                    product.stock -= qty
                    product.save(update_fields=["stock"])

                order.total_amount = _quantize_currency(running_total)
                order.status = Order.STATUS_PAID  # mock payment success
                order.is_paid = True
                order.save(update_fields=["total_amount", "status", "is_paid"])

                request.session["cart"] = {}
                request.session.modified = True

                messages.success(
                    request, _("Order #%(order_id)d created successfully!") % {'order_id': order.pk})
                return redirect("order_success", order_id=order.pk)

        except ValueError as e:
            messages.error(request, _("Invalid data in cart: %(error)s") % {'error': str(e)})
            return redirect("cart_detail")
        except Exception as e:
            # Log the actual error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Checkout error: {str(e)}", exc_info=True)

            messages.error(
                request,
                _("An error occurred during checkout. Please try again. If the problem persists, contact support.")
            )
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


@login_required
def orders_list(request):
    """Orders list view: sellers see their items, admins see all orders."""
    if is_seller(request.user) and not request.user.is_staff:
        # Seller view: show orders containing their products
        orders = Order.objects.filter(
            items__product__owner=request.user
        ).distinct().prefetch_related("items__product", "items__product__owner", "user").order_by("-created_at")
    elif request.user.is_staff:
        # Admin view: show all orders
        orders = Order.objects.all().prefetch_related("items__product", "items__product__owner", "user").order_by("-created_at")
    else:
        # Regular user: redirect to my_orders
        return redirect("my_orders")
    
    paginator = Paginator(orders, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "orders/orders_list.html", {"page_obj": page_obj, "is_seller_view": is_seller(request.user) and not request.user.is_staff})


@login_required
@require_POST
def order_item_update_status(request, item_id):
    """Update order item status. Sellers can only update items for their own products."""
    item = get_object_or_404(OrderItem, pk=item_id)
    
    # Permission check: sellers can only update items for their own products, admins can update any
    if not request.user.is_staff:
        if not is_seller(request.user) or item.product.owner != request.user:
            messages.error(request, _("You don't have permission to update this item."))
            return redirect("orders_list")
    
    new_status = request.POST.get("status")
    valid_statuses = [choice[0] for choice in OrderItem.STATUS_CHOICES]
    
    if new_status not in valid_statuses:
        messages.error(request, _("Invalid status."))
        return redirect("orders_list")
    
    item.status = new_status
    item.save()
    messages.success(request, _("Order item status updated."))
    return redirect("orders_list")
