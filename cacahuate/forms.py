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
