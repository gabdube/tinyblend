"""
Tinyblend example 

"""

import sys
from os.path import dirname as dn, abspath
sys.path.append(dn(dn(abspath(__file__))))

import tinyblend as blend
from pyglet.window import Window
from pyglet import app
from pyshaders import from_files_names

class Game(Window):

    def __init__(self):
        Window.__init__(self, 800, 600, visible=False, caption='Tinyblend example')
        self.assets = blend.BlenderFile('assets.blend')
        self.load_assets()
        self.set_visible()

    def load_assets(self):
        scenes = self.assets.find('Scene')
        scene = scenes.find_by_name('MainScene')

        print(self.assets.tree('Object'))

        cam = scene.camera

        

        
def main():
    game = Game()
    app.run()

if __name__ == '__main__':
    main()

