def test_materials_package_imports_empty_registries():
    from omai.materials.operator import NODES, EDGES
    assert isinstance(NODES, tuple)
    assert isinstance(EDGES, tuple)
