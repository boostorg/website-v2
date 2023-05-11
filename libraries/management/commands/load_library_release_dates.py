import requests
from django.core.management.base import BaseCommand
from libraries.github import GithubAPIClient, GithubDataParser
from libraries.models import Library
from versions.models import Version


class Command(BaseCommand):
    help = 'Load release dates for libraries'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = GithubAPIClient()
        self.parser = GithubDataParser()
    
    def handle(self, *args, **options):
        libraries = Library.objects.all()
    
        for library in libraries:
            print(f"Getting tags for {library.slug}")
            tags = self.client.get_tags(repo_slug=library.slug)
            first_tag = tags[-1]
            response = requests.get(first_tag['commit']['url'])
            date_raw = response.json()["commit"]["committer"]["date"]
            library.save()