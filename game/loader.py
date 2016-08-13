# -*- coding: utf-8 -*-
"""
Assets loader for the blender file format (.blend)

Author: Gabriel Dube
"""

from struct import Struct
from enum import Enum
from collections import namedtuple, OrderedDict
from itertools import permutations
from weakref import ref

class NamedStruct(object):
    """
        A type that fuse namedtuple and Struct together.
    """

    __fields__ = ('names', 'format')
    def __init__(self, name, fmt, *fields):
        self.format = Struct(fmt)
        self.names = namedtuple(name, fields)

    @classmethod
    def from_namedtuple(cls, ntuple, fmt):
        """
            Build a NamedStruct from a namedtuple

            Author: Gabriel Dube
        """
        named_struct = super(NamedStruct, cls).__new__(cls)
        named_struct.format = Struct(fmt)
        named_struct.names = ntuple

        return named_struct

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

class BlenderFileReadException(BlenderFileException):
    """
        Exception raised when reading bad values from a blend file
        author: Gabriel Dube
    """
    def __init__(self, message):
        super().__init__(message)



class BlenderObjectFactory(object):
    """
        Object that reads blender structures from datablocks

        Author: Gabriel Dube
    """
    def _build_object(self):
        file = self.file

        import pprint

        name, fields = file._export_struct(self.struct_dna)
        pprint.pprint(fields)

        return None

    def __init__(self, file, struct_index):
        self._file = ref(file)

        for index, struct_dna in enumerate(file.index.structures):
            if struct_dna.index == struct_index:
                self.struct_dna = struct_dna
                self.sdna_index = index
                break

        dnafields = self.struct_dna.fields
        dnatypes = file.index.type_names
        self.has_name = 'ID' in (dnatypes[ftype] for ftype, fname in dnafields)
        self.object = self._build_object()
        
    def __len__(self):
        file = self.file
        blocks = file.blocks
        count = 0

        for block, offset in blocks:
            count += block.sdna == self.sdna_index

        return count

    def __repr__(self):
        file = self.file

        dna = self.struct_dna
        return "<BlenderObjectFactory for '{}' objects>".format(file.index.type_names[dna.index])

    def __str__(self):
        file = self.file

        dna = self.struct_dna
        field_names = file.index.field_names
        type_names = file.index.type_names
        
        repr = type_names[dna.index] + '\n'
        for ftype, fname in dna.fields:
            repr += '  {} {}'.format(type_names[ftype], field_names[fname])+'\n'

        return repr

    def __iter__(self):
        file = self.file
        blocks = file.blocks

        for block, offset in blocks:
            if block.sdna == self.sdna_index:
                data = file._read_block(block, offset)
                yield self.object.unpack(data)
    
    @property
    def file(self):
        file = self._file()
        if file is None:
            raise RuntimeError('Parent blend file was freed')
        
        return file

    def find(self, name):
        """
            Find and build an object by name. If the object does not have a name,
            raise a BlenderFileReadException.

            author: Gabriel Dube
        """
        file = self.file
        if not self.has_name:
            raise BlenderFileReadException('Object type do not have a name')

        
        for obj in self:
            if obj.id == name:
                return obj

