from django import forms
from .models import BlogPost, Entry, Link, Poll, Video


class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ["title", "content"]

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
        fields = ["title", "content"]


class LinkForm(EntryForm):
    class Meta:
        model = Link
        fields = ["title", "external_url"]


class PollForm(EntryForm):
    class Meta:
        model = Poll
        fields = ["title", "content"]  # XXX: add choices


class VideoForm(EntryForm):
    class Meta:
        model = Video
        fields = ["title", "external_url"]
