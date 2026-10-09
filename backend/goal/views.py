from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from .models import Goal
from .periods import parse_period, scope_name
from .serializers import GoalSerializer
from .statistics import count_books, monthly_counts, period_metadata


def select_goal(user, year, month):
    goals = Goal.objects.filter(user=user).order_by('id')
    if year is not None:
        goals = goals.filter(year=year, month=month)
    return goals.first()


def goal_period(goal):
    if goal is None:
        return None
    return {'year': goal.year, 'month': goal.month, 'scope': scope_name(goal.year, goal.month)}


class GoalViewSet(ModelViewSet):
    serializer_class = GoalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Goal.objects.filter(user=self.request.user).order_by('id')
        year, month = parse_period(self.request.query_params)
        if year is not None:
            queryset = queryset.filter(year=year, month=month)
        return queryset

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user)
        except IntegrityError:
            # The database constraint also protects concurrent scoped creates.
            raise ValidationError({'period': '해당 기간 목표가 이미 있습니다.'})


class GoalProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year, month = parse_period(request.query_params)
        goal = select_goal(request.user, year, month)
        # Preserve the original no-query progress 404 and all-time counting contract.
        if goal is None and year is None:
            return Response({'error': '설정된 목표가 없습니다.', **period_metadata(year, month)}, status=404)
        total = goal.total_books if goal else 0
        count = count_books(request.user, year, month)
        return Response({'goal_id': goal.pk if goal else None, 'goal_period': goal_period(goal), 'goal_books': total,
                         'read_books': count, 'progress': round(count / total * 100, 2) if total > 0 else 0,
                         **period_metadata(year, month)})


class MonthlyReadingProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year, month = parse_period(request.query_params)
        goal = select_goal(request.user, year, month)
        # No-query monthly data stays in the current local year, independent of a target.
        year = year if year is not None else timezone.localtime().year
        monthly = monthly_counts(request.user, year, month)
        return Response({'goal_id': goal.pk if goal else None, 'goal_period': goal_period(goal),
                         'goal_books': goal.total_books if goal else 0,
                         'read_books': count_books(request.user, year, month),
                         'monthly_reading': monthly, **period_metadata(year, month)})
