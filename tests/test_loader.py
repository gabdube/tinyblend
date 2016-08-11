# -*- coding: utf-8 -*-
"""
Assets loader tests

author: Gabriel Dube
"""
import sys
from os.path import dirname as dn
sys.path.append(dn(dn(__file__)))


import pytest
from game import BlenderFile, BlenderFileImportException

def test_open_blend_file():
    test_blend = BlenderFile('tests/test1.blend')

    head = test_blend.header
    assert 'VersionInfo(major=2, minor=7, rev=7)', repr(head.version)
    assert BlenderFile.Arch.X64, head.arch
    assert BlenderFile.Endian.Little, head.endian

    test_blend.close()

def test_open_bad_blend_file():
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test2.blend')
    pytest.raises(BlenderFileImportException, BlenderFile, 'tests/test3.blend')