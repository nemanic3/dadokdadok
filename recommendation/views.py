from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny
from .models import Recommendation
from .serializers import RecommendationSerializer

class RecommendationViewSet(ModelViewSet):
    queryset = Recommendation.objects.all()
    serializer_class = RecommendationSerializer
    permission_classes = [AllowAny]  # 테스트용으로 모든 사용자 허용

    def get_queryset(self):
        # 인증되지 않은 사용자는 빈 queryset 반환
        if self.request.user.is_anonymous:
            return Recommendation.objects.none()
        # 인증된 사용자는 자신의 추천 데이터만 반환
        return self.queryset.filter(user=self.request.user)