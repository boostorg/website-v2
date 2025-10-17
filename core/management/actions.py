from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Callable

import djclick as click
from django.core.mail import send_mail
from django.core.management import call_command
from django.utils import timezone

from config import settings


def progress_message(message: str):
    click.secho(message, fg="green")
    return f"{timezone.now()}: {message}"


@dataclass
class Action:
    """
    A distinct task to be completed.

    Action can be a callable or a list of string arguments to pass to `call_command`
    """

    description: str
    handler: Callable | list[str]

    @property
    def handler_name(self) -> str:
        if isinstance(self.handler, Callable):
            return f"function: {self.handler.__name__}"
        return f"command: {self.handler[0]}"

    def run(self):
        if isinstance(self.handler, Callable):
            self.handler()
        else:
            call_command(*self.handler)


class ActionsManager(metaclass=ABCMeta):
    progress_messages: list[str] = []

    def __init__(self):
        self.tasks: list[Action] = []
        self.set_tasks()
        self.validate_tasks()

    @abstractmethod
    def set_tasks(self):
        """
        Set self.tasks to a list of Action instances.
        self.tasks = [Action(...), Action(...)]
        """
        raise NotImplementedError

    def validate_tasks(self):
        if not self.tasks:
            raise ValueError("No tasks defined. You must set some with set_tasks()")
        if not all(isinstance(task, Action) for task in self.tasks):
            raise TypeError("All tasks must be instances of Action")

    def add_progress_message(self, message: str):
        message = progress_message(message)
        self.progress_messages.append(message)

    def run_tasks(self) -> dict[str:int]:
        for task in self.tasks:
            # "Task: " prefix for easy log parsing
            self.add_progress_message(
                f"Task start - {task.handler_name}, desc: {task.description.lower()}..."
            )
            task.run()
            self.add_progress_message(
                f"Task done - {task.handler_name}, desc: {task.description.lower()}"
            )


def send_notification(user, message, subject):
    if user and user.email:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
