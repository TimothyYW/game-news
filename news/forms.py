from django import forms
from .models import News
from ckeditor.widgets import CKEditorWidget

class NewsForm(forms.ModelForm):
    class Meta:
        model = News
        fields = ["title", "content"]

        widgets = {
            "title": forms.Textarea(
                attrs={
                    "class": "w-full rounded-2xl border-gray-100 bg-gray-50/50 focus:bg-white focus:border-orange-500 focus:ring-4 focus:ring-orange-500/10 p-5 transition-all duration-200 text-lg font-bold placeholder:text-gray-300 resize-none",
                    "placeholder": "An interesting title...",
                    "rows": 2,
                }
            ),
            "content": CKEditorWidget(
                attrs={
                    "class": "w-full rounded-2xl border-gray-100",
                }
            ),
        }

