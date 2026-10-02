from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from review.models import Review
from goal.models import Goal

@receiver(post_save, sender=Review)
def update_goal_progress(sender, instance, created, **kwargs):
    """ 사용자가 리뷰를 작성하면 목표 진행률을 자동 업데이트 """
    if created:
        user = instance.user
        book = instance.book

        # ✅ 중복 리뷰인지 확인 (사용자가 같은 책에 여러 리뷰 작성 방지)
        if Review.objects.filter(user=user, book=book).count() > 1:
            return

        # ✅ 사용자의 목표 업데이트
        goals = Goal.objects.filter(user=user)
        for goal in goals:
            goal.read_books += 1
            goal.save()

@receiver(post_delete, sender=Review)
def decrease_goal_progress(sender, instance, **kwargs):
    """ 사용자가 리뷰를 삭제하면 목표 진행률을 감소 """
    user = instance.user
    book = instance.book

    # ✅ 사용자의 목표 업데이트
    goals = Goal.objects.filter(user=user)
    for goal in goals:
        if goal.read_books > 0:
            goal.read_books -= 1  # ✅ 읽은 책 개수 감소
            goal.save()