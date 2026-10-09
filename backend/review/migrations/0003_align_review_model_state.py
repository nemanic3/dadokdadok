import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('review', '0002_initial')]

    # 0002 already enforces user+book uniqueness. Align ORM metadata without
    # rebuilding existing tables or replacing that equivalent unique index.
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterUniqueTogether(name='review', unique_together=set()),
                migrations.AlterField(
                    model_name='comment', name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='comments', to=settings.AUTH_USER_MODEL),
                ),
                migrations.AlterField(
                    model_name='like', name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='likes', to=settings.AUTH_USER_MODEL),
                ),
                migrations.AddConstraint(
                    model_name='review',
                    constraint=models.UniqueConstraint(fields=('user', 'book'), name='unique_user_book_review'),
                ),
            ],
        ),
    ]
