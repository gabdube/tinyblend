# -*- coding: utf-8 -*-
"""
Assets loader tests

author: Gabriel Dube
"""
import sys
from os.path import dirname as dn
sys.path.append(dn(dn(__file__)))


import pytest, gc
from tinyblend import BlenderFile, BlenderObjectFactory, BlenderObject, BlenderFileImportException, BlenderFileReadException

def test_open_blend_file():
    blend = BlenderFile('fixtures/test1.blend')

    head = blend.header
    assert 'VersionInfo(major=2, minor=7, rev=7)', repr(head.version)
    assert BlenderFile.Arch.X64, head.arch
    assert BlenderFile.Endian.Little, head.endian

    blend.close()

def test_should_read_scene_data():
    blend = BlenderFile('fixtures/test1.blend')

    worlds = blend.find('World')
    assert worlds.file is blend, 'World file is not blend'
    assert len(worlds) == 1, 'Test blend should have one world'

    world = worlds.find_by_name('TestWorld')
    assert world.file is blend
    assert isinstance(world, worlds.object)
    assert world.VERSION == blend.header.version
    assert len(world.mtex) == 18
    assert world.aodist > 12.8999 and world.aodist < 12.90001
    assert world.id.name[0:11] == b'WOTestWorld'    

    scenes = blend.find('Scene')
    assert len(scenes) == 1, 'Test blend should have one scene'

    rctfs = blend.find('rctf')
    pytest.raises(BlenderFileReadException, rctfs.find_by_name, 'blah')  # rctf object do not have a name
    pytest.raises(BlenderFileReadException, blend.find, 'foos')          # foos is not a valid structure
    pytest.raises(KeyError, worlds.find_by_name, 'BOO')                  # There are no worlds by the name of BOO in the blend file

    blend.close()


def test_equality():
    blend = BlenderFile('fixtures/test1.blend')

    worlds = blend.find('World')

    world1 = worlds.find_by_name('TestWorld')
    world2 = worlds.find_by_name('TestWorld')

    assert id(world1) is not id(world2)
    assert world1 == world2

def test_should_lookup_pointer():
    blend = BlenderFile('fixtures/test1.blend')

    worlds = blend.find('World')
    scenes = blend.find('Scene')

    world = worlds.find_by_name('TestWorld')
    scene = scenes.find_by_name('MyTestScene')

    pytest.raises(BlenderFileReadException, blend._from_address, 0)
    pytest.raises(AttributeError, setattr, scene, 'world', 0)
    pytest.raises(AttributeError, delattr, scene, 'world')

    scene_world = scene.world
    assert type(scene_world) is worlds.object
    assert scene_world is not world
    assert scene.world == world
    assert scene.world is scene_world
    assert scene.id.next is None         # Null pointer lookup returns None

def test_should_lookup_pointer_array():
    blend = BlenderFile('fixtures/test1.blend')

    obj = blend.find('Object').find_by_name('Suzanne')
    data = obj.data

    assert data.totvert == len(data.mvert)

def test_blend_struct_lookup():
    blend = BlenderFile('fixtures/test1.blend')

    scene_index = blend.index.type_names.index('Scene')
    float_index = blend.index.type_names.index('float')
    bad_index = 983742

    struct = blend._struct_lookup(scene_index)
    assert struct.index == scene_index, 'Struct index is not scene index'

    pytest.raises(BlenderFileReadException, blend._struct_lookup, float_index)
    pytest.raises(BlenderFileReadException, blend._struct_lookup, 983742)

    blend.close()

def test_weakref():
    blend = BlenderFile('fixtures/test1.blend')
    worlds = blend.find('World')
    
    del blend

    pytest.raises(RuntimeError, getattr, worlds, 'file')
    pytest.raises(RuntimeError, len, worlds)
    pytest.raises(RuntimeError, repr, worlds)
    pytest.raises(RuntimeError, str, worlds)
    pytest.raises(RuntimeError, worlds.find_by_name, '...')

def test_cache_lookup():
    blend = BlenderFile('fixtures/test1.blend')
    v = blend.header.version

    worlds = blend.find('World')

    assert BlenderObjectFactory.CACHE[v]['World']() is not None
    assert BlenderObject.CACHE[v]['World']() is not None
    
    del worlds
    gc.collect()

    assert BlenderObjectFactory.CACHE[v]['World']() is None
    assert BlenderObject.CACHE[v]['World']() is None

    worlds = blend.find('World')
    assert isinstance(worlds, BlenderObjectFactory)
    assert BlenderObjectFactory.CACHE[v]['World']() is not None
    assert BlenderObject.CACHE[v]['World']() is not None

    blend.close()

def test_list_structures():
    blend = BlenderFile('fixtures/test1.blend')
    structs = blend.list_structures()
    assert len(structs) > 30
    assert 'Scene' in structs

def test_tree():
    blend = BlenderFile('fixtures/test1.blend')
    scene_repr = blend.tree('Scene')
    assert len(scene_repr.splitlines()) > 100
    assert 'ID' in scene_repr

def test_open_bad_blend_file():
    pytest.raises(BlenderFileImportException, BlenderFile, 'fixtures/test2.blend')
    pytest.raises(BlenderFileImportException, BlenderFile, 'fixtures/test3.blend')