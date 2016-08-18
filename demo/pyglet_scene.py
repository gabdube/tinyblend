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
from matmath import Mat4, translate, perspective

# Load the bindings in order to operate more easily with pyglbuffers
shaders.load_extension('pyglbuffers_bindings')

class Game(Window):

    def __init__(self):
        Window.__init__(self, 800, 600, visible=False, resizable=True, caption='Tinyblend example')
        
        # Most assets are located in the blend file
        self.assets = blend.BlenderFile('assets.blend')
        
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

        self.zoom = -2.5
        self.view.set_data(translate(None, (0,0,self.zoom)))
        self.proj.set_data(perspective(60.0, 800/600, 0.1, 256.0))
        self.upload_uniforms()

        # States
        self.mouse_states = {mouse.LEFT: None}

        # Scene creation
        self.setup_scene()

        # Show the window
        self.set_visible()

    def setup_scene(self):
        " Load the assets in the scene "
        triangle = Buffer.array('(3f)[position](3f)[color]', GL_STATIC_DRAW)
        data =( (( 1.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
                ((-1.0, -1.0, 0.0), (0.0, 1.0, 0.0)),
                (( 0.0,  1.0, 0.0), (0.0, 1.0, 1.0)) )
        triangle.init(data)

        self.tri = triangle

    def upload_uniforms(self):
        " Upload the uniforms to the shader " 

        uni = self.shader.uniforms
        uni.view = self.view.data()
        uni.model = self.model.data()
        uni.proj = self.proj.data()

    def on_resize(self, width, height):
        Window.on_resize(self, width, height)
        self.proj.set_data(perspective(60.0, width/height, 0.1, 256.0))
        self.upload_uniforms()

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.zoom -= 0.3*scroll_y
        self.view.set_data(translate(None, (0,0,self.zoom)))
        self.upload_uniforms()

    def on_mouse_press(self, x, y, button, modifiers):
        self.mouse_states[button] = (x, y)

    def on_mouse_release(self, x, y, button, modifiers):
        self.mouse_states[button] = None

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons & mouse.LEFT != 0:
            pass
        elif buttons & mouse.LEFT != 0:
            pass

    def on_draw(self):
        # Clear the window
        self.clear()

        self.tri.bind()
        self.shader.map_attributes(self.tri)
        glDrawArrays(GL_TRIANGLES, 0, len(self.tri))
    
        # Draw the scene 
        #self.tri.draw(GL_TRIANGLES)

def main():
    game = Game()
    app.run()

if __name__ == '__main__':
    main()

