from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsReviewOwner(BasePermission):
    """공개 조회를 유지하고 리뷰 변경은 작성자만 허용한다."""

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or obj.user_id == request.user.pk
