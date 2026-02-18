from django.db import models


class News(models.Model):
    id         = models.UUIDField(primary_key=True, editable=False)
    author_id  = models.UUIDField()
    title      = models.TextField()
    content    = models.TextField()
    image_url  = models.TextField(null=True, blank=True)
    votes      = models.IntegerField(default=0)
    views      = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "news"
        managed  = False
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Profile(models.Model):
    id         = models.UUIDField(primary_key=True, editable=False)
    username   = models.TextField()
    avatar_url = models.TextField(null=True, blank=True)
    bio        = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles"
        managed  = False

    def __str__(self):
        return self.username