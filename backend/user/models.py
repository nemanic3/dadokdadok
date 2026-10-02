from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    """ 유저 모델 (프로필 이미지 선택 가능) """
    PROFILE_IMAGE_CHOICES = [
        ("profile_images/profile_image.svg", "Profile 1"),
        ("profile_images/profile_image1.svg", "Profile 2"),
        ("profile_images/profile_image2.svg", "Profile 3"),
        ("profile_images/profile_image3.svg", "Profile 4"),
        ("profile_images/profile_image4.svg", "Profile 5"),
        ("profile_images/profile_image5.svg", "Profile 6"),
    ]

    profile_image = models.CharField(
        max_length=255,
        choices=PROFILE_IMAGE_CHOICES,
        default="profile_images/profile_image.svg"
    )

    nickname = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'user'

    def __str__(self):
        return self.username
