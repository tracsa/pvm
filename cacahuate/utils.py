from case_conversion import pascalcase
from importlib import import_module
from coralillo.errors import ModelNotFoundError
import os
import sys
from jinja2 import Template, TemplateError

from cacahuate.errors import MisconfiguredProvider
from cacahuate.models import User
from cacahuate.jsontypes import MultiFormDict


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


def render_or(template, default, context={}):
    ''' Renders the given template in case it is a valid jinja template or
    returns the default value '''
    try:
        return Template(template).render(**context)
    except TemplateError:
        return default


def compact_values(collected_forms):
    ''' Takes the input from the first form in a process and compacts it into
    the first set of values for _the state_ that will be used in conditionals
    or jinja templates'''
    context = dict()
    for form in collected_forms:
        form_dict = dict()

        for name, input in form['inputs']['items'].items():
            form_dict[name] = input['value_caption']

        context[form['ref']] = form_dict

    return context


def get_values(execution_data):
    ''' the proper and only way to get the ``'values'`` key out of
    an execution document from mongo. It takes care of the transformations
    needed for it to work in jinja templates and other contexts where the
    multiplicity of answers (multiforms) is relevant. '''
    try:
        return {
            k: MultiFormDict(v) for k, v in execution_data['values'].items()
        }
    except KeyError:
        return dict()
