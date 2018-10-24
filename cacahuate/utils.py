from case_conversion import pascalcase
from importlib import import_module
from coralillo.errors import ModelNotFoundError
import os
import sys

from cacahuate.errors import MisconfiguredProvider
from cacahuate.models import User


def user_import(module_key, class_sufix, import_maper, default_path, enabled):
    ''' import a provider defined by the user '''
    if module_key in import_maper:
        import_path = import_maper[module_key]

        cwd = os.getcwd()

        if cwd not in sys.path:
            sys.path.insert(0, cwd)
    elif module_key in enabled:
        import_path = default_path + '.' + module_key
    else:
        raise MisconfiguredProvider(
            'Provider {} not enabled'.format(module_key)
        )

    cls_name = pascalcase(module_key) + class_sufix

    try:
        mod = import_module(import_path)
        cls = getattr(mod, cls_name)
    except ModuleNotFoundError:
        raise MisconfiguredProvider(
            'Could not import provider module {}'.format(import_path)
        )
    except AttributeError:
        raise MisconfiguredProvider('Provider does not define class {}'.format(
            cls_name,
        ))

    return cls


def clear_username(string):
    ''' because mongo usernames have special requirements '''
    string = string.strip()

    if string.startswith('$'):
        string = string[1:]

    try:
        string = string[:string.index('@')]
    except ValueError:
        pass

    return string.replace('.', '')


def get_or_create(identifier, data):
    identifier = clear_username(identifier)
    data['identifier'] = identifier

    try:
        return User.get_by_or_exception('identifier', identifier)
    except ModelNotFoundError:
        return User(**data).save()
