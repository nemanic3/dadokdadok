from rest_framework import serializers
from .models import Recommendation

class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ['id', 'user', 'book_title', 'created_at']
        read_only_fields = ['user', 'created_at']  # 사용자와 생성 시간은 읽기 전용
