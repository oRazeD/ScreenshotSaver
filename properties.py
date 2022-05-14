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
            ('open_exr', "EXR", "")
        ),
        name='Format Type'
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

    mp4_format_type: EnumProperty(
        items=(
            ('mp4', "MP4", ""),
            ('gif', "GIF", "")
        ),
        name='Format Type'
    )

    mp4_framerate: IntProperty(
        name='Framerate',
        default=2,
        min=0,
        soft_max=24
    )

    mp4_res_downscale: EnumProperty(
        items=(
            ('1', "Full", ""),
            ('2', "1/2", ""),
            ('4', "1/4", "")
        ),
        name='Scale',
        description='Downscale the video output for smaller file sizes'
    )

    mp4_end_repeat_count: IntProperty(
        name='End Repeat',
        description='How many times the end frame repeats',
        default=0,
        min=0,
        soft_max=10
    )

    mp4_start_repeat_count: IntProperty(
        name='Start Repeat',
        description='How many times the start frame repeats',
        default=0,
        min=0,
        soft_max=10
    )

    mp4_crop_type: EnumProperty(
        items=(
            ('none', "None", ""),
            ('from_border', "from Border", ""),
            ('to_resolution', "to Resolution", "")
        ),
        name='Crop',
        description='Crop the input image sequence based on either a border crop or to a specific resolution'
    )

    mp4_crop_res_x: IntProperty(
        name='X',
        description='Desired X resolution of image',
        default=1920,
        min=2,
        step=2,
        soft_max=7680
    )

    mp4_crop_res_y: IntProperty(
        name='Y',
        description='Desired Y resolution of image',
        default=1080,
        min=2,
        step=2,
        soft_max=4320
    )

    mp4_crop_amt_width: IntProperty(
        name='W',
        description='Image width amount to crop (steps in 2)',
        default=0,
        min=0,
        step=2,
        soft_max=7678
    )

    mp4_crop_amt_height: IntProperty(
        name='H',
        description='Image height amount to crop (steps in 2)',
        default=0,
        min=0,
        step=2,
        soft_max=4318
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

    def change_lens_flip(self, context) -> None:
        if self.camera_ob is not None:
            self.camera_ob.scale[0] = -1 if self.lens_flip_x else 1
            self.camera_ob.scale[1] = -1 if self.lens_flip_y else 1

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
    cam_res_x: IntProperty(name='X', update=update_res_x, default=1920)
    cam_res_y: IntProperty(name='Y', update=update_res_y, default=1080)
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
    lens_flip_x: BoolProperty(
        name='Horizontal',
        description='Flip the camera horizontally',
        update=change_lens_flip
    )
    lens_flip_y: BoolProperty(
        name='Vertical',
        description='Flip the camera vertically',
        update=change_lens_flip
    )

    render_frame: IntProperty(
        name='Render Frame',
        description="The frame to render this screenshot on",
        default=0,
        min=0
    )

    # Export Properties
    use_subfolder: BoolProperty(
        name='to Subfolder',
        default=True,
        description='Render this screenshot to a subfolder of the Export Path'
    )
    subfolder_name: StringProperty(name='Folder Name')

    # Render/Shading Properties
    use_defaults: BoolProperty(
        name='Use Defaults',
        default=True,
        description='Use the scene shading at the time of rendering for this screenshot'
    )
    render_type: EnumProperty(
        items=(
            ('workbench', "Workbench", ""),
            ('eevee', "EEVEE", "")
        )
    )
    lighting_type: EnumProperty(
        items=(
            ('studio', "Studio", ""),
            ('matcap', "MatCap", ""),
            ('flat', "Flat", "")
        )
    )
    studio_light_name: StringProperty(default='default')
    matcap_light_name: StringProperty(default='basic_1.exr')
    eevee_light_name: StringProperty(default='city.exr')
    use_wsl: BoolProperty(
        name='World Space Lighting',
        default=False,
        description='Make the light fixed and not follow the camera (Recommended for static shots)'
    )
    color_type: EnumProperty(
        items=(
            ('material', "Material", ""),
            ('single', "Single", ""),
            ('object', "Object", ""),
            ('random', "Random", ""),
            ('vertex', "Vertex", ""),
            ('texture', "Texture", "")
        )
    )
    single_color_value: FloatVectorProperty(
        name="Single Color Value",
        subtype='COLOR_GAMMA',
        default=[.8, .8, .8],
        size=3,
        min=0,
        max=1
    )
    use_backface_culling: BoolProperty(
        name='Backface Culling',
        description='Use back face culling to hide the back side of faces'
    )
    use_cavity: BoolProperty(
        name='Cavity',
        description='Use cavity'
    )
    cavity_ridge: FloatProperty(min=0, max=2.5, subtype='FACTOR', default=0)
    cavity_valley: FloatProperty(min=0, max=2.5, subtype='FACTOR', default=1)
    curve_ridge: FloatProperty(min=0, max=2, subtype='FACTOR', default=1)
    curve_valley: FloatProperty(min=0, max=2, subtype='FACTOR', default=0)
    use_outline: BoolProperty(
        name='Outline',
        description='Render an outline around objects',
        default=True
    )
    outliner_color_value: FloatVectorProperty(
        name="Outline Color Value",
        subtype='COLOR_GAMMA',
        default=[0, 0, 0],
        size=3,
        min=0,
        max=1
    )
    use_spec_lighting: BoolProperty(
        name='Specular Lighting',
        description='Render specular highlights',
        default=True
    )

    eevee_light_name: StringProperty(default='forest.exr')
    use_scene_lights: BoolProperty(
        name='Use Scene Lights',
        description='Render lights and light probes of the scene',
        default=True
    )
    use_scene_world: BoolProperty(
        name='Use Scene World',
        description='Use scene world for lighting',
        default=True
    )
    eevee_use_rotate: BoolProperty(
        name='Use Locked Rotation',
        description=""
    )
    eevee_intensity: FloatProperty(
        name='Strength',
        description="",
        default=1,
        min=0,
        max=2,
        subtype='FACTOR'
    )
    eevee_alpha: FloatProperty(
        name='World Opacity',
        description="",
        default = 0,
        min=0,
        max=1,
        subtype='FACTOR'
    )
    eevee_blur: FloatProperty(
        name='Blur',
        description="",
        default = .5,
        min=0,
        max=1,
        subtype='FACTOR'
    )

    studio_rotate_z: FloatProperty(name='Rotation', min=-3.14159265359, max=3.14159265359, subtype='ANGLE')


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
