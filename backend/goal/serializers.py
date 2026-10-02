from rest_framework import serializers
from .models import Goal

class GoalSerializer(serializers.ModelSerializer):
    """ 연간 목표 설정을 위한 시리얼라이저 (목표 책 수만 입력) """
    class Meta:
        model = Goal
        fields = ['id', 'total_books', 'read_books']