from django import forms
from .helpers import get_link_preview_data
from .models import BlogPost, Entry, Link, News, Poll, Video


class EntryForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={"size": 100}))

    class Meta:
        model = Entry
        fields = ["title", "publish_at", "content", "image"]

    def save(self, *args, commit=True, **kwargs):
        instance = super().save(*args, commit=False, **kwargs)
        # Automatically approve unapproved news that do not require moderation
        if not instance.is_approved and not instance.author_needs_moderation():
            instance.approve(user=instance.author, commit=False)
        if commit:
            instance.save()
        return instance


class BlogPostForm(EntryForm):
    class Meta:
        model = BlogPost
        fields = ["title", "publish_at", "content", "image"]


class LinkForm(EntryForm):
    class Meta:
        model = Link
        fields = ["title", "publish_at", "external_url", "image"]

    # Holding on this as it's a new feature Issue #437
    # def save(self, *args, commit=True, **kwargs):
    #     instance = super().save(*args, commit=False, **kwargs)
    #     if self.cleaned_data["external_url"] and not self.cleaned_data["image"]:
    #         link_data = get_link_preview_data(self.cleaned_data["external_url"])
    #         print(link_data)
    #     instance.save()
    #     return instance


class NewsForm(EntryForm):
    class Meta:
        model = News
        fields = ["title", "publish_at", "content", "image"]


class PollForm(EntryForm):
    class Meta:
        model = Poll
        fields = ["title", "publish_at", "content", "image"]  # XXX: add choices


class VideoForm(EntryForm):
    class Meta:
        model = Video
        fields = ["title", "publish_at", "external_url", "image"]
