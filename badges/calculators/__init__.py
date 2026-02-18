import importlib
import inspect
import pkgutil
from typing import Generator

from badges.calculators.base_calculator import BaseCalculator


def get_calculators() -> Generator[BaseCalculator]:
    """
    Discover and return all implemented calculator classes.

    Returns:
        List of calculator classes that inherit from BaseCalculator.
    """
    calculators_package = importlib.import_module("badges.calculators")
    for importer, modname, ispkg in pkgutil.iter_modules(calculators_package.__path__):
        if modname == "base_calculator":
            continue

        module = importlib.import_module(f"badges.calculators.{modname}")
        # get all classes from the module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # we want subclasses of BaseCalculator, not BaseCalculator itself
            if issubclass(obj, BaseCalculator) and obj is not BaseCalculator:
                yield obj
