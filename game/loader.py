# -*- coding: utf-8 -*-
"""
Assets loader for the blender file format (.blend)

Author: Gabriel Dube
"""

from struct import Struct
from enum import Enum
from collections import namedtuple
from weakref import ref
import re

# List of base types found in blend fields and their struct char representation.
_BASE_TYPES = {'float':'f', 'double':'d', 'int':'i', 'short':'h', 'char':'c', 'uint64_t':'Q'}

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
        x, y = len(data), self.format.size
        if (x > y) and (x % y == 0):
            return list(self.iter_unpack(data))

        values = self.format.unpack(data)
        return self.names(*self.format.unpack(data))

    def unpack_from(self, data, offset):
        return self.names(*self.format.unpack_from(data, offset))

    def iter_unpack(self, data):
        return (self.names(*d) for d in self.format.iter_unpack(data))


class BlenderObject(object):
    """
        Blender object base. Unpack raw data depending on the subclass format string.

        Class names:
            VERSION: Version of the blend file for this struct. (Blender structures change with blender versions)

        Instance names:
            file: The parent file of this object

        Pointer Fields:
            In order to read pointer fields, a lookup in the blend file is neccesary.
            This class keeps a weakref to to its parent blend file. If the parent file
            is closed or freed, the pointer lookup will raise a RuntimeError

        author: Gabriel Dube
    """
    # Cache for BlenderObject subclasses. Dict of {VERSION: {CLASS_NAME: CLASS}}
    CACHE = {}
    
    # Version of the blend file. Overriden in subclasses.
    VERSION = None

    # Format Struct to unpack the raw data. Overriden in subclasses
    FMT = None

    # List of (subclasses, offset) in the object. Overriden is subclasses 
    CLASSES = None

    @staticmethod
    def _set_fields(names, data, obj):
        """
            Unpack the base types (float, int, etc) from the raw data to the object

            author: Gabriel Dube
        """
        template = re.compile('(.+)_\d+_(\d+)')
        gen = zip(names, data)
        while True:
            name, value = gen.__next__()
            match = template.findall(name)
            if len(match) == 0:
                setattr(obj, name, value)
            else:
                arr = []
                for i in range(int(match[0][1])):
                    _, value = gen.__next__()
                    arr.append(value)
                setattr(obj, match[0][0], arr)


    def __new__(cls, file, data):
        obj = super(BlenderObject, cls).__new__(cls)
        obj._file = file

        # Unpack structures from the raw data to the object
        for cls_, slice, name in cls.CLASSES:
            obj_ = cls_(file, data[slice])
            setattr(obj, name, obj_)

        try:
            BlenderObject._set_fields(cls.FMT.names._fields, cls.FMT.unpack(data), obj)
        except StopIteration:
            pass

        return obj

    @property
    def file(self):
        file = self._file()
        if file is None:
            raise RuntimeError('Parent blend file was freed')
        
        return file

