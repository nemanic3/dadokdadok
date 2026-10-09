import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.db import transaction
from .serializers import check_password_policy
from .security import revoke_refresh_tokens
from django.utils.encoding import force_bytes
from urllib.parse import urlencode, urlsplit
from django.core.mail import send_mail
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .throttles import RecoveryIPThrottle, ResetIPThrottle, RecoveryIdentityThrottle, ResetIdentityThrottle

User = get_user_model()
logger = logging.getLogger(__name__)
RECOVERY_MESSAGE = '등록된 이메일이면 계정 복구 안내가 전송됩니다.'


class RecoveryEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


def unique_recovery_user(email):
    # Count inactive and legacy duplicate accounts too: never choose one silently.
    users = list(User.objects.filter(email__iexact=email.strip())[:2])
    if len(users) == 1 and users[0].is_active and users[0].has_usable_password():
        return users[0]
    return None


def send_recovery_mail(user, subject, body):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except (SMTPException, OSError):
        # Do not include mailbox, token, or SMTP exception contents in logs/responses.
        logger.warning('Account recovery mail delivery failed.')


class FindIdView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryIPThrottle, RecoveryIdentityThrottle]

    def post(self, request):
        serializer = RecoveryEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = unique_recovery_user(serializer.validated_data['email'])
        if user:
            send_recovery_mail(user, '다독다독 아이디 안내', f'다독다독 아이디: {user.username}')
        return Response({'message': RECOVERY_MESSAGE})


class ResetConfirmationSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=256)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def get_throttles(self):
        confirming = isinstance(self.request.data, dict) and any(key in self.request.data for key in ('uid', 'token', 'new_password'))
        return [ResetIPThrottle(), ResetIdentityThrottle()] if confirming else [RecoveryIPThrottle(), RecoveryIdentityThrottle()]

    def post(self, request):
        if isinstance(request.data, dict) and any(key in request.data for key in ('uid', 'token', 'new_password')):
            return self.confirm(request)
        serializer = RecoveryEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        base = getattr(settings, 'PASSWORD_RESET_URL', 'http://127.0.0.1:5500/screen/find-account.html')
        try:
            parsed = urlsplit(base)
            valid = bool(parsed.hostname and parsed.path and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)
            secure = parsed.scheme == 'https' or (settings.DEBUG and parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1'))
        except ValueError:
            valid = secure = False
        if not valid or not secure:
            logger.warning('Password reset URL must be a trusted HTTPS frontend URL (HTTP loopback is development-only).')
            return Response({'error': '계정 복구 설정을 확인해주세요.'}, status=503)
        user = unique_recovery_user(serializer.validated_data['email'])
        if user:
            query = urlencode({'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                               'token': default_token_generator.make_token(user)})
            link = f'{base}?{query}'
            send_recovery_mail(user, '다독다독 비밀번호 재설정', f'아래 링크에서 비밀번호를 재설정해주세요.\n{link}\n본인이 요청하지 않았다면 무시해주세요.')
        return Response({'message': RECOVERY_MESSAGE})

    def confirm(self, request):
        serializer = ResetConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        invalid = {'error': '링크가 올바르지 않거나 만료되었습니다.'}
        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            if not uid.isdecimal() or len(uid) > 20:
                return Response(invalid, status=400)
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=uid)
                if not user.is_active or not user.has_usable_password() or not default_token_generator.check_token(user, data['token']):
                    return Response(invalid, status=400)
                check_password_policy(data['new_password'], user, 'new_password')
                if user.check_password(data['new_password']):
                    raise serializers.ValidationError({'new_password': '현재 비밀번호와 다른 비밀번호를 입력해주세요.'})
                user.set_password(data['new_password'])
                user.save(update_fields=['password'])
                revoke_refresh_tokens(user)
        except (ValueError, UnicodeDecodeError, OverflowError, User.DoesNotExist):
            return Response(invalid, status=400)
        return Response({'message': '비밀번호가 변경되었습니다. 다시 로그인해주세요.'})
