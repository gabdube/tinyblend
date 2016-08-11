# -*- coding: utf-8 -*-
"""
Assets loader for the blender file format (.blend)

author: Gabriel Dube
"""

from struct import Struct
from enum import Enum
from collections import namedtuple
from itertools import permutations

# Blender structures format are defined here. When a BlendFile is loaded, the structs
# are instanced and then cached in the class. 

BLENDER_STRUCTURE_FORMATS = {
    'FileBlockHeader': '4siPii',
}

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
    Endian = Enum('Endian', ('Little', 'Big'), qualname='BlenderFile.Endian')

    VersionInfo = namedtuple('VersionInfo', ('major', 'minor', 'rev'))
    BlenderFileInfo = namedtuple('BlenderFileInfo', ('version', 'arch', 'endian'))

    # Cache for generated blender structures
    StructCache = {} 

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

    def create_structs(self):
        """
            Define the blender data structures add them to the class struct cache
        """
        head = self.header
        key = (head.arch, head.endian)
        if key in BlenderFile.StructCache.keys():
            return 

        endian = '<' if head.endian == BlenderFile.Endian.Little else '>'
        ptr = 'Q' if head.arch == BlenderFile.Arch.X64 else 'I'

        cache = {}
        for name, fmt in BLENDER_STRUCTURE_FORMATS.items():
            fmt = endian + (fmt.replace('P', ptr))
            cache[name] = Struct(fmt)

        BlenderFile.StructCache[key] = cache

    def parse_blocks(self):
        """
            Extract the file block headers from the file
        """
        handle = self.handle
        FileBlockHeader = self.FileBlockHeader

        # Get the blend file size
        end = handle.seek(0, 2)
        handle.seek(12, 0)

        file_block_heads = []
        while end != handle.seek(0, 1):
            buf = handle.read(FileBlockHeader.size)
            file_block_head = FileBlockHeader.unpack(buf)
            file_block_heads.append(file_block_head)

            handle.read(file_block_head[1])

        return file_block_heads

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
        self.create_structs()
        self.blocks = self.parse_blocks()

    def close(self):
        self.handle.close()

    def __getattr__(self, name):
        cache = BlenderFile.StructCache.get((self.header.arch, self.header.endian)) or {}
        attr = cache.get(name)
        if attr is None:
            raise AttributeError('Attribute \'{}\' not found'.format(name))

        return attr
        