from django.core.exceptions import PermissionDenied

from core.utils import is_seller


def seller_required(view_func):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if is_seller(request.user):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped
