# Tinyblend

Tinyblend is a very small and lazy library that reads [Blender](https://www.blender.org/) file data (.blend).  
Tinyblend was tested on Linux and Windows and on Blender 2.77, but it should work on any OS and any blender version.  
Tinyblend **does not** support writing blender files and **does not** support reading compressed files.  

Running the test suite requires [pytest](http://doc.pytest.org/en/latest/)

See the `/demo` folder for an example. (Requires [pyglet](https://bitbucket.org/pyglet/pyglet/wiki/Home))

### Requirements

* Python 3.4 and up (tested with 3.5)

### Installation

`pip install tinyblend`

### License

>MIT License

>Copyright (c) 2016 Gabriel Dubé

>Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

>The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


### How it works

Tinyblend was created to be fast and very easy on memory. To achieve this, tinyblend is very lazy. When a Blender file is imported,
only the file schema is loaded in memory. This allows to load huge files quickly and without problems. Using this method the large amount
of "garbage" data in a blend file can be ignored.

When accessing an object type for the first time, tinyblend look at the file shema for the object structure and then dynamically compiles
the structure into a python type (class). This allows tinyblend to potentially load blender file from any versions. The object is then cached for speed.

Compiled types are cached by blender version. So it's possible to load data from two different versions without problems.

The data of the extracted object can be accessed as if it was a "normal" python object. `scene.id.name` for example.

The compiled object lifetime is not infinite, as soon as there is no active object of a his type, the python GC will free the type.

Finally, when an object is loaded, only its immediate fields are parsed. Non immediate field (fields with a pointer type), are only loaded
when accessed for the first time (the value loaded is then cached). This extra action is completely invisible to the user.

### Developer Guide

You will be happy to learn that the tinyblend apui is indeed tiny.

#### Loading/Closing a Blender file

Loading a Blender file is done through the `BlenderFile` type. The fist argument of the constuctor is the blend file path.  
Use the `close` method when done with the file to close the underlying file handle. Note that after the file is closed, it will be
impossible to load other objects.

```python
from tinyblend import BlenderFile

blend = BlenderFile('rabid_squirrel.blend')
print(blend.header) # BlendFileInfo(version=VersionInfo(major=2, minor=7, rev=7), arch=<Arch.X64: 'Q'>, endian=<Endian.Little: '<'>)
# Do stuff
blend.close()

```

#### Printing a type representation

To list the structure names available in a blend file, use the method `list_structures`.

Blender is huge and probably has hundreds of different (undocumented) structures. You probably don't want to check the source
in order to see what fields a structure has. Hopefully, the tinyblend library has a method named `tree` that returns a representation
of the underlying struct.

The tree functions is also available on instanced blender object.

```python
from tinyblend import BlenderFile

blend = BlenderFile('super_ragdoll.blend')
structs = blend.list_structures()
print('Scene' in structs)  # True
print(blend.tree('Scene'))
# See demo/scene_struct.txt for the output (the scene struct has 461 fields)
```

#### Reading object data

Reading blend file is done in two steps (3 if you count loading the blend file).  

A blender file has a `list` method that returns a `BlenderObjectFactory`. The factory is really just an interface
to easily read data of the same type from a blender file.

Then, from the factory, the method `find_by_name` can be used to ... you guessed right! Find an object by name.  
Its also possible to iter over a factory to return all its object (if the object do not have a name for example).

```python
from tinyblend import BlenderFile

blend = BlenderFile('power_weasel.blend')
scenes = BlenderFile.list('Scene')
print(len(scenes))  # 2

my_scene = scenes.find_by_name('the_forest')
print(my_scene)          #<Tinyblend.Scene object at 0xXXXXX>
print(my_scene.id.name)  #b"SCthe_forest"

for scene in scenes:
    print(scene)
    print(my_scene.id.name)

```

#### Important implementation stuff

First, the loading done by TinyBlend is very basic. All it does is parse the binary data and put the value in a variable. This means that,
for example, the name returned `scene.id.name` begins with an internal type identifier (SC).

Second, each time the same an object is loaded from the blend file, a different instance is created. But tinyshaders also implements equality
testing on all its compiled objects. Basically it means this:

```python
scene1 = scenes.find_by_name('the_forest')
scene2 = scenes.find_by_name('the_forest')
print(scene1 is scene2) # False
print(scene1 == scene2) # True
```

### Pretty picture

![Alt text](/demo/img.PNG "Image")  
