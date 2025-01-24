from rest_framework import serializers
from .models import Goal

class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = ['id', 'user', 'goal_count', 'progress', 'created_at']
        read_only_fields = ['user', 'created_at']  # 사용자와 생성 시간은 읽기 전용
