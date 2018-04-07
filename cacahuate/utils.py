from case_conversion import pascalcase
from importlib import import_module
import os
import sys

from cacahuate.errors import MisconfiguredProvider


def user_import(module_key, import_maper, default_path):
    ''' import a provider defined by the user '''
    if module_key in import_maper:
        import_path = import_maper[module_key]

        cwd = os.getcwd()

        if cwd not in sys.path:
            sys.path.insert(0, cwd)
    else:
        import_path = default_path + '.' + module_key

    try:
        mod = import_module(import_path)
        cls = getattr(mod, pascalcase(module_key) + 'HierarchyProvider')
    except (ModuleNotFoundError, AttributeError):
        raise MisconfiguredProvider

    return cls
