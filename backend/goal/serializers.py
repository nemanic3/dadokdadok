from rest_framework import serializers
from .statistics import count_books, period_metadata
from .models import Goal
from .periods import parse_period, scope_name


class GoalSerializer(serializers.ModelSerializer):
    # Persisted legacy counters are retained, but never accepted or trusted by APIs.
    total_books = serializers.IntegerField(min_value=1, max_value=2147483647, required=True)
    year = serializers.IntegerField(min_value=1, max_value=9999, allow_null=True, required=False)
    month = serializers.IntegerField(min_value=1, max_value=12, allow_null=True, required=False)
    read_books = serializers.SerializerMethodField()
    scope = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = ['id', 'total_books', 'read_books', 'year', 'month', 'scope']
        validators = []  # Owner-aware nullable-period validation below.

    def validate(self, attrs):
        request = self.context['request']
        query_year, query_month = parse_period(request.query_params)
        if self.instance is None and query_year is not None:
            for key, value in [('year', query_year), ('month', query_month)]:
                if key in attrs and attrs[key] != value:
                    raise serializers.ValidationError({key: '요청 기간과 목표 기간이 다릅니다.'})
                attrs[key] = value
        if self.instance is not None:
            for key in ['year', 'month']:
                if key in attrs and attrs[key] != getattr(self.instance, key):
                    raise serializers.ValidationError({key: '기간을 옮길 수 없습니다. 새 목표를 만드세요.'})
        year = attrs.get('year', self.instance.year if self.instance else None)
        month = attrs.get('month', self.instance.month if self.instance else None)
        if month is not None and year is None:
            raise serializers.ValidationError({'month': '월 목표에는 연도가 필요합니다.'})
        if year is not None:
            existing = Goal.objects.filter(user=request.user, year=year, month=month)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({'period': '해당 기간 목표가 이미 있습니다.'})
        return attrs

    def get_scope(self, goal):
        return scope_name(goal.year, goal.month)

    def get_read_books(self, goal):
        return count_books(goal.user, goal.year, goal.month)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(period_metadata(instance.year, instance.month))
        return data
