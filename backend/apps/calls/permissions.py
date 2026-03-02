from rest_framework import permissions


class IsOperator(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'operator')


class IsChiefOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in ('chief', 'admin')
        )


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')


class CallPermission(permissions.BasePermission):
    """
    Operators can read/write their own calls.
    Chief/admin can read all calls.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in ('chief', 'admin'):
            return True
        # Operator: can access only own calls
        return obj.operator_id == user.id
