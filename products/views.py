from django.shortcuts import render, get_object_or_404
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .forms import ProductForm
# from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Product, Category
from django.contrib.auth.decorators import permission_required


def product_list(request):
    products = Product.objects.filter(is_active=True).select_related(
        "category").order_by("-created_at")
    return render(request, "products/product_list.html", {"products": products})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    return render(request, "products/product_detail.html", {"product": product})


def product_list(request):
    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    products = Product.objects.filter(
        is_active=True).select_related("category")

    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(
                category__name__icontains=q)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if sort == "price_asc":
        products = products.order_by("price")
    elif sort == "price_desc":
        products = products.order_by("-price")
    else:
        products = products.order_by("-created_at")

    categories = Category.objects.all().order_by("name")

    paginator = Paginator(products, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "categories": categories,
        "page_obj": page_obj,
        "q": q,
        "category_id": category_id,
        "sort": sort,
    }
    return render(request, "products/product_list.html", context)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, "products/product_detail.html", {"product": product})


@permission_required("products.add_product", raise_exception=True)
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.owner = request.user
            product.save()

            messages.success(request, "Product created successfully.")
            return redirect("product_detail", pk=product.pk)
        messages.error(request, "Fix the errors below.")
    else:
        form = ProductForm()

    return render(
        request,
        "products/product_form.html",
        {"form": form, "mode": "create"}
    )


@permission_required("products.change_product", raise_exception=True)
def product_update(request, pk):
    if request.user.is_superuser:
        product = get_object_or_404(Product, pk=pk)
    else:
        product = get_object_or_404(Product, pk=pk, owner=request.user)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect("product_detail", pk=product.pk)
        messages.error(request, "Fix the errors below.")
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "products/product_form.html",
        {"form": form, "mode": "update", "product": product}
    )

@permission_required("products.delete_product", raise_exception=True)
def product_delete(request, pk):
    if request.user.is_superuser:
        product = get_object_or_404(Product, pk=pk)
    else:
        product = get_object_or_404(Product, pk=pk, owner=request.user)

    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted.")
        return redirect("product_list")

    return render(
        request,
        "products/product_confirm_delete.html",
        {"product": product}
    )
