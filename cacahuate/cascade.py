''' Logic on how information is invalidated in cascade. It is used by
validation-type nodes and patch requests '''
from cacahuate.errors import EndOfProcess


def get_ref_index(state, node, actor, ref, index):
    forms = state['state']['items'][node]['actors']['items'][actor]['forms']

    ref_forms = [
        i for (i, form) in enumerate(forms) if form['ref'] == ref
    ]

    if int(index) in ref_forms:
        return ref_forms.index(int(index))

    return None


def cascade_invalidate(xml, state, invalidated, comment):
    ''' computes a set of fields to be marked as invalid given the
    original `invalidated` set of fields. '''
    # because this could cause a recursive import
    from cacahuate.node import make_node

    # find the first node that is invalid and select it
    set_values = {
        i['ref']: {
            'value': i['value'],
            'value_caption': i['value_caption'],
        }
        for i in invalidated
        if 'value' in i
    }
    invalid_refs = set(
        i['ref']
        for i in invalidated
    )
    xmliter = iter(xml)

    for element in xmliter:
        node = make_node(element, xmliter)
        more_fields = node.get_invalidated_fields(invalid_refs, state)

        invalid_refs.update(more_fields)

    # computes the keys and values to be used in a mongodb update to set the
    # fields as invalid
    updates = dict()

    for key in invalid_refs:
        node, actor, form, input = key.split('.')
        index, ref = form.split(':')

        ref_index = get_ref_index(
            state=state,
            node=node,
            actor=actor,
            ref=ref,
            index=index,
        )

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
        values_input_path = 'values.{ref}.{ref_index}.{input}'.format(
            ref=ref,
            ref_index=ref_index,
            input=input,
        )

        # inputs
        input_state = 'valid' if key in set_values else 'invalid'

        updates[input_state_path] = input_state

        if key in set_values:
            updates[input_value_path] = set_values[key]['value']
            updates[input_caption_path] = set_values[key]['value_caption']

            if ref_index is not None:
                updates[values_input_path] = set_values[key]['value']

        # forms
        if input_state == 'valid' and (
                form_state_path not in updates or
                updates[form_state_path] == 'valid'):
            form_state = 'valid'
        else:
            form_state = 'invalid'

        updates[form_state_path] = form_state

        # actors
        if form_state == 'valid' and (
                actor_state_path not in updates or
                updates[actor_state_path] == 'valid'):
            actor_state = 'valid'
        else:
            actor_state = 'invalid'

        updates[actor_state_path] = actor_state

        # nodes
        if actor_state == 'valid' and (
                node_state_path not in updates or
                updates[node_state_path] == 'valid'):
            node_state = 'valid'
        else:
            node_state = 'invalid'

        updates[node_state_path] = node_state
        updates[comment_path] = comment

    return updates


def track_next_node(xml, state, mongo, config):
    ''' given an xml and the current state, returns the first invalid or
    unfilled node following the xml's ruleset (conditionals) '''
    from cacahuate.node import make_node

    xmliter = iter(xml)
    node = make_node(next(xmliter), xmliter)

    if node.id in state['state']['items']:
        node_state = state['state']['items'][node.id]['state']
        if node_state in ('invalid', 'unfilled'):
            return node

    try:
        while True:
            node = node.next(
                xml,
                state,
                mongo,
                config,
                skip_reverse=True,
            )

            if node.id in state['state']['items']:
                if state['state']['items'][node.id]['state'] == 'valid':
                    continue

            return node
    except StopIteration:
        # End of process
        raise EndOfProcess
