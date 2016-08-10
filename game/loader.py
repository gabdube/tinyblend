# -*- coding: utf-8 -*-
"""
Assets loader for the blender file format (.blend)

author: Gabriel Dube
"""

from struct import Struct
from enum import Enum
from collections import namedtuple

class BlenderFileException(Exception):
    """
        Base exception class for blender import related exceptions

        author: Gabriel Dube
    """
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return "Error while executing action on blender file: {}".format(repr(self.message))

class BlenderFileImportException(BlenderFileException):
    """
        Exception raised when a blender file import fails.
        
        author: Gabriel Dube
    """
    def __init__(self, message):
        super().__init__(message)

class BlenderFile(object):
    """
        Parse a blender file and extract the contained assets

        Attributes:
            * handle - Underlying file object
            * header - Information about the whole file. version (major,minor,rev), arch (32/64bits) and endianess (little/big)
    
        author: Gabriel Dube
    """

    Arch = Enum('Arch', ('X32', 'X64'), qualname='BlenderFile.Arch')
    Endian = Enum('Endian', (('Little', '<'), ('Big', '>')), qualname='BlenderFile.Endian')

    VersionInfo = namedtuple('VersionInfo', ('major', 'minor', 'rev'))
    BlenderFileInfo = namedtuple('BlenderFileInfo', ('version', 'arch', 'endian'))

    @staticmethod
    def parse_header(header):
        """
            Parse the header of a blender file and return the formatted data in a BlenderFileInfo object.
            The passed header must be valid.

            Arguments:
                header - The header to parse as a byte string

            Return value: A BlenderFileInfo object if successful, None otherwise.

            author: Gabriel Dube
        """
        arch = header[7:8]
        endian = header[8:9]
        version = [x-48 for x in header[9::]]

        if arch == b'-':
            arch = BlenderFile.Arch.X64
        elif arch == b'_':
            arch = BlenderFile.Arch.X32
        else:
            return None

        if endian == b'v':
            endian = BlenderFile.Endian.Little
        elif endian == b'V':
            endian = BlenderFile.Endian.Big
        else:
            return None

        version = BlenderFile.VersionInfo(*version)

        return BlenderFile.BlenderFileInfo(version=version, arch=arch, endian=endian)

    def __init__(self, blend_file_name):
        handle = open('./assets/'+blend_file_name, 'rb')

        bytes_header = handle.read(12)
        if len(bytes_header) != 12 or bytes_header[0:7] != b'BLENDER':
            raise BlenderFileImportException('Bad file header')

        header = BlenderFile.parse_header(bytes_header)
        if header is None:
            raise BlenderFileImportException('Bad file header')

        self.header = header
        self.handle = handle
        self.handle.close()