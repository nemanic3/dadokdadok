from rest_framework.viewsets import ModelViewSet
from .models import Goal
from .serializers import GoalSerializer
from rest_framework.permissions import AllowAny

class GoalViewSet(ModelViewSet):
    """
    A viewset for viewing and editing Goal instances.
    """
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer
    permission_classes = [AllowAny]  # 모든 사용자에게 접근 허용