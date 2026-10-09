from copy import copy

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .security import revoke_refresh_tokens
from .profile_images import ProfileImageField
from dadokdadok.constraints import is_unique_conflict

User = get_user_model()


def check_password_policy(password, user, field='password'):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({field: exc.messages})


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, max_length=254)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if not attrs.get('username') and not attrs.get('email'):
            raise serializers.ValidationError({'username': '아이디 또는 이메일을 입력해주세요.'})
        if attrs.get('username') and attrs.get('email') and attrs['username'] != attrs['email']:
            raise serializers.ValidationError({'username': '로그인 식별자를 하나만 입력해주세요.'})
        return attrs


class EmailValidationMixin:
    def validate_email(self, value):
        value = value.strip().lower()
        matches = User.objects.filter(email__iexact=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError('이미 등록된 이메일입니다.')
        return value


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nickname', 'profile_image']
        read_only_fields = fields


class NormalizedUsernameField(serializers.CharField):
    def to_internal_value(self, data):
        # Normalize before model validators (especially uniqueness and length).
        return User.normalize_username(super().to_internal_value(data))


class SignupSerializer(EmailValidationMixin, serializers.ModelSerializer):
    email = serializers.EmailField(required=True, allow_blank=False)
    profile_image = ProfileImageField(required=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ['username', 'password', 'nickname', 'email', 'profile_image']

    def build_standard_field(self, field_name, model_field):
        field_class, field_kwargs = super().build_standard_field(field_name, model_field)
        if field_name == 'username':
            field_class = NormalizedUsernameField
        return field_class, field_kwargs

    def validate(self, attrs):
        candidate = User(**{key: value for key, value in attrs.items() if key != 'password'})
        check_password_policy(attrs['password'], candidate)
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(**validated_data)
        except IntegrityError as exc:
            # Match only existing unique constraints, never email or
            # unrelated integrity failures; preserve the field error contract.
            for field in ('username', 'nickname'):
                if (is_unique_conflict(exc, 'user', (field,))
                        and User.objects.filter(**{field: validated_data[field]}).exists()):
                    validator = next(value for value in self.fields[field].validators
                                     if isinstance(value, UniqueValidator))
                    raise serializers.ValidationError({field: [validator.message]}, code='unique') from exc
            raise


class UserSerializer(EmailValidationMixin, serializers.ModelSerializer):
    email = serializers.EmailField(required=True, allow_blank=False)
    profile_image = ProfileImageField(required=False)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    current_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = ['id', 'nickname', 'email', 'profile_image', 'password', 'current_password']
        read_only_fields = ['id']

    def validate(self, attrs):
        if 'password' in attrs:
            if not self.instance or not self.instance.check_password(attrs.get('current_password', '')):
                raise serializers.ValidationError({'current_password': '현재 비밀번호를 확인해주세요.'})
            candidate = copy(self.instance)
            for key, value in attrs.items():
                if key not in ('password', 'current_password'):
                    setattr(candidate, key, value)
            check_password_policy(attrs['password'], candidate)
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('current_password', None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if password is not None:
                instance.set_password(password)
                instance.save(update_fields=['password'])
                revoke_refresh_tokens(instance)
        return instance
