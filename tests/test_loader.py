# -*- coding: utf-8 -*-
"""
Assets loader tests

author: Gabriel Dube
"""
import sys
from os.path import dirname as dn
sys.path.append(dn(dn(__file__)))


import pytest, gc
from game import BlenderFile, BlenderFileImportException, BlenderFileReadException
from game.loader import BlenderObjectFactory, BlenderObject

def test_open_blend_file():
    blend = BlenderFile('tests/test1.blend')

    head = blend.header
    assert 'VersionInfo(major=2, minor=7, rev=7)', repr(head.version)
    assert BlenderFile.Arch.X64, head.arch
    assert BlenderFile.Endian.Little, head.endian

    blend.close()

def test_should_read_scene_data():
    blend = BlenderFile('tests/test1.blend')

    worlds = blend.worlds
    assert worlds.file is blend, 'World file is not blend'
    assert len(worlds) == 1, 'Test blend should have one world'

    first_world = next(iter(worlds))
    assert first_world.file is blend
    assert first_world.VERSION == blend.header.version
    assert len(first_world.mtex) == 18
    assert first_world.aodist > 12.8999 and first_world.aodist < 12.90001

    pytest.raises(BlenderFileReadException, getattr, blend, 'foos')

    blend.close()

def test_blend_struct_lookup():
    blend = BlenderFile('tests/test1.blend')

    scene_index = blend.index.type_names.index('Scene')
    float_index = blend.index.type_names.index('float')
    bad_index = 983742

    struct = blend._struct_lookup(scene_index)
    assert struct.index == scene_index, 'Struct index is not scene index'

    pytest.raises(BlenderFileReadException, blend._struct_lookup, float_index)
    pytest.raises(BlenderFileReadException, blend._struct_lookup, 983742)

    blend.close()

def test_weakref():
    blend = BlenderFile('tests/test1.blend')
    worlds = blend.worlds
    
    del blend

    pytest.raises(RuntimeError, getattr, worlds, 'file')
    pytest.raises(RuntimeError, len, worlds)
    pytest.raises(RuntimeError, repr, worlds)
    pytest.raises(RuntimeError, str, worlds)
    pytest.raises(RuntimeError, worlds.find, '...')

def test_cache_lookup():
    blend = BlenderFile('tests/test1.blend')
    v = blend.header.version

    worlds = blend.worlds

    assert BlenderObjectFactory.CACHE[v]['World']() is not None
    assert BlenderObject.CACHE[v]['World']() is not None
    
    del worlds
    gc.collect()

    assert BlenderObjectFactory.CACHE[v]['World']() is None
    assert BlenderObject.CACHE[v]['World']() is None

    worlds = blend.worlds
    assert isinstance(worlds, BlenderObjectFactory)
    assert BlenderObjectFactory.CACHE[v]['World']() is not None
    assert BlenderObject.CACHE[v]['World']() is not None

    blend.close()

def test_open_bad_blend_file():
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test2.blend')
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test3.blend')