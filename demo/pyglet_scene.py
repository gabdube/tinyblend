"""
Tinyblend example 
"""

import sys
from os.path import dirname as dn, abspath
sys.path.append(dn(dn(abspath(__file__))))

from pyglet.gl import GL_TRIANGLES, GL_FLOAT, GL_STATIC_DRAW
from pyglet.graphics import vertex_list
from pyglet.window import Window
from pyglet import app

import tinyblend as blend
import pyshaders as shaders
from pyglbuffers import Buffer
from matmath import Mat4, translate, perspective

class Game(Window):

    def __init__(self):
        Window.__init__(self, 800, 600, visible=False, resizable=True, caption='Tinyblend example')
        
        # Most assets are located in the blend file
        self.assets = blend.BlenderFile('assets.blend')
        
        # Load shaders
        self.shader = shaders.from_files_names('shaders/main.glsl.vert', 'shaders/main.glsl.frag')
        self.shader.owned = False
        self.shader.use()

        # Uniforms matrices setup
        self.view = Mat4()
        self.model = Mat4()
        self.proj = Mat4()

        self.view.set_data(translate(None, (0,0,-2.5)))
        self.proj.set_data(perspective(60.0, 800/600, 0.1, 256.0))

        # Extract the assets from the blend file
        self.setup_scene()

        # Show the window
        self.reload_uniforms()
        self.set_visible()

    def setup_scene(self):
        triangle = Buffer.array('(3f)[position](3f)(color)', GL_STATIC_DRAW)
        triangle.init(my_data)

        attr = self.shader.attributes
        attr.inColor.enable()
        attr.inColor.point_to(4, GL_FLOAT, 3, 0)

    def reload_uniforms(self):
        uni = self.shader.uniforms
        uni.view = self.view.data()
        uni.model = self.model.data()
        uni.proj = self.proj.data()

    def on_resize(self, width, height):
        Window.on_resize(self, width, height)
        self.proj.set_data(perspective(60.0, width/height, 0.1, 256.0))
        self.reload_uniforms()

    def on_draw(self):
        # Clear the window
        self.clear()
    
        # Draw the scene 
        self.tri.draw(GL_TRIANGLES)

def main():
    game = Game()
    app.run()

if __name__ == '__main__':
    main()

