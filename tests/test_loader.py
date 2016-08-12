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

def test_open_blend_file():
    blend = BlenderFile('tests/test1.blend')

    head = blend.header
    assert 'VersionInfo(major=2, minor=7, rev=7)', repr(head.version)
    assert BlenderFile.Arch.X64, head.arch
    assert BlenderFile.Endian.Little, head.endian

    blend.close()

def test_should_read_scene():
    blend = BlenderFile('tests/test1.blend')

    scenes = blend.scenes
    assert len(scenes) == 1, 'Test blend should have one scene'

    pytest.raises(BlenderFileReadException, getattr, blend, 'foos')

    blend.close()

def test_weakref():
    blend = BlenderFile('tests/test1.blend')
    scenes = blend.scenes
    
    del blend

    pytest.raises(RuntimeError, len, scenes)
    pytest.raises(RuntimeError, repr, scenes)
    pytest.raises(RuntimeError, str, scenes)


def test_open_bad_blend_file():
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test2.blend')
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test3.blend')