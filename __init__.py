bl_info = {
    "name":"Screenshot Saver",
    "author":"Ethan Simon-Law",
    "location": "3D View -> Sidebar -> Screenshot Saver",
    "description": "A tool for taking screenshots when you save",
    "version":(0, 1),
    "blender":(3, 0, 0),
    "tracker_url": "https://discord.com/invite/wHAyVZG",
    "category": "3D View"
}


import importlib, bpy
from bpy.app.handlers import persistent
from .operators import display_error_message


################################################################################################################
# HANDLERS
################################################################################################################


@persistent
def screenshot_save_handler(scene) -> None:
    '''Handles saving screenshots whenever the file is saved'''
    scene = bpy.context.scene

    if scene.screenshot_saver.record_on_save:
        if not len(scene.scrshot_camera_coll):
            display_error_message('Could not render because no screenshot cameras exist.') # Send this before saving
            return None

        bpy.ops.scrshot.render_screenshots()


################################################################################################################
# REGISTRATION
################################################################################################################


module_names = (
    "ui",
    "operators",
    "properties"
)

modules = []
for module_name in module_names:
    if module_name in locals():
        modules.append(importlib.reload(locals()[module_name]))
    else:
        modules.append(importlib.import_module("." + module_name, package=__package__))

def register():
    for mod in modules:
        mod.register()

    bpy.app.handlers.save_post.append(screenshot_save_handler)

def unregister():
    for mod in modules:
        mod.unregister()

    bpy.app.handlers.save_post.remove(screenshot_save_handler)


# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
