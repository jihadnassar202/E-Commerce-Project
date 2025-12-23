SELLER_GROUP_NAME = "Seller"


def is_seller(user):
    """
    Return True when the user is authenticated and either a superuser
    or a member of the Seller group.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=SELLER_GROUP_NAME).exists()
