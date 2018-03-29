from xml.dom.minidom import Element
from pvm.xml import get_ref
from pvm.errors import ValidationErrors, InputError, RequiredInputError

def get_associated_data(ref:str, data:dict) -> dict:
    ''' given a reference returns its asociated data in the data dictionary '''
    if 'form_array' not in data:
        return {}

    for form in data['form_array']:
        if type(form) != dict:
            continue

        if 'ref' not in form:
            continue

        if form['ref'] == ref:
            return form['data']

    return {}

def validate_input(form_index:int, input:Element, value):
    ''' Validates the given value against the requirements specified by the
    input element '''
    if input.getAttribute('required') and (value=='' or value is None):
        raise RequiredInputError(form_index, input.getAttribute('name'))

    return value

def validate_form(index:int, form:Element, data:dict) -> dict:
    ''' Validates the given data against the spec contained in form. In case of
    failure raises an exception. In case of success returns the validated data.
    '''
    ref = get_ref(form)

    given_data = get_associated_data(ref, data)
    collected_data = {}
    errors = []

    for input in form.getElementsByTagName('input'):
        name = input.getAttribute('name')

        try:
            collected_data[name] = validate_input(index, input, given_data.get(name))
        except InputError as e:
            errors.append(e)

    if errors:
        raise ValidationErrors(errors)

    return collected_data

def validate_json(json_data:dict, req:list):
    if 'process_name' not in json_data:
        raise BadRequest([{
            'detail': 'process_name is required',
            'where': 'request.body.process_name',
        }])
