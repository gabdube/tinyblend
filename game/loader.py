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
    'Int': ('i', 'val'),
    'Short': ('h', 'val'),
    'StructField': ('hh', 'type', 'name'),
    'FileBlockHeader': ('4siPii', 'code', 'size', 'addr', 'sdna', 'count')
}

class NamedStruct(object):
    """
        A type that fuse namedtuple and Struct together. Greatly increase the readability of the source
        when unpacking blender ressources
    """

    __fields__ = ('names', 'format')
    def __init__(self, name, fmt, *fields):
        self.format = Struct(fmt)
        self.names = namedtuple(name, fields)

    def unpack(self, data):
        return self.names(*self.format.unpack(data))

    def unpack_from(self, data, offset):
        return self.names(*self.format.unpack_from(data, offset))

    def iter_unpack(self, data):
        return (self.names(*d) for d in self.format.iter_unpack(data))

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
            * blocks - List of blender data block in the blend file
    
        author: Gabriel Dube
    """

    Arch = Enum('Arch', ('X32', 'X64'), qualname='BlenderFile.Arch')
    Endian = Enum('Endian', ('Little', 'Big'), qualname='BlenderFile.Endian')

    VersionInfo = namedtuple('VersionInfo', ('major', 'minor', 'rev'))
    BlendFileInfo = namedtuple('BlendFileInfo', ('version', 'arch', 'endian'))
    BlendStructRef = namedtuple('BlendStructRef', ('name', 'fields'))
    BlendIndex = namedtuple('BlendIndex', ('names', 'types', 'structures'))
    

    # Cache for generated blender structures
    StructCache = {} 

    @staticmethod
    def parse_header(header):
        """
            Parse the header of a blender file and return the formatted data in a BlendFileInfo object.
            The passed header must be valid.

            Arguments:
                header - The header to parse as a byte string

            Return value: A BlendFileInfo object if successful, None otherwise.

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

        return BlenderFile.BlendFileInfo(version=version, arch=arch, endian=endian)

    def _create_structs(self):
        """
            Define the blender data structures add them to the class struct cache
        """
        head = self.header
        key = self._cache_key
        if key in BlenderFile.StructCache.keys():
            return 

        endian = '<' if head.endian == BlenderFile.Endian.Little else '>'
        ptr = 'Q' if head.arch == BlenderFile.Arch.X64 else 'I'

        cache = {}
        for name, fmt in BLENDER_STRUCTURE_FORMATS.items():
            fmt, *field_names = fmt
            fmt = endian + (fmt.replace('P', ptr))
            cache[name] = NamedStruct(name, fmt, *field_names)

        BlenderFile.StructCache[key] = cache

    def _parse_index(self, head, data_offset):
        """
            Parse the blender index and return the parsed data.
            The index has an unkown length, so it cannot be parsed in one shot
        """
        Int, Short, StructField, BlendStructRef = self.Int, self.Short, self.StructField, BlenderFile.BlendStructRef
        data = self.handle.read(head.size)

        def align():
            nonlocal offset
            tmp = offset%4
            offset += 0 if tmp==0 else 4-tmp

        if data[0:8] != b'SDNANAME':
            raise BlenderFileImportException('Malformed index')

        # Reading the blend file names
        offset = 8
        name_count = Int.unpack_from(data, offset).val
        names = data[offset+4::].split(b'\x00', name_count)[:-1]

        # Reading the blend file types
        offset += sum((len(n) for n in names))+len(names)+4; align()         # Size of all names + size of all null char + name_count offset and Align the offset at 4 bytes
        if data[offset:offset+4] != b'TYPE':
            raise BlenderFileImportException('Malformed index')

        type_count = Int.unpack_from(data, offset+4).val
        type_names = data[offset+8::].split(b'\x00', type_count)[:-1]

        # Reading the types length
        offset += sum((len(t) for t in type_names))+len(type_names)+8; align()
        if data[offset:offset+4] != b'TLEN':
            raise BlenderFileImportException('Malformed index')

        offset += 4
        type_data_length = Short.format.size * type_count
        type_sizes = (x.val for x in Short.iter_unpack(data[offset:offset+type_data_length]))
        types = tuple(zip(type_names, type_sizes))

        # Reading structures information
        offset += type_data_length; align()
        if data[offset:offset+4] != b'STRC':
            raise BlenderFileImportException('Malformed index')

        offset += 8
        structures = []
        structure_count = Int.unpack_from(data, offset-4).val
        for _ in range(structure_count):
            structure_type_index = Short.unpack_from(data, offset).val

            field_count = Short.unpack_from(data, offset+2).val
            fields = []
            offset += 4
            for _ in range(field_count):
                fields.append(StructField.unpack_from(data, offset))
                offset += 4
            
            structures.append(BlendStructRef(name=structure_type_index, fields=tuple(fields)))

        # Rewind the blend at the end of the block head
        self.handle.seek(data_offset, 0)

        return BlenderFile.BlendIndex(names=tuple(names), types=types, structures=tuple(structures) )


    def _parse_blocks(self):
        """
            Extract the file block headers from the file. 
            Return a list of extracted blocks and the index (aka SDNA) block
        """
        handle = self.handle
        FileBlockHeader = self.FileBlockHeader

        # Get the blend file size
        end = handle.seek(0, 2)
        handle.seek(12, 0)

        blend_index = None
        end_found = False
        file_block_heads = []
        while end != handle.seek(0, 1) and not end_found:
            buf = handle.read(FileBlockHeader.format.size)
            file_block_head = FileBlockHeader.unpack(buf)
            
            # DNA1 indicates the index block of the blend file
            # ENDB indicates the end of the blend file
            if file_block_head.code == b'DNA1':
                blend_index = self._parse_index(file_block_head, handle.seek(0, 1))
            elif file_block_head.code == b'ENDB':
                end_found = True
            else:
                file_block_heads.append((file_block_head, handle.seek(0, 1)))

            handle.read(file_block_head.size)
        
        if blend_index is None:
            raise BlenderFileImportException('Could not find blend file index')

        if end_found == False:
            raise BlenderFileImportException('End of the blend file was not found')
        
        return file_block_heads, blend_index

    def __init__(self, blend_file_name):
        handle = open('./assets/'+blend_file_name, 'rb')

        bytes_header = handle.read(12)
        if len(bytes_header) != 12 or bytes_header[0:7] != b'BLENDER':
            raise BlenderFileImportException('Bad file header')

        header = BlenderFile.parse_header(bytes_header)
        if header is None:
            raise BlenderFileImportException('Bad file header')

        self.header = header
        self._cache_key = (self.header.arch, self.header.endian)
        self.handle = handle
        self._create_structs()
        self.blocks, self.index = self._parse_blocks()

    def close(self):
        self.handle.close()

    def __getattr__(self, name):
        cache = BlenderFile.StructCache.get(self._cache_key) or {}
        attr = cache.get(name)
        if attr is None:
            raise AttributeError('Attribute \'{}\' not found'.format(name))

        return attr
        