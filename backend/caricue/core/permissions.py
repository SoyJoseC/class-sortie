from rest_framework import permissions


class IsTeacherOwner(permissions.IsAuthenticated):
    """Object-level ownership check.

    Every teacher-facing model either has a `teacher` field or exposes an
    `owner_teacher_id` property that resolves to one. Objects that do not
    belong to the requesting teacher are rejected here; querysets are *also*
    filtered by owner in each viewset so unauthorised ids surface as 404
    rather than 403 (no existence oracle).
    """

    def has_object_permission(self, request, view, obj) -> bool:
        owner_id = getattr(obj, "owner_teacher_id", None)
        if owner_id is None:
            owner_id = getattr(obj, "teacher_id", None)
        return owner_id is not None and owner_id == request.user.pk


class OwnedQuerysetMixin:
    """Restricts a viewset's queryset to rows owned by `request.user`.

    Subclasses set `owner_field` to the ORM path from the model to the owning
    teacher (default: ``teacher``).
    """

    owner_field = "teacher"
    permission_classes = [IsTeacherOwner]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(**{self.owner_field: user})