class BlenderFile(object):
    """
        Parse a blender file and extract the contained assets

        Attributes:
            * handle - Underlying file object
            * header - Information about the whole file. version (major,minor,rev), arch (32/64bits) and endianess (little/big)
            * blocks - List of blender data block in the blend file
            * index  - List if all name, types and structures contained in the blend file
    
        author: Gabriel Dube
    """

    Arch = Enum('Arch', (('X32', 'I'), ('X64', 'Q')), qualname='BlenderFile.Arch')
    Endian = Enum('Endian', (('Little', '<'), ('Big', '>')), qualname='BlenderFile.Endian')

    # Version structures
    VersionInfo = namedtuple('VersionInfo', ('major', 'minor', 'rev'))
    BlendFileInfo = namedtuple('BlendFileInfo', ('version', 'arch', 'endian'))

    # Index structures
    BlendStructField = namedtuple('BlendStructField', ('index_type', 'index_name'))
    BlendStruct = namedtuple('BlendStruct', ('index', 'fields'))
    BlendHumanStructField = namedtuple('BlendHumanStructField', ('name', 'type', 'ptr', 'count'))
    BlendHumanStruct = namedtuple('BlendHumanStruct', ('name', 'fields'))
    BlendIndex = namedtuple('BlendIndex', ('field_names', 'type_names', 'type_sizes', 'structures'))

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
        if len(header) != 12 or header[0:7] != b'BLENDER':
            return None
       
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

    def _struct_lookup(self, index):
        """
            Lookup for a struct definition in the blender file.
            Raise a BlenderFileReadException if index is not associated with a struct.

            author: Gabriel Dube
        """
        
        lookup = (s for s in self.index.structures if s.index == index)
        try:
            return next(lookup)
        except StopIteration:
            if index > len(self.index.type_names) or index < 0:
                msg = 'Type index {} is not valid for this blend file'.format(index)
            else:
                type_name = self.index.type_names[index]
                msg = 'Type {} is not associated with a structure'.format(type_name)

            raise BlenderFileReadException(msg)

    def _export_struct(self, struct, recursive=False):
        """
            Format a blender struct object fields in a human readable dict.
            This is used when creating blender object types

            If recursive is set to True, the function will also export the composed types of struct

            author: Gabriel Dube
        """        
        BlendHumanStruct = BlenderFile.BlendHumanStruct
        BlendHumanStructField = BlenderFile.BlendHumanStructField

        base_types = ('float', 'int', 'short', 'char', 'uint64_t')
        field_names = self.index.field_names
        type_names = self.index.type_names

        struct_name = type_names[struct.index]
        struct_fields = []

        for ftype, fname in struct.fields:
            name = field_names[fname]
            _type = type_names[ftype]

            is_ptr = name[0] == '*'
            is_array = name[-1] == ']'

            if is_ptr:
                name = name[1::]
            if is_array:
                name = name[0:name.index('[')]

            if recursive and not _type in base_types:
                _type = self._export_struct(self._struct_lookup(ftype))

            struct_fields.append(BlendHumanStructField(name=name, type=_type, ptr=is_ptr, count=0))

        return BlendHumanStruct(name=struct_name, fields=struct_fields)

    def _fmt_strct(self, fmt):
        """
            Format a Struct format string to match the blender file endianess and pointer sizes.
            Author: Gabriel Dube
        """
        head = self.header
        return head.endian.value + (fmt.replace('P', head.arch.value))

    def _parse_index(self, head):
        """
            Parse the blender index and return the parsed data.
            The index has an unkown length, so it cannot be parsed in one shot

            Author: Gabriel Dube
        """
        def align():
            nonlocal offset
            tmp = offset%4
            offset += 0 if tmp==0 else 4-tmp


        Int = NamedStruct('Int', self._fmt_strct('i'), 'val')
        Short = NamedStruct('Short', self._fmt_strct('h'), 'val')
        StructField = NamedStruct.from_namedtuple(BlenderFile.BlendStructField, self._fmt_strct('hh'))
        BlendStruct = BlenderFile.BlendStruct

        rewind_offset = self.handle.seek(0, 1)
        data = self.handle.read(head.size)
        if data[0:8] != b'SDNANAME':
            raise BlenderFileImportException('Malformed index')

        # Reading the blend file names
        offset = 8
        name_count = Int.unpack_from(data, offset).val
        field_names = [n.decode('utf-8') for n in data[offset+4::].split(b'\x00', name_count)[:-1]]

        # Reading the blend file types
        offset += sum((len(n) for n in field_names))+len(field_names)+4; align()         # Size of all names + size of all null char + name_count offset and Align the offset at 4 bytes
        if data[offset:offset+4] != b'TYPE':
            raise BlenderFileImportException('Malformed index')

        type_count = Int.unpack_from(data, offset+4).val
        type_names = [n.decode('utf-8') for n in data[offset+8::].split(b'\x00', type_count)[:-1]]

        # Reading the types length
        offset += sum((len(t) for t in type_names))+len(type_names)+8; align()
        if data[offset:offset+4] != b'TLEN':
            raise BlenderFileImportException('Malformed index')

        offset += 4
        type_data_length = Short.format.size * type_count
        type_sizes = (x.val for x in Short.iter_unpack(data[offset:offset+type_data_length]))

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
            
            structures.append(BlendStruct(index=structure_type_index, fields=tuple(fields)))

        # Rewind the blend at the end of the block head
        self.handle.seek(rewind_offset, 0)

        return BlenderFile.BlendIndex(
            field_names=tuple(field_names),
            type_names=tuple(type_names),
            type_sizes=tuple(type_sizes),
            structures=tuple(structures)
        )


    def _parse_blocks(self):
        """
            Extract the file block headers from the file. 
            Return a list of extracted blocks and the index (aka SDNA) block

            Author: Gabriel Dube
        """
        handle = self.handle
        BlendBlockHeader = NamedStruct('BlendBlockHeader', self._fmt_strct('4siPii'), 'code', 'size', 'addr', 'sdna', 'count')

        # Get the blend file size
        end = handle.seek(0, 2)
        handle.seek(12, 0)

        blend_index = None
        end_found = False
        file_block_heads = []
        while end != handle.seek(0, 1) and not end_found:
            buf = handle.read(BlendBlockHeader.format.size)
            file_block_head = BlendBlockHeader.unpack(buf)
            
            # DNA1 indicates the index block of the blend file
            # ENDB indicates the end of the blend file
            if file_block_head.code == b'DNA1':
                blend_index = self._parse_index(file_block_head)
            elif file_block_head.code == b'ENDB':
                end_found = True
            else:
                file_block_heads.append((file_block_head, handle.seek(0, 1)))

            handle.read(file_block_head.size)
        
        if blend_index is None:
            raise BlenderFileImportException('Could not find blend file index')

        if end_found == False:
            raise BlenderFileImportException('End of the blend file was not found')
        
        return tuple(file_block_heads), blend_index

    def _read_block(self, block, offset):
        """
            Read a block data and return it.

            Author: Gabriel Dube
        """
        handle = self.handle
        handle.seek(offset, 0)
        data = handle.read(block.size)
        return data 

    def __init__(self, blend_file_name):
        handle = open('./assets/'+blend_file_name, 'rb')

        header = BlenderFile.parse_header(handle.read(12))
        if header is None:
            raise BlenderFileImportException('Bad file header')

        self.header = header
        self.handle = handle
        self.blocks, self.index = self._parse_blocks()
        self.factories = {}

    def __getattr__(self, _name):
        # Format the name. Ex: scenes becomes Scene
        name = _name[0:-1].capitalize()

        # If the factory was already created
        fact = self.factories.get(name)
        if fact is not None:
            return fact

        # Factory creation
        try:
            fact = BlenderObjectFactory(self, self.index.type_names.index(name))
            self.factories[name] = fact
            return fact
        except ValueError:
            raise BlenderFileReadException('Data type {}({}) could not be found in the blend file'.format(_name, name))

    def close(self):
        self.handle.close()

   