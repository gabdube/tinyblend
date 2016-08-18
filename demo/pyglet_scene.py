"""
Tinyblend example 
"""

import sys
from os.path import dirname as dn, abspath
sys.path.append(dn(dn(abspath(__file__))))

from pyglet.gl import GL_TRIANGLES, GL_FLOAT, GL_STATIC_DRAW
from pyglet.gl import glDrawArrays
from pyglet.graphics import vertex_list
from pyglet.window import Window, mouse
from pyglet import app

import tinyblend as blend
import pyshaders as shaders
from pyglbuffers import Buffer
from matmath import Mat4, translate, perspective, rotate

# Load the bindings in order to operate more easily with pyglbuffers
shaders.load_extension('pyglbuffers_bindings')

class Game(Window):

    def __init__(self):
        Window.__init__(self, 800, 600, visible=False, resizable=True, caption='Tinyblend example')
        
        # Most assets are located in the blend file
        self.assets = blend.BlenderFile('_assets.blend')
        
        # Load shaders
        shader = shaders.from_files_names('shaders/main.glsl.vert', 'shaders/main.glsl.frag')
        shader.owned = False
        shader.use()
        shader.enable_all_attributes()
        self.shader = shader

        # Uniforms matrices setup
        self.view = Mat4()
        self.model = Mat4()
        self.proj = Mat4()

        self.rotation = [0,0,0]
        self.position = [0,0, -2.5]
        self.proj.set_data(perspective(60.0, 800/600, 0.1, 256.0))
        self.upload_uniforms()

        # Scene creation
        self.setup_scene()

        # Show the window
        self.set_visible()

    def setup_scene(self):
        " Load the assets in the scene "
        triangle = Buffer.array('(3f)[position](3f)[color]', GL_STATIC_DRAW)
        data =( (( 1.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
                ((-1.0, -1.0, 0.0), (0.0, 1.0, 0.0)),
                (( 0.0,  1.0, 0.0), (0.0, 0.0, 1.0)) )
        triangle.init(data)

        self.tri = triangle

    def upload_uniforms(self):
        " Upload the uniforms to the shader " 

        self.view.set_data(translate(None, tuple(self.position) ))

        mod_mat = rotate(None, self.rotation[0], (1.0, 0.0, 0.0))
        mod_mat = rotate(mod_mat, self.rotation[1], (0.0, 1.0, 0.0))
        self.model.set_data(rotate(mod_mat, self.rotation[2], (0.0, 0.0, 1.0)))

        uni = self.shader.uniforms
        uni.view = self.view.data()
        uni.model = self.model.data()
        uni.proj = self.proj.data()

    def on_resize(self, width, height):
        Window.on_resize(self, width, height)
        self.proj.set_data(perspective(60.0, width/height, 0.1, 256.0))
        self.upload_uniforms()

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.position[2] -= 0.3*scroll_y
        self.upload_uniforms()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons & mouse.LEFT != 0:
            self.rotation[0] += dy * 1.25
            self.rotation[1] += dx * 1.25
        elif buttons & mouse.RIGHT != 0:
            self.position[0] += dx * 0.005
            self.position[1] += dy * 0.005

        self.upload_uniforms()

    def on_draw(self):
        # Clear the window
        self.clear()

        self.tri.bind()
        self.shader.map_attributes(self.tri)
        glDrawArrays(GL_TRIANGLES, 0, len(self.tri))
    
def main():
    game = Game()
    app.run()

if __name__ == '__main__':
    main()

