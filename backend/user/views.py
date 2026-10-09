from django.contrib.auth import get_user_model, authenticate
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from django.http import JsonResponse
from .serializers import UserSerializer, SignupSerializer, PublicUserSerializer, LoginSerializer
from django.db.models import Q
from django.shortcuts import get_object_or_404  # ✅ Import 추가
from .profile_images import ProfileImageSerializer, profile_image_url
from .throttles import SignupIPThrottle, LoginIPThrottle, LoginIdentityThrottle, UserMutationThrottle

User = get_user_model()

# ✅ 홈 API
def home(request):
    return JsonResponse({"message": "Welcome to DadokDadok API!"})

# ✅ 회원가입 API
class SignupView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SignupIPThrottle]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Signup successful!", "user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ✅ 로그인 API (JWT 인증)
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginIPThrottle, LoginIdentityThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        identifier = User.normalize_username(data.get('username') or data['email'])
        candidates = list(User.objects.filter(Q(username=identifier) | Q(email__iexact=identifier))[:2])
        user = None
        if len(candidates) == 1:
            user = authenticate(request=request, username=candidates[0].username, password=data['password'])
        else:
            # Match the password hash cost without selecting an ambiguous account.
            User().set_password(data['password'])
        if user is None:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response(self.login_response(user, refresh), status=status.HTTP_200_OK)

    def login_response(self, user, refresh):
        return {
            "message": "Login successful!",
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": UserSerializer(user).data
        }


class LegacyTokenLoginView(LoginView):
    """Same authentication policy, preserving SimpleJWT's public response keys."""
    def login_response(self, user, refresh):
        return {'access': str(refresh.access_token), 'refresh': str(refresh)}


# ✅ 로그아웃 API (JWT 토큰 블랙리스트 적용 가능)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserMutationThrottle]

    def post(self, request):
        refresh_token = request.data.get('refresh_token') if isinstance(request.data, dict) else None
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
        subject = token.get(jwt_settings.USER_ID_CLAIM)
        if str(subject) != str(getattr(request.user, jwt_settings.USER_ID_FIELD)):
            return Response({'error': 'Token does not belong to this account.'}, status=status.HTTP_403_FORBIDDEN)
        token.blacklist()
        return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)

# ✅ 회원 정보 조회, 수정 및 삭제 API
class UserViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        return [UserMutationThrottle()] if self.action in ('update_profile', 'delete') else super().get_throttles()

    @action(detail=False, methods=["get"])
    def me(self, request):
        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=["put"])
    def update_profile(self, request):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully.", "user": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["delete"])
    def delete(self, request):
        user = request.user
        user.delete()
        return Response({"message": "Account successfully deleted."}, status=status.HTTP_204_NO_CONTENT)


class ProfileImageListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'profile_images': [profile_image_url(value) for value, _ in User.PROFILE_IMAGE_CHOICES]})


class UpdateProfileImageView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserMutationThrottle]

    def post(self, request):
        serializer = ProfileImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected_image = serializer.validated_data['profile_image']
        request.user.profile_image = selected_image
        request.user.save(update_fields=['profile_image'])
        return Response({'message': '프로필 이미지가 업데이트되었습니다.', 'profile_image': profile_image_url(selected_image)})

class UserProfileView(APIView):
    """ 특정 사용자의 프로필 조회 (닉네임 기반) """
    permission_classes = [AllowAny]  # ✅ 누구나 조회 가능

    def get(self, request, nickname):
        user = get_object_or_404(User, nickname=nickname)  # ✅ 닉네임으로 사용자 검색
        serializer = PublicUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)