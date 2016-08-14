# -*- coding: utf-8 -*-
"""
Assets loader tests

author: Gabriel Dube
"""
import sys
from os.path import dirname as dn
sys.path.append(dn(dn(__file__)))


import pytest
from game import BlenderFile, BlenderFileImportException, BlenderFileReadException
from game.loader import BlenderObjectFactory

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
    assert worlds.file is blend, 'Scenes file is not blend'
    assert len(worlds) == 1, 'Test blend should have one world'

    print(worlds.signature())

    test_world = worlds.find('TestWorld')
    print(test_world)

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

def test_blender_object_format_size():
    blend = BlenderFile('tests/test1.blend')

    index = blend.index
    scene_index = index.type_names.index('Scene')
    world_index = index.type_names.index('World')
    scene_size = index.type_sizes[scene_index]
    world_size = index.type_sizes[world_index]
    
    scenes = blend.scenes
    worlds = blend.worlds

    scenes_fmt = scenes.object.FMT
    worlds_fmt = worlds.object.FMT

    assert worlds_fmt.size == world_size, 'World object format size do not match type size'
    #assert scenes_fmt.size == scene_size, 'Scene object format size do not match type size'

    blend.close()

def test_weakref():
    blend = BlenderFile('tests/test1.blend')
    scenes = blend.scenes
    
    del blend

    pytest.raises(RuntimeError, getattr, scenes, 'file')
    pytest.raises(RuntimeError, len, scenes)
    pytest.raises(RuntimeError, repr, scenes)
    pytest.raises(RuntimeError, str, scenes)
    pytest.raises(RuntimeError, scenes.find, '...')


def test_open_bad_blend_file():
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test2.blend')
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test3.blend')