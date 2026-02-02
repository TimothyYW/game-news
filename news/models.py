from django.db import models
from ckeditor.fields import RichTextField

# Create your models here.
class News(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)  # no default here!
    title = models.TextField()
    content = RichTextField()  # rich text editor here
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "news"   # important: match Supabase table name
        managed = False     # Django will NOT try to create/alter this table

    def __str__(self):
        return self.title


   