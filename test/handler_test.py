from .context import lib, get_testing_config

def test_get_start_node():
    config = get_testing_config()
    handler = lib.handler.Handler(config)

    start_node = handler.get_start()

    assert start_node is not None
    assert isinstance(start_node, lib.node.Node)
    assert isinstance(start_node, lib.node.StartNode)

def test_save_execution():
    config = get_testing_config()
    handler = lib.handler.Handler(config)

    exct_id = handler.save_execution(node)

    exct = Execution.get(exct_id)

    assert exct.process == 'simple_2018-02-19'
    assert type(exct.pointers) == set
    assert len(exct.pointers) == 1

def test_recover_step():
    config = get_testing_config()
    handler = lib.handler.Handler(config)

    step = handler.recover_step()

    assert step is not None
    assert isinstance(step, lib.node.Node)
