# E-commerce Project (Django + Postgres)

A small e-commerce demo with role-based seller controls, product CRUD with images, dynamic category management, cart/checkout, and AJAX search/filter.

## Stack
- Django 6
- PostgreSQL
- Bootstrap 5
- Pillow (image uploads)

## Setup
1. Create and activate a virtualenv
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Configure env vars (using `python-decouple`):
   ```
   DB_NAME=...
   DB_USER=...
   DB_PASSWORD=...
   DB_HOST=127.0.0.1
   DB_PORT=5432
   ```
4. Run migrations
   ```bash
   python manage.py migrate
   ```
5. Create a superuser
   ```bash
   python manage.py createsuperuser
   ```
6. (Optional) Seed roles via management command if added; otherwise use admin to create the `Seller` group.

7. Run the dev server
   ```bash
   python manage.py runserver
   ```

## Roles & permissions
- **Admin/staff**: can manage users, mark users as Sellers, manage categories, manage any product.
- **Seller**: can create/edit/delete their own products.
- **Buyer (authenticated)**: can browse, add to cart, and checkout.

## Key features
- Product CRUD with image upload, validation, and ownership checks.
- Category model with `is_active`; staff UI for create/update/list.
- Role-based seller gating for create/edit/delete.
- Product listing with Bootstrap cards, server pagination, and AJAX search/filter + clear.
- Cart with quantity updates; checkout creates orders/order items, captures status and total.
- Stock enforcement on add-to-cart/checkout; sold-out cards disable cart button.
- Auth flows: login, logout, register; navbar shows role-aware links.

## Media & static
- Media served via `MEDIA_URL`/`MEDIA_ROOT` in dev (ensure directories exist).
- Requires Pillow for image handling.

## Running checks
```bash
python manage.py check
```

## Notes / gaps to address
- Delete via Bootstrap modal.
- Navbar search/filter placement per spec.
- Sold-out badge shown; consider additional visual cues if needed.