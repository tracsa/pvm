from jinja2 import Template, TemplateError


def render_or(template, default, context={}):
    ''' Renders the given template in case it is a valid jinja template or
    returns the default value '''
    try:
        return Template(template).render(**context)
    except TemplateError:
        return default
