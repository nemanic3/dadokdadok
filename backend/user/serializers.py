from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'email', 'profile_image']
        extra_kwargs = {
            'profile_image': {'required': False}  # ✅ 프로필 이미지 필수 입력이 아님
        }

class SignupSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'password', 'nickname', 'email']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_nickname(self, value):
        """ 닉네임 중복 검사 """
        if User.objects.filter(nickname=value).exists():
            raise serializers.ValidationError("이미 사용 중인 닉네임입니다.")
        return value

    def validate_email(self, value):
        """ 이메일 중복 검사 """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 등록된 이메일입니다.")
        return value

    def create(self, validated_data):
        """ 비밀번호 해싱 후 저장 """
        validated_data['password'] = make_password(validated_data['password'])  # ✅ 비밀번호 해싱
        return User.objects.create(**validated_data)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nickname', 'email', 'profile_image']  # ✅ 필요한 필드만 포함