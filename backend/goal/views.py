from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models.functions import TruncMonth
from django.db.models import Count
from datetime import datetime
from .models import Goal
from .serializers import GoalSerializer
from review.models import Review

class GoalViewSet(ModelViewSet):
    """
    연간 목표 설정 (목표 책 수만 입력)
    """
    serializer_class = GoalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Goal.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class GoalProgressView(APIView):
    """
    목표 진행률 조회 (그래프 데이터 제공)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print("GoalProgressView called")
        user = request.user
        goal = Goal.objects.filter(user=user).first()

        if not goal:
            return Response({"error": "설정된 목표가 없습니다."}, status=404)

        # ✅ 사용자가 리뷰를 남긴 유니크한 책 개수 계산 (중복 리뷰 제외)
        read_books_count = Review.objects.filter(user=user).values("book").distinct().count()

        # ✅ 진행률 계산
        progress = (read_books_count / goal.total_books) * 100 if goal.total_books > 0 else 0

        return Response({
            "goal_books": goal.total_books,
            "read_books": read_books_count,
            "progress": round(progress, 2)  # ✅ 소수점 2자리
        }, status=200)

class MonthlyReadingProgressView(APIView):
    """
    월별 독서량 조회 (그래프용 데이터)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        current_year = datetime.now().year

        goal = Goal.objects.filter(user=user).first()
        if not goal:
            return Response({"error": "설정된 목표가 없습니다."}, status=404)

        # ✅ 리뷰 작성 날짜(created_at) 기준으로 월별 독서량 집계
        monthly_reading = (
            Review.objects.filter(user=user, created_at__year=current_year)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        # ✅ YYYY-MM 형식으로 변환
        monthly_data = {entry["month"].strftime("%Y-%m"): entry["count"] for entry in monthly_reading}
        monthly_data = {month: monthly_data.get(month, 0) for month in
                        [f"{current_year}-{str(m).zfill(2)}" for m in range(1, 13)]}

        return Response({
            "goal_books": goal.total_books,
            "read_books": sum(monthly_data.values()),
            "monthly_reading": monthly_data
        }, status=200)