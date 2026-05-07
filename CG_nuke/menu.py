import nuke
import os

nuke.pluginAddPath(os.path.dirname(__file__))

from auto_precomp import createAutoPrecomp

toolbar = nuke.menu("Nodes")

menu = toolbar.addMenu("CG_NUKE", icon=os.path.join(os.path.dirname(__file__), "cg_logo.png"), index=-1)

menu.addCommand("auto_precomp", "createAutoPrecomp()",'^1')
