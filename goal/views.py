from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Goal
from .serializers import GoalSerializer

class GoalViewSet(viewsets.ModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 현재 로그인한 사용자의 목표만 반환
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # 목표 생성 시 현재 유저를 저장
        serializer.save(user=self.request.user)