class BlenderObjectFactory(object):
    """
        Object that reads blender structures from datablocks. A BlenderObjectFactory
        is created when the data types is accessed for the first time in a blend file.
        The BlenderObjectFactory is then cached because their creation can be quite expensive.

        A BlenderObjectFactory keeps a weakref to its parent blend file. If the parent file
        is closed or freed, all its methods will raise a RuntimeError

        The BlenderObjectFactory creates a new type from the blender structure definition,
        this type is then used to unpack the blender objects from raw data. For more information
        see the BlenderObject documentation.

        author: Gabriel Dube
    """
    # Cache for instanced factories. Dict of {VERSION: {CLASS_NAME: CLASS}}
    CACHE = {}

    @staticmethod
    def _build_objects(file, struct):
        """
            Create the blender object for the factory.

            author: Gabriel Dube
        """
        base_types = _BASE_TYPES
        head = file.header
        arch, endian = head[1::]
        
        # Get cache
        version = file.header.version
        version_cache = BlenderObject.CACHE.get(version)
        if version_cache is None:
            version_cache = {}
            BlenderObject.CACHE[version] = version_cache
        
        # Get the name of the struct
        name = file.index.type_names[struct.index]

        # If type was cached, use the cached version
        obj = (version_cache.get(name) or (lambda: None) )()
        if obj is not None:
            return obj, obj.CLASSES

        # If type was not cached, create a new blender object type
        dependencies = []
        offset = 0
        name, fields = file._export_struct(struct)
        for f, dna in zip(fields, struct.fields):
            if f.type not in base_types and not f.ptr:
                tmp_dna = file._struct_lookup(dna.index_type)
                dep = (BlenderObjectFactory._build_objects(file, tmp_dna)[0], slice(offset, offset+f.size), f.name)
                dependencies.append(dep)

            offset += f.size
        
        fmt, fmt_names = compile_fmt(fields)
        fmt_names = namedtuple(name, fmt_names)
        fmt = (endian.value)+fmt.replace('P', arch.value)
        fmt = NamedStruct.from_namedtuple(fmt_names, fmt)
        

        # Then build the object itself
        obj = type(name, (BlenderObject,), {'VERSION':version, 'FMT': fmt, 'CLASSES': dependencies})
        version_cache[name] = ref(obj)

        return obj, tuple(dependencies)

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
        self.object, self.dependencies = BlenderObjectFactory._build_objects(file, self.struct_dna)
        self.object_name = file.index.type_names[self.struct_dna.index]
        
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

    def __iter__(self):
        file = self.file
        blocks = file.blocks

        for block, offset in blocks:
            if block.sdna == self.sdna_index:
                data = file._read_block(block, offset)
                yield self.object(self._file, data)
    
    @property
    def file(self):
        file = self._file()
        if file is None:
            raise RuntimeError('Parent blend file was freed')
        
        return file

    def find_by_name(self, name):
        """
            Find and build an object by name. If the object does not have a name,
            raise a BlenderFileReadException.

            author: Gabriel Dube
        """
        if not self.has_name:
            raise BlenderFileReadException('Object type do not have a name')

        name_bytes = name.encode()
        for obj in self:
            _name = obj.id.name
            if _name[2:_name.index(0)] == name_bytes:
                return obj

        raise KeyError('File do not have {} objects named \'{}\''.format(self.object_name, name))


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

    Arch   = Enum('Arch', (('X32', 'I'), ('X64', 'Q')), qualname='BlenderFile.Arch')
    Endian = Enum('Endian', (('Little', '<'), ('Big', '>')), qualname='BlenderFile.Endian')

    # Version structures
    VersionInfo   = namedtuple('VersionInfo', ('major', 'minor', 'rev'))
    BlendFileInfo = namedtuple('BlendFileInfo', ('version', 'arch', 'endian'))

    # Index structures
    BlendBlockHeader     = namedtuple('BlendBlockHeader', ('code', 'size', 'addr', 'sdna', 'count'))
    BlendStructFieldDNA  = namedtuple('BlendStructFieldDNA', ('index_type', 'index_name'))
    BlendStructDNA       = namedtuple('BlendStructDNA', ('index', 'fields'))
    BlendStructField     = namedtuple('BlendStructField', ('name', 'type', 'size', 'ptr', 'count'))
    BlendStruct          = namedtuple('BlendStruct', ('name', 'fields'))
    BlendIndex           = namedtuple('BlendIndex', ('field_names', 'type_names', 'type_sizes', 'structures'))

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

    def _export_struct(self, struct):
        """
            Format a blender struct object fields in a human readable dict.
            This is used when creating blender object types

            If recursive is set to True, the function will also export the composed types of struct

            author: Gabriel Dube
        """        
        BlendStruct = BlenderFile.BlendStruct
        BlendStructField = BlenderFile.BlendStructField

        field_names = self.index.field_names
        type_names = self.index.type_names
        type_sizes = self.index.type_sizes

        ptr_size = 8 if self.header.arch == BlenderFile.Arch.X64 else 4

        struct_name = type_names[struct.index]
        struct_fields = []

        for ftype, fname in struct.fields:
            name = field_names[fname]
            _type = type_names[ftype]
            size = type_sizes[ftype]

            is_ptr = name[0] == '*'
            is_array = name[-1] == ']'

            if is_ptr:
                name = name[1::]
                size = ptr_size

            if is_array:
                x, y = name.index('['), name.index(']')
                count = int(name[x+1:y])
                name = name[0:x]
                size *= count
            else:
                count = 1

            struct_fields.append(BlendStructField(name=name, type=_type, size=size, ptr=is_ptr, count=count))

        return BlendStruct(name=struct_name, fields=tuple(struct_fields))

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
        BlendStructFieldDNA = NamedStruct.from_namedtuple(BlenderFile.BlendStructFieldDNA, self._fmt_strct('hh'))
        BlendStructDNA = BlenderFile.BlendStructDNA

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
                fields.append(BlendStructFieldDNA.unpack_from(data, offset))
                offset += 4
            
            structures.append(BlendStructDNA(index=structure_type_index, fields=tuple(fields)))

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
        BlendBlockHeader = NamedStruct.from_namedtuple(BlenderFile.BlendBlockHeader, self._fmt_strct('4siPii'))

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

        if BlenderObjectFactory.CACHE.get(header.version) is None:
            BlenderObjectFactory.CACHE[header.version] = {}

    def find(self, name):
        version = self.header.version
        factories = BlenderObjectFactory.CACHE.get(version)

        # If the factory was already created
        fact = (factories.get(name) or (lambda:None))()
        if fact is not None:
            return fact

        # Factory creation
        try:
            fact = BlenderObjectFactory(self, self.index.type_names.index(name))
            factories[name] = ref(fact)
            return fact
        except ValueError:
            raise BlenderFileReadException('Data type {} could not be found in the blend file'.format(name))

    def close(self):
        self.handle.close()
    def tree(self, type_name, recursive=True, max_level=999):
        """
            Return a representation of the struct. Useful when looking for attributes in a struct

            author: Gabriel Dube
        """
        def field_lookup(struct, indent_level=0):
            indent = '    '*indent_level
            fields = ''
            for ftype, fname in struct.fields:
                type_name, field_name = type_names[ftype], field_names[fname]
                fields += indent+'|-- {} {}'.format(type_name, field_name)+'\n'
                if recursive and indent_level < max_level:
                    if ftype in struct_indexes and not '*' in field_name:
                        fields += field_lookup(self._struct_lookup(ftype), indent_level+1)

            return fields


        field_names = self.index.field_names
        type_names = self.index.type_names
        struct_indexes = [s.index for s in self.index.structures]
        
        type_index = type_names.index(type_name)
        dna = self._struct_lookup(type_index)

        repr = '{} ({})\n'.format(type_name, self.header.version)
        repr += field_lookup(dna)

        return repr

def compile_fmt(fields):
    """
        Compile a list of BlenderFile.BlendStructField into a format string that can be passed
        to a Struct objet

        Author: Gabriel Dube
    """
    base_types = _BASE_TYPES
    fmt = ''
    fmt_names = []

    for f in fields:
        t, count = f.type, str(f.count)
        if f.count > 1 and t != 'char':
            name = (f.name+('_{}_{}'.format(i, count)) for i in range(f.count))
        else:
            name = (f.name,)

        # If type is a pointer
        if f.ptr:
            fmt_names.extend(name)
            fmt += count+'P'
            continue

        # If type is a base type
        if t in base_types:
            # Strings
            if t == 'char' and f.count > 1:
                t = count+'s'
            else:
                t = count+base_types[t]
            fmt_names.extend(name)
            fmt += t
            continue

        # If type is another structure
        fmt += (str(f.size)+'x')
    

    return fmt, fmt_names

   