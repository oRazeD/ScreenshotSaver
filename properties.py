import bpy, os
from bpy.props import *
from .operators import display_error_message


############################################################
# PROPERTY GROUP
############################################################


class SCRSHOT_property_group(bpy.types.PropertyGroup):
    ### UPDATE FUNCTIONS ###

    def bad_recording_setup(self, context) -> None:
        if self.record_on_save and not len(context.scene.scrshot_camera_coll):
            display_error_message('Could not render because no screenshot cameras exist.')
            self.record_on_save = False
            return None

    def update_export_path(self, context) -> None:
        if self.export_path != ' ' and not os.path.exists(bpy.path.abspath(self.export_path)):
            self.export_path = ' '

    ### PROPERTIES ###

    export_path: StringProperty(name="", default=" ", description="", subtype='DIR_PATH', update=update_export_path) #default="//screenshots\\"

    format_type: EnumProperty(
        items=(
            ('png', "PNG", ""),
            ('jpeg', "JPEG", ""),
            ('exr', "EXR", "")
        )
    )

    record_on_save: BoolProperty(
        name="Record on Save",
        description='Begin/stop recording screenshots when you save the file',
        update=bad_recording_setup
    )

    cameras_visible: BoolProperty(
        name="Camera Visiblity",
        description='Toggle the viewport visibility of the cameras collection'
    )


class SCRSHOT_collection_property(bpy.types.PropertyGroup):
    camera_ob: PointerProperty(
        name = "",
        type = bpy.types.Object,
        description='The camera object used for this screenshot item'
    )


    ### UPDATE FUNCTIONS ###

    def name_conflict_handling(self, context) -> None:
        # Detect conflicting/repeating names
        item_name_count = 0
        repeated_names = False
        for item in context.scene.scrshot_camera_coll:
            if item.name == self.name:
                item_name_count += 1

            if item_name_count > 1:
                repeated_names = True
                break

        if repeated_names:
            self.name = self.saved_name
            display_error_message('You cannot use repeating screenshot names.')
            return None

        # Rename identifiers for object/camera data
        if self.saved_name:
            for ob in bpy.data.objects:
                if ob.screenshot_id == self.saved_name and ob.type == 'CAMERA':
                    ob.screenshot_id = self.name
                    ob.name = self.name

            for cam in bpy.data.cameras:
                if cam.screenshot_id == self.saved_name:
                    cam.screenshot_id = self.name
                    cam.name = self.name

        self.saved_name = self.name

    def update_res_x(self, context) -> None:
        if self.lock_res and self.cam_res_x != self.cam_res_y:
            self.cam_res_y = self.cam_res_x

        context.scene.render.resolution_x = self.cam_res_x

    def update_res_y(self, context) -> None:
        if self.lock_res and self.cam_res_y != self.cam_res_x:
            self.cam_res_x = self.cam_res_y

        context.scene.render.resolution_y = self.cam_res_y

    def match_screenshot_id(self, context) -> None:
        if self.camera_ob is not None:
            self.camera_ob.screenshot_id = self.camera_ob.data.screenshot_id = self.name

    def change_camera_type(self, context) -> None:
        if self.camera_ob is not None:
            self.camera_ob.data.type = 'ORTHO' if self.cam_type == 'ortho' else 'PERSP'

    def change_lens_type(self, context) -> None:
        if self.camera_ob is not None:
            self.camera_ob.data.lens_unit = 'FOV' if self.lens_type == 'fov' else 'MILLIMETERS'

    ### PROPERTIES ###

    # Core Properties
    id: IntProperty()
    name: StringProperty(update=name_conflict_handling)
    saved_name: StringProperty()
    enabled: BoolProperty(default=True)
    camera_ob: PointerProperty(
        name = "",
        type = bpy.types.Object,
        description='The camera object used for this screenshot item',
        update=match_screenshot_id
    )
    cam_res_x: IntProperty(name='X', update=update_res_x)
    cam_res_y: IntProperty(name='Y', update=update_res_y)
    lock_res: BoolProperty(
        name='Lock Resolution',
        description='Sync both resolution sliders for square images',
        update=update_res_x
    )
    cam_type: EnumProperty( # Override property to hide Panoramic
        items=(
            ('persp', "Perspective", ""),
            ('ortho', "Orthographic", "")
        ),
        name='Lens Type',
        update=change_camera_type
    )
    lens_type: EnumProperty( # Override property to rename enums
        items=(
            ('mm', "MM", ""),
            ('fov', "FOV", "")
        ),
        name='Lens Unit',
        update=change_lens_type
    )

    # Render/Shading Properties
    render_type: EnumProperty(
        items=(
            ('workbench', "Workbench", ""),
            ('eevee', "EEVEE", "")
        )
    )
    use_defaults: BoolProperty(
        name='Use Defaults',
        default=True,
        description='Use the scene shading at the time of rendering for this screenshot'
    )
    lighting_type: EnumProperty(
        items=(
            ('studio', "Studio", ""),
            ('matcap', "MatCap", ""),
            ('flat', "Flat", "")
        )
    )
    use_wsl: BoolProperty(
        name='World Space Lighting',
        default=False,
        description='Make the light fixed and not follow the camera (Recommended for static shots)'
    )
    studio_rotate_z: FloatProperty(name='Rotation', min=-3.14159265359, max=3.14159265359, subtype='ANGLE')
    use_subfolder: BoolProperty(
        name='Export to Subfolder',
        default=False,
        description='Render this screenshot to a subfolder of the Export Path'
    )
    subfolder_name: StringProperty(name='Folder Name')


##################################
# REGISTRATION
##################################


classes = (
    SCRSHOT_property_group,
    SCRSHOT_collection_property
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.screenshot_saver = PointerProperty(type=SCRSHOT_property_group)
    bpy.types.Scene.scrshot_camera_coll = CollectionProperty(type=SCRSHOT_collection_property)
    bpy.types.Scene.scrshot_camera_index = IntProperty()

    bpy.types.Object.screenshot_id = StringProperty()
    bpy.types.Camera.screenshot_id = StringProperty()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.screenshot_saver
    del bpy.types.Scene.scrshot_camera_coll
    del bpy.types.Scene.scrshot_camera_index

    del bpy.types.Object.screenshot_id
    del bpy.types.Camera.screenshot_id


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
