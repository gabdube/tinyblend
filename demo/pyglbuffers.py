# -*- coding: utf-8 -*-
"""
''MIT License

Copyright (c) 2016 Gabriel Dubé

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from pyglet.gl import (glGenBuffers, glBindBuffer, GLuint, glBufferData,
  glIsBuffer, glDeleteBuffers, GLfloat, GLdouble, GLbyte, GLubyte, GLint,
  GLshort, GLushort, glGetBufferParameteriv, glGetBufferSubData, glBufferSubData,
  glMapBuffer, glUnmapBuffer, glGetBufferPointerv)

from pyglet.gl import (GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER, GL_PIXEL_PACK_BUFFER,
  GL_PIXEL_UNPACK_BUFFER, GL_STATIC_COPY, GL_STATIC_DRAW, GL_STATIC_READ,
  GL_DYNAMIC_COPY, GL_DYNAMIC_DRAW, GL_DYNAMIC_READ, GL_STREAM_COPY, GL_STREAM_DRAW,
  GL_STREAM_READ, GL_TRUE, GL_BUFFER_SIZE, GL_READ_ONLY, GL_WRITE_ONLY, GL_READ_WRITE,
  GL_BUFFER_MAPPED, GL_BUFFER_ACCESS, GL_BUFFER_USAGE, GL_BUFFER_MAP_POINTER, 
  GL_FLOAT, GL_DOUBLE, GL_BYTE, GL_UNSIGNED_BYTE, GL_INT, GL_UNSIGNED_INT,
  GL_SHORT, GL_UNSIGNED_SHORT)

try:
    import pyglbuffers_extensions
    from importlib import import_module
    NO_EXTENSIONS = False
except:
    NO_EXTENSIONS = True

import re
from ctypes import byref, Structure, cast, POINTER, sizeof, c_void_p
from functools import lru_cache, namedtuple
from collections.abc import Sequence
from sys import modules

#Loaded extensions name are added in here
LOADED_EXTENSIONS = []

BUFFER_FORMAT_TYPES_MAP = { 'f': (GLfloat, GL_FLOAT), 'd': (GLdouble, GL_DOUBLE),
                            'b': (GLbyte, GL_BYTE), 'B': (GLubyte, GL_UNSIGNED_BYTE),
                            'i': (GLint, GL_INT), 'I': (GLuint, GL_UNSIGNED_INT),
                            's': (GLshort, GL_SHORT), 'S': (GLushort, GL_UNSIGNED_SHORT)}
                            
pyvars = re.compile('[_a-zA-Z][_\w]+')

map_info = namedtuple('MappingInformation', ['access', 'target', 'ptr', 'size'])

def ptr_array(arr):
    " Cast an array in a pointer "
    return cast(arr, POINTER(arr._type_))
    
def eval_index(index, length):
    if index < 0 and index >= (-length) :  
        return length+index
    elif index >= length:
        raise IndexError('Index "{}" out of bound, buffer has a length of "{}"'.format(index, length))
    elif index < (-length):
        raise IndexError('Index "{}" out of bound, buffer has a length of "{}"'.format(index, length))
        
    return index

def eval_slice(slice, length):
    _start = slice.start
    _stop = slice.stop
    step = slice.step
    
    if step is None: 
        step = 1
    elif step == 0:
        raise IndexError('Step cannot be 0')
        
    if step < 1:
        start, stop = _stop, _start 
        if _start is None: start = length-1
        if _stop is None: stop = 0     
    else:
        start, stop = _start, _stop   
        if _start is None: start = 0
        if _stop is None: stop = length      
            
    if start < 0: start = length+start   
    if stop < 0: stop = length+stop

    if start >= length or stop > length:
        raise IndexError('Slices indexes "{}:{}" out of bound, buffer has a length of "{}"'.format(_start, _stop, length))
        
    if start < 0 or stop < 0:
        raise IndexError('Slices indexes "{}:{}" out of bound, buffer has a length of "{}"'.format(_start, _stop, length))

    return start, stop, step

class BufferFormatError(Exception):
    def __init__(self, *args):
        super().__init__(*args)
        
class PyGlBuffersExtensionError(Exception):
    def __init__(self, *args):
        super().__init__(*args)

class GLGetObject(object):
    """
        Descriptor that wraps glGet* function
    """
    __slots__ = ['pname']
    buffer = GLint(0)
    
    def __init__(self, pname): self.pname = pname
    def __set__(self): raise AttributeError('Attribute is not writable')
    def __delete__(self): raise AttributeError('Attribute cannot be deleted')

class GetBufferObject(GLGetObject):
    __slots__ = []

    def __get__(self, instance, cls):
        instance.bind()
        glGetBufferParameteriv(instance.target, self.pname, byref(self.buffer))
        return self.buffer.value

class BufferFormat(object):
    """
        This class has two functions:
        - Pack formatted python data into a raw buffer.
        - Read a formatted buffer and return formatted python data
        
        Fields:
            struct: ctypes struct representing this format
            item: named tuple representing this format
            tokens: Information on the formatted values fields
    """
    
    __fields__ = ['struct', 'item', 'tokens']
    
    pattern = re.compile(r'\((\d)+([fdbBsSiI])\)\[(\w+)\]')
    token = namedtuple('FormatToken', ('offset', 'gl_type', 'size', 'type', 'name', ))
    
    @staticmethod
    def new(format):
        """"
            Call the required function to create a BufferFormat depending on the "format" type.
            
            Parameters:
                format: Data to build the format from.
        """
        if isinstance(format, BufferFormat):
            format2 = BufferFormat()
            for field in BufferFormat.__fields__:
                setattr(format2, field, getattr(format, field))
            
            format = format2
            
        elif isinstance(format, str):
            format = BufferFormat.from_string(format)
        else:
            raise TypeError("Format must be a string or a BufferFormat object.")
    
        return format
    
    
    @classmethod
    @lru_cache(maxsize=16)
    def from_string(cls, format_str):
        """ 
            Create a buffer format from a string. Generated buffer format are
            cached, so this function is not expensive to call.
            
            A format string is composed of N format token.
            A format token follow these rules: ({number}{format char})[{name}]
            Whitespaces are ignored.
            
            Available format char:
              f: float
              d: double
              b: byte
              B: unsigned Byte
              s: short
              S: unsigned short
              i: int
              I: unsigned int            
            
            Example:
                "(3i)[vertex](4f)[color]"
                "(4f)[foo] (4f)[bar] (4d)[yolo]"
        """
        format_str = format_str.replace(' ', '')
        format_str_2 = ""
        
        if len(format_str) == 0:
            raise BufferFormatError('Format must be present')
        
        # Create the tokens
        tokens, offset = [], 0
        for match in BufferFormat.pattern.finditer(format_str):
            groups = match.groups()
            
            _type, gl_type = BUFFER_FORMAT_TYPES_MAP.get(groups[1])
            size=int(groups[0])
            
            name=groups[2]
            name_match = pyvars.match(name)
            if name_match is None or name_match.span() != (0, len(name)):
                raise ValueError('"{}" is not a valid variable name'.format(name))
            
            token = BufferFormat.token(size=size, type=_type*size, name=name, gl_type=gl_type, offset=offset)
            tokens.append(token)
            offset += sizeof(token.type)
            format_str_2 += format_str[match.start():match.end()]
            
        if format_str_2 != format_str:
            raise BufferFormatError('Format string is not valid')
                
        bformat = super().__new__(cls)
        
        # Save the tokens
        bformat.tokens = tokens        
        
        # Build the item
        bformat.item = namedtuple('V', [t.name for t in tokens])
        
        # Build the structure
        struct_fields = [(t.name, t.type) for t in tokens]
        bformat.struct = type('BufferStruct', (Structure,), {'_fields_': struct_fields})
        
        return bformat
        
    def pack(self, data):
        """
            Pack python sequence into a c struct. The data must match the
            BufferFormat format.
            
            Argument:
                data: Sequence of python data. 
        """
        if len(data) == 0:
            raise ValueError('No data to pack')
        
        buffers = (self.struct*len(data))()
        
        # Allow single tuple when there is only one token
        # Ex: ((1,2,3), (4,5,6)) is accepted instead of (((1,2,3),), ((4,5,6),))
        if len(self.tokens) > 1 or isinstance(data[0][0], Sequence):
            iter_data = iter(data)
        else:
            iter_data = ((d,) for d in data)

        try:
            error = False
            for data, buffer in zip(iter_data, iter(buffers)):
                for subdata, token in zip(iter(data), iter(self.tokens)):
                    setattr(buffer, token.name, token.type(*subdata))
                    
        except TypeError:
            error = True
            
        if error:
            msg = 'Expected Sequence with format "{}", found "{}"'
            
            for k, v in BUFFER_FORMAT_TYPES_MAP.items():
                if v is token.type._type_:
                    format_str = str(token.size)+k
    
            raise ValueError(msg.format(format_str, subdata))
        
        return buffers
        
    def pack_single(self, data):
        """
            Pack a python value into a c struct. The value must match
            the BufferFormat format.
            
            Argument:
                data: Python value. 
        """
        try:
            # Allow single tuple when there is only one token
            # Ex: (1,2,3) is accepted instead of ((1,2,3),)
            if len(self.tokens) == 1 and not isinstance(data[0], Sequence):
                data = (data,)                
                
            buffer = self.struct()
            error = False
            for subdata, token in zip(iter(data), iter(self.tokens)):
                setattr(buffer, token.name, token.type(*subdata))
                
        except TypeError:
            error = True
            
        if error:
            msg = 'Expected Sequence with format "{}", found "{}"'
            
            for k, v in BUFFER_FORMAT_TYPES_MAP.items():
                if v is token.type._type_:
                    format_str = str(token.size)+k
    
            raise ValueError(msg.format(format_str, subdata))
        
        return buffer
        
        
    def unpack(self, data):
        """
            Unpack a sequence of ctypes struct in a named tuple. The packed data must 
            have been packed by the formatter.
            
            Argument:
                data: sequence of ctypes struct. 
        """
        if len(data) > 0 and not isinstance(data[0], self.struct):
            raise ValueError("Impossible to unpack data that was not packed by the formatter")
        
        data_dict = {}
        unpack_data = []
        for d in data:
            for t in self.tokens:
                data_dict[t.name] = tuple(getattr(d, t.name))
            
            unpack_data.append(self.item(**data_dict))
        
        return tuple(unpack_data)
        
    def unpack_single(self, data):
        """
            Unpack a ctypes struct in a named tuple. The packed data must 
            have been packed by the formatter.
            
            Argument:
                data: ctypes struct
        """
        if not isinstance(data, self.struct):
            raise ValueError("Impossible to unpack data that was not packed by the formatter")
            
        data_dict = {}
        for t in self.tokens:
            data_dict[t.name] = tuple(getattr(data, t.name))
        
        return self.item(**data_dict)
            
class Buffer(object):
    """
        Wrapper over an opengl buffer.
    
        Slots:
            bid: Underlying buffer identifier
            data: Object that allows pythonic access to the buffer data
            target: Buffer target (ex: GL_ARRAY_BUFFER)
            owned: If the object own the underlying data
    """

    __slots__ = ['bid', 'format', 'target', '_usage', 'data', 'owned',
                 '__weakref__', 'mapinfo']    
    
    size = GetBufferObject(GL_BUFFER_SIZE)    
    mapped = GetBufferObject(GL_BUFFER_MAPPED)
    access = GetBufferObject(GL_BUFFER_ACCESS)
    usage = GetBufferObject(GL_BUFFER_USAGE)
    
    def __init__(self, buffer_id, format, usage=GL_DYNAMIC_DRAW, owned=False):
        self.bid = GLuint(getattr(buffer_id, 'value', buffer_id))
        self.owned = owned
        self._usage = usage
        self.format = BufferFormat.new(format)
        self.target = None
        self.mapinfo = None

    @staticmethod
    def __alloc(cls, target, format, usage): 
        buf = super().__new__(cls)
        buf.owned = True
        buf.bid = GLuint()
        glGenBuffers(1, byref(buf.bid))
        glBindBuffer(target, buf.bid)
        buf._usage = usage
        buf.format = BufferFormat.new(format)
        buf.target = target
        buf.mapinfo = None
        
        return buf
        
    @classmethod
    def array(cls, format, usage=GL_STATIC_DRAW):
        " Generate a buffer that hold vertex data (GL_ARRAY_BUFFER) "
        return Buffer.__alloc(cls, GL_ARRAY_BUFFER, format, usage)
        
    @classmethod
    def element(cls, format, usage=GL_STATIC_DRAW):
       " Generate a buffer that hold vertex indices (GL_ELEMENT_ARRAY_BUFFER) "
       return Buffer.__alloc(cls, GL_ELEMENT_ARRAY_BUFFER, format, usage) 
       
    @classmethod
    def pixel_pack(cls, format, usage=GL_STATIC_DRAW):
       """
           Generate a buffer that is used as the destination for OpenGL commands
           that read data from image objects  (GL_PIXEL_PACK_BUFFER) 
       """
       return Buffer.__alloc(cls, GL_PIXEL_PACK_BUFFER, format, usage)       
       
    @classmethod
    def pixel_unpack(cls, format, usage=GL_STATIC_DRAW):
       """
           Generate a buffer that it is used as the source of data for commands 
           like glTexImage2D() (GL_PIXEL_UNPACK_BUFFER)
       """
       return Buffer.__alloc(cls, GL_PIXEL_UNPACK_BUFFER, format, usage)
    
    def valid(self):
        " Return True if the underlying opengl buffer is valid or False if it is not "
        return glIsBuffer(self.bid) == GL_TRUE
        
    def bind(self, target=None):
        """
            Bind the buffer to its target
        
            Arguments:
                target: Default to None. One of the GL target (such as GL_ARRAY_BUFFER)
                        If None, use the default buffer target.
        """
        if self.target is None:
            raise ValueError("Buffer target was not defined")
            
        target = target if target is not None else self.target
        glBindBuffer(target, self.bid)
        
    def map(self, access=GL_READ_WRITE, target=None):
        """
        Map the buffer locally. This increase the reading/writing speed.
        If the buffer was already mapped, a BufferError will be raised.
        
        Arguments:
            access: Buffer access. Can be GL_READ_WRITE, GL_READ_ONLY, GL_WRITE_ONLY. Default to GL_READ_WRITE
            target: Target to bind the buffer to. If None, use the buffer default target. Default to None.
        """
        if self.mapped == GL_TRUE:
            raise BufferError("Buffer is already mapped")
        
        target = target if target is not None else self.target
        glBindBuffer(target, self.bid)
        glMapBuffer(target, access)
        
        ptr_type = POINTER(self.format.struct)
        ptr = c_void_p()
        glGetBufferPointerv(target, GL_BUFFER_MAP_POINTER, byref(ptr))        
        
        self.mapinfo = map_info(target=target, access=access, ptr=cast(ptr,ptr_type),
                                size=self.size//sizeof(self.format.struct))
        
    def unmap(self):
        """
            Unmap the buffer. Will raise a BufferError if the buffer is not mapped.
        """
        
        if self.mapped != GL_TRUE:
            raise BufferError("Buffer is not mapped")
            
        glUnmapBuffer(self.mapinfo.target)
        self.mapinfo = None
        
    def init(self, data, target=None):
        """
            Fill the buffer data with "data". Data must be formatted using the
            parent buffer format. This calls glBufferData. To initialize a buffer
            without data (ie: only reserving space), use reserve().
            
            This method is called when assiging values to the data field of a buffer.
            Ex: buffer.data = ( (1.0, 2.0, 3.0, 4.0),  )
            
            Parameters:
                data: Data to use to initialize the buffer.
        """
        if target is None:
            target = self.target
            
        self.bind(target)
        cdata = self.format.pack(data)
        glBufferData(target, sizeof(cdata), ptr_array(cdata), self._usage)
        
    def reserve(self, length, target=None):
        """
            Fill the buffers with "length" zeroed elements.
            
            Parameters:
                length: Number of element the buffer will be able to hold
        """
        if target is None:
            target = self.target
            
        self.bind()
        glBufferData(target, sizeof(self.format.struct)*length, c_void_p(0), self._usage)
    
    def __getitem_mapped(self, buffer, key):
        " Called by __getitem__ if the buffer content is mapped locally "
        info = buffer.mapinfo
        if info.access == GL_WRITE_ONLY:
            raise BufferError("Impossible to read to a buffer mapped with GL_WRITE_ONLY")
            
        blen = info.size
        
        if isinstance(key, int):
            key = eval_index(key, blen)
            return buffer.format.unpack_single(info.ptr[key])
        else: 
            start, stop, step = eval_slice(key, blen)
            return buffer.format.unpack(info.ptr[start:stop:step])
        
    def __setitem_mapped(self, buffer, key, value):
        " Called by __setitem__ if the buffer content is mapped locally "
        info = buffer.mapinfo        
        if buffer.mapinfo.access == GL_READ_ONLY:
            raise BufferError("Impossible to write to a buffer mapped with GL_READ_ONLY")
            
        blen = info.size
        
        if isinstance(key, int):
            key = eval_index(key, blen)
            info.ptr[key] = buffer.format.pack((value,))[0]
        else: 
            start, stop, step = eval_slice(key, blen)
            if step == -1:
                value = list(reversed(value))
                step = 1
                
            # Ctypes pointers do not support slicing assignment
            for count, i in enumerate(range(start, stop, step)):
                info.ptr[i] = buffer.format.pack((value[count],))[0]
    
    def __getitem__(self, key):
        if not isinstance(key, int) and not isinstance(key, slice):
            raise KeyError('Key must be an integer or a slice, got {}'.format(type(key).__qualname__))

        if self.mapinfo is not None:
            return self.__getitem_mapped(self, key)

        self.bind()            
        blen = len(self) 
       
        if isinstance(key, int):
            key = eval_index(key, blen)
            
            buf = self.format.struct()
            buf_size = sizeof(buf)
            glGetBufferSubData(self.target, key*buf_size, buf_size, byref(buf))
            
            return self.format.unpack_single(buf)
        
        else:
            start, stop, step = eval_slice(key, blen)
            buf_len = stop-start
            buf = (self.format.struct*buf_len)()
            buf_size = sizeof(buf)
            buf_offset = start * sizeof(self.format.struct)
            
            glGetBufferSubData(self.target, buf_offset, buf_size, byref(buf))
            
            return self.format.unpack(buf[::step])
            
    def __setitem__(self, key, value):
        if not isinstance(key, int) and not isinstance(key, slice):
            raise KeyError('Key must be an integer or a slice, got {}'.format(type(key).__qualname__))

        if self.mapinfo is not None:
            return self.__setitem_mapped(self, key, value)

        self.bind()
        blen = len(self)            
            
        if isinstance(key, int):
            key = eval_index(key, blen)
            buf = self.format.pack((value,))
            buf_size = sizeof(buf)
            glBufferSubData(self.target, key*buf_size, buf_size, byref(buf))
            
        else:
            if key.step is not None and key.step not in (1, -1):
                raise NotImplementedError('Unmapped buffer write do not support steps different than 1.')
            if key.step == -1:
                value = list(reversed(value))                
                
            start, stop, step = eval_slice(key, blen)
            if stop-start != len(value):
                raise ValueError("Buffer do not support resizing")
                
            buf = self.format.pack(value)
            buf_size = sizeof(self.format.struct) * (stop-start)
            buf_offset = start * sizeof(self.format.struct)
                
            
            glBufferSubData(self.target, buf_offset, buf_size, byref(buf))
            
    def __repr__(self):
        return repr(self[::])
        
    def __enter__(self):
        self.map()

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.unmap()
            return True
        
        return False
        
    def __bool__(self):
        return self.valid() 
        
    def __len__(self):
        return self.size//sizeof(self.format.struct)
        
    def __del__(self):
        if getattr(self, 'owned', False) and self.valid():
            if self.mapped == GL_TRUE:
                self.unmap()
            
            glDeleteBuffers(1, byref(self.bid))
            

def extension_loaded(extension_name):
    """
        Return True if the extension is loaded, False otherwise.
        
        Arguments:
            extension_name: Name of the extension to check
    """
    return extension_name in LOADED_EXTENSIONS
        
def find_extension(extension_name):
    """
        Load the extension module. Used internally.
    """
    
    if NO_EXTENSIONS:
        raise ImportError('pyglbuffers extension module cannot be found. Maybe it was not installed?')
        
    try:
        ext = import_module('.'+extension_name, pyglbuffers_extensions.__package__)
        return ext
    except ImportError:
        raise ImportError('No extension named "{}" found'.format(extension_name))
    
def check_extension(extension_name):
    """
        Return True if the client can use the extension, False otherwise
        
        Arguments:
            extension_name: Name of the extension to check
    """
    ext = find_extension(extension_name)
    return ext.supported()
    
def load_extension(extension_name):
    """
        Load the extension. Will raise an ImportError if the extension was already loaded
        or a PyShadersExtensionError if the extension is not supported by the client.
        
        Arguments:
            extension_name: Name of the extension to check
    """
    if extension_name in LOADED_EXTENSIONS:
        raise ImportError('Extension "{}" is already loaded'.format(extension_name))
        
    ext = find_extension(extension_name)
    if ext.supported() is False:
        raise PyGlBuffersExtensionError('Extension "{}" is not supported'.format(extension_name))

    
    ext.load(modules['pyglbuffers'])
    LOADED_EXTENSIONS.append(extension_name)