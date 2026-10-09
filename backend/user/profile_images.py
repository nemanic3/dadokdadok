from django.conf import settings
from rest_framework import serializers

from .models import CustomUser


def profile_image_url(value):
    # Preserve stored choice keys and the public /media/profile_images/ alias.
    return f'{settings.MEDIA_URL}{value}'


class ProfileImageField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        super().__init__(choices=CustomUser.PROFILE_IMAGE_CHOICES, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, str):
            for value, _ in CustomUser.PROFILE_IMAGE_CHOICES:
                if data == profile_image_url(value):
                    data = value
                    break
        return super().to_internal_value(data)


class PublicProfileImageField(serializers.Field):
    """Expose only a fixed-choice media URL, including for invalid legacy rows."""
    def __init__(self, **kwargs):
        super().__init__(read_only=True, **kwargs)

    def to_representation(self, value):
        if value not in dict(CustomUser.PROFILE_IMAGE_CHOICES):
            value = CustomUser._meta.get_field('profile_image').get_default()
        return profile_image_url(value)


class ProfileImageSerializer(serializers.Serializer):
    profile_image = ProfileImageField()
