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

    def get_update_keys(invalidated):
        ''' computes the keys and values to be used in a mongodb update to
        set the fields as invalid '''
        ikeys = set()
        fkeys = set()
        akeys = set()
        nkeys = set()
        ckeys = set()

        for key in invalidated:
            node, actor, form, input = key.split('.')
            index, ref = form.split(':')

            ikeys.add(('state.items.{node}.actors.items.{actor}.'
                       'forms.{index}.inputs.items.{input}.'
                       'state'.format(
                            node=node,
                            actor=actor,
                            index=index,
                            input=input,
                        ), 'invalid'))

            fkeys.add(('state.items.{node}.actors.items.{actor}.'
                       'forms.{index}.state'.format(
                            node=node,
                            actor=actor,
                            index=index,
                        ), 'invalid'))

            akeys.add(('state.items.{node}.actors.items.{actor}.'
                       'state'.format(
                            node=node,
                            actor=actor,
                        ), 'invalid'))

            nkeys.add(('state.items.{node}.state'.format(
                node=node,
            ), 'invalid'))

        for key, _ in nkeys:
            key = '.'.join(key.split('.')[:-1]) + '.comment'
            ckeys.add((key, comment))

        return fkeys | akeys | nkeys | ikeys | ckeys

    updates = dict(get_update_keys(invalidated))

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
