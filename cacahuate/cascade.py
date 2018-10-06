''' Logic on how information is invalidated in cascade. It is used by
validation-type nodes and patch requests '''


def cascade_invalidate(xml, state, mongo, config, invalidated, comment):
    ''' computes a set of fields to be marked as invalid given the
    original `invalidated` set of fields. '''
    # because this could cause a recursive import
    from cacahuate.node import make_node

    # find the data backwards
    first_node_found = False
    first_invalid_node = None
    set_values = {
        i['ref']: {
            'value': i['value'],
            'value_caption': i['value_caption'],
        }
        for i in invalidated
        if 'value' in i
    }
    invalidated = set(
        i['ref']
        for i in invalidated
    )
    xmliter = iter(xml)

    for element in xmliter:
        node = make_node(element, xmliter)

        more_fields = node.get_invalidated_fields(invalidated, state)

        invalidated.update(more_fields)

        if more_fields and not first_node_found:
            first_node_found = True
            first_invalid_node = node

    # computes the keys and values to be used in a mongodb update to set the fields as invalid
    updates = dict()

    for key in invalidated:
        node, actor, form, input = key.split('.')
        index, ref = form.split(':')

        node_path = 'state.items.{node}'.format(node=node)
        comment_path = node_path + '.comment'
        node_state_path = node_path + '.state'
        actor_path = node_path + '.actors.items.{actor}'.format(actor=actor)
        actor_state_path = actor_path + '.state'
        form_path = actor_path + '.forms.{index}'.format(index=index)
        form_state_path = form_path + '.state'
        input_path = form_path + '.inputs.items.{input}'.format(input=input)
        input_state_path = input_path + '.state'
        input_value_path = input_path + '.value'
        input_caption_path = input_path + '.value_caption'

        # inputs
        input_state = 'valid' if key in set_values else 'invalid'

        updates[input_state_path] = input_state

        if key in set_values:
            updates[input_value_path] = set_values[key]['value']
            updates[input_caption_path] = set_values[key]['value_caption']

        # forms
        if input_state == 'valid' and (form_state_path not in updates or updates[form_state_path] == 'valid'):
            form_state = 'valid'
        else:
            form_state = 'invalid'

        updates[form_state_path] = form_state

        # actors
        if form_state == 'valid' and (actor_state_path not in updates or updates[actor_state_path] == 'valid'):
            actor_state = 'valid'
        else:
            actor_state = 'invalid'

        updates[actor_state_path] = actor_state

        # nodes
        if actor_state == 'valid' and (node_state_path not in updates or updates[node_state_path] == 'valid'):
            node_state = 'valid'
        else:
            node_state = 'invalid'

        updates[node_state_path] = node_state
        updates[comment_path] = comment

    # update state
    collection = mongo[
        config['EXECUTION_COLLECTION']
    ]
    collection.update_one({
        'id': state['id'],
    }, {
        '$set': updates,
    })

    return first_invalid_node
