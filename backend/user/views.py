from django.contrib.auth import get_user_model, authenticate
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from .serializers import UserSerializer, SignupSerializer
from django.conf import settings
from django.shortcuts import get_object_or_404  # ✅ Import 추가
import os

User = get_user_model()

# ✅ 홈 API
def home(request):
    return JsonResponse({"message": "Welcome to DadokDadok API!"})

# ✅ 회원가입 API
class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Signup successful!", "user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ✅ 로그인 API (JWT 인증)
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Login successful!",
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)

# ✅ 로그아웃 API (JWT 토큰 블랙리스트 적용 가능)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            token = RefreshToken(refresh_token)
            token.blacklist()  # RefreshToken을 블랙리스트에 추가
            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

# ✅ 회원 정보 조회, 수정 및 삭제 API
class UserViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

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
    """ 사용자가 선택할 수 있는 프로필 이미지 리스트 제공 """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "profile_images": [
                f"{settings.MEDIA_URL}profile_images/profile_image.svg",
                f"{settings.MEDIA_URL}profile_images/profile_image1.svg",
                f"{settings.MEDIA_URL}profile_images/profile_image2.svg",
                f"{settings.MEDIA_URL}profile_images/profile_image3.svg",
                f"{settings.MEDIA_URL}profile_images/profile_image4.svg",
                f"{settings.MEDIA_URL}profile_images/profile_image5.svg",
            ]
        })


class UpdateProfileImageView(APIView):
    """ 사용자가 선택한 프로필 이미지를 저장 """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        selected_image = request.data.get("profile_image")  # 사용자가 선택한 이미지 URL

        # ✅ 선택한 이미지가 미리 제공된 이미지 목록에 있는지 확인
        allowed_images = [
            "profile_images/profile_image.svg",
            "profile_images/profile_image1.svg",
            "profile_images/profile_image2.svg",
            "profile_images/profile_image3.svg",
            "profile_images/profile_image4.svg",
            "profile_images/profile_image5.svg",
        ]

        if selected_image not in allowed_images:
            return Response({"error": "올바른 프로필 이미지를 선택하세요."}, status=400)

        # ✅ 유저 프로필 이미지 업데이트
        user.profile_image = selected_image
        user.save()

        return Response({"message": "프로필 이미지가 업데이트되었습니다.", "profile_image": f"{settings.MEDIA_URL}{selected_image}"}, status=200)

class UserProfileView(APIView):
    """ 특정 사용자의 프로필 조회 (닉네임 기반) """
    permission_classes = [AllowAny]  # ✅ 누구나 조회 가능

    def get(self, request, nickname):
        user = get_object_or_404(User, nickname=nickname)  # ✅ 닉네임으로 사용자 검색
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)