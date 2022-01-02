import bpy, os, json, time
from bpy.types import Operator

import logging
log = logging.getLogger(__name__)
if "PYDEVD_USE_FRAME_EVAL" in os.environ: # If using the Python Dev add-on for blender, set config to debug
    logging.basicConfig(level='DEBUG')


################################################################################################################
# FUNCTIONS & MIX-IN
################################################################################################################


def poll_active_screenshot_item(context) -> bool:
    '''Poll for the active screenshot item'''
    scene = context.scene

    if not len(scene.scrshot_camera_coll):
        return False
    elif (scene.scrshot_camera_index + 1) > len(scene.scrshot_camera_coll):
        return False
    return True


def display_error_message(message='', title='Screenshot Saver Warning', icon='ERROR') -> None:
    '''Display a custom error message in situations where a regular error message cannot be sent'''
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


class OpInfo: # Mix-in class
    bl_options = {'REGISTER', 'UNDO'}


################################################################################################################
# OPERATORS
################################################################################################################


### GENERIC OPS ###

class SCRSHOT_OT_open_folder(OpInfo, Operator):
    """Opens up the File Explorer to the designated folder location"""
    bl_idname = "scrshot.open_folder"
    bl_label = "Open Folder"

    def execute(self, context):
        try:
            bpy.ops.wm.path_open(filepath = bpy.path.abspath(context.scene.screenshot_saver.export_path))
        except RuntimeError:
            self.report({'ERROR'}, "No valid file path set")
        return{'FINISHED'}


### RENDER OPS ###

class SCRSHOT_OT_render_screenshots(OpInfo, Operator):
    """The core operator for taking and rendering screenshots"""
    bl_idname = "scrshot.render_screenshots"
    bl_label = "Render Screenshots"

    render_type: bpy.props.EnumProperty(
        items=(
            ('single', "Single", ""),
            ('enabled', "All Enabled", "")
        ),
        default='enabled',
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        return (
            poll_active_screenshot_item(context) 
            and os.path.exists(bpy.path.abspath(context.scene.screenshot_saver.export_path))
        )

    def get_space_data(self, context) -> None:
        '''Gets the active space data based on where the cursor is located and handles poor contexts'''
        if context.area.type != 'VIEW_3D':
            self.saved_area_type = context.area.type

            context.area.type = 'VIEW_3D'
        else:
            self.saved_area_type = None

        self.space_data = context.space_data

    def save_settings(self, context) -> None:
        '''Saves all to-be modified settings mostly recursively'''
        shading = self.space_data.shading
        overlay = self.space_data.overlay
        render = context.scene.render

        # Use dir() to save every entry in the UI
        #
        # This will end up saving a lot of unnecessary data, but is very
        # modular comparedto saving everything we need individually
        self.saved_settings = {}

        for data in (shading, render, render.image_settings):
            for attr in dir(data):
                if data not in self.saved_settings:
                    self.saved_settings[data] = {}

                self.saved_settings[data][attr] = getattr(data, attr)

        # Manual dict values (only for when we need to cherry pick one or two values from each "group")
        self.saved_settings[overlay] = {'show_overlays': overlay.show_overlays}
        self.saved_settings[context.scene] = {'camera': context.scene.camera}

    def load_saved_settings(self, context) -> None:
        '''A "refresh" method that returns all changed attributes to their original values mostly recursively'''
        # Original UI
        if self.saved_area_type is not None:
            context.area.type = self.saved_area_type

        # Original shading, overlay, file path, etc settings
        self.saved_settings_overflow = {}
        for key, values in self.saved_settings.items():
            for name, value in dict(values).items(): # dict() is unecessary but the syntax is missing otherwise
                try:
                    setattr(key, name, value)
                except AttributeError: # read_only attr
                    pass
                except TypeError: # This seems to only happen with color depth (bad context), keep debug log for future exceptions
                    log.debug(f'{name}: {value} had a TypeError, this should be normal.')

        # Original camera view
        if self.switch_cam:
            bpy.ops.view3d.view_camera()

    def load_user_sett(self, context, active_scrshot) -> None:
        '''Load per screenshot settings such as file pathing, resolution and render setups'''
        def handle_name_suffix(file_path) -> str:
            counter = 1
            new_file_path = file_path + '_{:04d}'.format(counter)

            while os.path.exists(new_file_path + '.' + context.scene.screenshot_saver.format_type):
                counter += 1
                new_file_path = file_path + '_{:04d}'.format(counter)

            return new_file_path

        scene = context.scene
        render = scene.render
        shading = self.space_data.shading

        if active_scrshot.use_subfolder:
            path_end = os.path.join(active_scrshot.subfolder_name, active_scrshot.name)
        else:
            path_end = active_scrshot.name

        file_path = handle_name_suffix(os.path.join(bpy.path.abspath(scene.screenshot_saver.export_path), path_end))
        render.filepath = file_path

        scene.camera = active_scrshot.camera_ob

        render.resolution_x = active_scrshot.cam_res_x
        render.resolution_y = active_scrshot.cam_res_y

        if active_scrshot.render_type == 'workbench':
            shading.type = 'SOLID'

            if not active_scrshot.use_defaults:
                shading.light = str(active_scrshot.lighting_type).upper()

                if active_scrshot.lighting_type == 'studio':
                    shading.use_world_space_lighting = active_scrshot.use_wsl
                    shading.studiolight_rotate_z = active_scrshot.studio_rotate_z

                shading.studio_light = active_scrshot.studio_light_name

                shading.show_backface_culling = active_scrshot.use_backface_culling
                shading.show_object_outline = active_scrshot.use_outline
                shading.show_cavity = active_scrshot.use_cavity
                shading.show_specular_highlight = active_scrshot.use_spec_lighting

                shading.cavity_type = 'BOTH'
                shading.cavity_ridge_factor = active_scrshot.cavity_ridge
                shading.cavity_valley_factor = active_scrshot.cavity_valley
                shading.curvature_ridge_factor = active_scrshot.curve_ridge
                shading.curvature_valley_factor = active_scrshot.curve_valley

                shading.object_outline_color = active_scrshot.outliner_color_value

                shading.color_type = str(active_scrshot.color_type).upper()
        else: # TODO EEVEE
            render.engine = 'BLENDER_EEVEE'
            shading.type = 'RENDERED'

    def load_misc_sett(self, context) -> None:
        '''Set a handful of render settings that are maintained across all screenshot renders'''
        scene = context.scene
        render = scene.render
        shading = self.space_data.shading
        image_settings = render.image_settings

        scene.display.viewport_aa = 'FXAA'

        self.space_data.overlay.show_overlays = False

        shading.use_dof = False
        shading.show_xray = False
        shading.show_shadows = False

        shading.use_scene_world = False
        shading.use_scene_lights = False

        image_settings.color_mode = 'RGB'
        scene.display_settings.display_device = 'sRGB'

        render.use_file_extension = True
        render.use_render_cache = False
        render.use_overwrite = True
        render.use_placeholder = False

        # TODO Does isolate toggle operator not work when taking screenshots?

        if context.space_data.region_3d.view_perspective != 'CAMERA':
            self.switch_cam = True
            bpy.ops.view3d.view_camera()
        else:
            self.switch_cam = False

        scrshot_saver = context.scene.screenshot_saver

        if scrshot_saver.format_type == 'png':
            image_settings.file_format = 'PNG'
            image_settings.color_depth = '16'
        elif scrshot_saver.format_type == 'jpeg':
            image_settings.file_format = 'JPEG'
        else: # EXR
            image_settings.file_format = 'OPEN_EXR'
            image_settings.color_depth = '16'

    def render_screenshot(self, context) -> int:
        '''A base for calling per screenshot setup methods and rendering each screenshot'''
        if self.render_type == 'enabled':
            scrshot_camera_coll = context.scene.scrshot_camera_coll

            # Begin looping through screenshots
            rendered_screenshots = [scrshot for scrshot in scrshot_camera_coll if scrshot.enabled]
            for scrshot in rendered_screenshots:
                # Load the user settings for this particular screenshot
                self.load_user_sett(context, active_scrshot=scrshot)

                # Use opengl renders for both workbench and eevee (speed trumps quality here)
                bpy.ops.render.opengl(write_still=True)

            return len(rendered_screenshots)
        else: # Single
            camera_index = context.scene.scrshot_camera_index
            active_scrshot = context.scene.scrshot_camera_coll[camera_index]

            self.load_user_sett(context, active_scrshot)

            bpy.ops.render.opengl(write_still=True)

            return 1

    def execute(self, context):
        # Start counting execution time
        start = time.time()

        self.get_space_data(context)

        # Save current shading settings
        self.save_settings(context)
        
        # Load misc/generic settings that will apply to all rendered screenshots
        self.load_misc_sett(context)

        # Prepare and render all screenshots
        render_count = self.render_screenshot(context)

        # Reload original shading settings
        self.load_saved_settings(context)

        # This is only scene when rendering manually, will get overwritten by standard saving message
        self.report({'INFO'}, f"{render_count} Screenshot(s) Rendered!")

        # End the timer
        end = time.time()
        execution_time = end - start
        log.debug(f'Render Finished! Execution Time: {execution_time}')
        return {'FINISHED'}


### OUTLINER OPS ###

class SCRSHOT_OT_add_screenshot_item(OpInfo, Operator):
    """Add a new screenshot item to the scene"""
    bl_idname = "scrshot.add_screenshot_item"
    bl_label = "Add Item"

    def create_coll_and_cam(self, context, active_scrshot_name):
        # Create a collection to service add-on cameras
        if not 'ScrSaver Cameras (do not touch)' in bpy.data.collections:
            new_coll = bpy.data.collections.new(name = "ScrSaver Cameras (do not touch)")
                
            context.scene.collection.children.link(new_coll)
        else:
            new_coll = bpy.data.collections.get('ScrSaver Cameras (do not touch)')

        # Get users camera position
        region = context.space_data.region_3d # This is the space the mouse is hovering over, fine for our needs but
                                              # a solution that needs to find the view_3d independant of space_data 
                                              # might need to track mouse position?

        view_matrix_inv = region.view_matrix.inverted() # Invert the 4x4 view matrix
        view_matrix_transl = view_matrix_inv.to_translation() # Get translation attribute of the 4x4 matrix
        view_matrix_rot = view_matrix_inv.to_euler() # Get rotation attribute of the 4x4 matrix

        # Reset in-camera view settings
        region.view_camera_zoom = 0
        region.view_camera_offset = (0, 0)

        # Create a new camera at the matrix position (users camera)
        new_cam_data = bpy.data.cameras.new(active_scrshot_name)
        new_camera_ob = bpy.data.objects.new(active_scrshot_name, new_cam_data)

        new_camera_ob.location = view_matrix_transl
        new_camera_ob.rotation_euler = view_matrix_rot
        new_camera_ob.screenshot_id = new_camera_ob.name
        new_cam_data.screenshot_id = new_cam_data.name
        new_cam_data.passepartout_alpha = .9
        new_cam_data.lens = context.space_data.lens
        new_cam_data.show_name = True

        new_coll.objects.link(new_camera_ob)

        context.scene.camera = new_camera_ob

        # Deselect all objects
        for ob in context.selected_objects:
            ob.select_set(False)

        context.view_layer.objects.active = new_camera_ob

        new_camera_ob.hide_select = False
        new_camera_ob.select_set(True)

        if region.view_perspective != 'CAMERA':
            bpy.ops.view3d.view_camera() # Override the context if method changes. Changing the view "manually" has issues
        return new_camera_ob

    def execute(self, context):
        scene = context.scene

        item = scene.scrshot_camera_coll.add()
        item.id = len(scene.scrshot_camera_coll) - 1
        item.cam_res_x = scene.render.resolution_x
        item.cam_res_y = scene.render.resolution_y

        idx_count = 1
        name_found = False
        while not name_found:
            if f'screenshot_{idx_count}' in scene.scrshot_camera_coll:
                idx_count += 1
            else:
                item.name = f"screenshot_{idx_count}"
                name_found = True

        item.subfolder_name = item.name

        ## Create & link a new camera to the new item
        camera_ob = self.create_coll_and_cam(context, active_scrshot_name=item.name)
        item.camera_ob = camera_ob

        scene.scrshot_camera_index = len(scene.scrshot_camera_coll) - 1
        return {'FINISHED'}


class SCRSHOT_OT_delete_screenshot_item(OpInfo, Operator):
    """Delete the active screenshot item from the scene"""
    bl_idname = "scrshot.delete_screenshot_item"
    bl_label = "Delete Item"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return poll_active_screenshot_item(context)

    def execute(self, context):
        scene = context.scene

        try: # Might not be necessary?
            camera_index = scene.scrshot_camera_index
            active_scrshot = scene.scrshot_camera_coll[camera_index]

            for ob in bpy.data.objects:
                if ob.screenshot_id == active_scrshot.name:
                    bpy.data.objects.remove(ob)

            for cam in bpy.data.cameras:
                if cam.screenshot_id == active_scrshot.name:
                    bpy.data.cameras.remove(cam)

            scene.scrshot_camera_coll.remove(camera_index)
            
            # Move objects contained inside the bake group collection to the root collection level and delete the collection
            if not len(scene.scrshot_camera_coll) and 'ScrSaver Cameras (do not touch)' in bpy.data.collections:
                bake_group_coll = bpy.data.collections.get("ScrSaver Cameras (do not touch)")
                if bake_group_coll is not None:
                    for ob in bake_group_coll.all_objects:
                        # Move object to the master collection
                        context.scene.collection.objects.link(ob)
                        
                        # Remove the objects from the original collection
                        ob.users_collection[0].objects.unlink(ob)

                    bpy.data.collections.remove(bake_group_coll)
        except IndexError:
            pass

        # If the current index is larger than the array set the active index to the lowest item in the list
        if (camera_index + 1) > len(scene.scrshot_camera_coll):
            scene.scrshot_camera_index = camera_index - 1
        return {'FINISHED'}


class SCRSHOT_OT_select_and_preview(OpInfo, Operator):
    """Select the camera item and preview"""
    bl_idname = "scrshot.select_and_preview"
    bl_label = "Select and Preview"
    bl_options = {'INTERNAL'}

    # TODO Maybe autoselect the screenshot item as well?

    scrshot_name: bpy.props.StringProperty()
    preview_cam: bpy.props.BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return poll_active_screenshot_item(context)

    def execute(self, context):
        scene = context.scene

        active_scrshot = scene.scrshot_camera_coll[self.scrshot_name]
        camera_ob = active_scrshot.camera_ob

        if self.preview_cam:
            scene.camera = camera_ob

            scene.render.resolution_x = active_scrshot.cam_res_x
            scene.render.resolution_y = active_scrshot.cam_res_y

            if context.space_data.region_3d.view_perspective != 'CAMERA':
                bpy.ops.view3d.view_camera()

        # Deselect all objects
        for ob in context.selected_objects:
            ob.select_set(False)
        
        context.view_layer.objects.active = camera_ob

        camera_ob.hide_select = False
        camera_ob.select_set(True)
        return {'FINISHED'}


class SCRSHOT_OT_copy_screenshot_settings(OpInfo, Operator):
    """Copy the active screenshots settings, to be pasted on other screenshots"""
    bl_idname = "scrshot.copy_screenshot_settings"
    bl_label = "Copy Screenshot Settings"

    @classmethod
    def poll(cls, context):
        return poll_active_screenshot_item(context)

    def execute(self, context):
        active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]

        # Create simplified dictionary for use in JSON
        scrshot_copy_vars = {}
        for key in active_scrshot.__annotations__.keys():
            key_attr = getattr(active_scrshot, key)

            # Ignore values that are for specific datablocks, JSON won't 
            # be able to parse the objects and we don't need them
            # 
            # Also ignore certain internal keys manually, not a great
            # method but the list shouldn't get bigger
            if isinstance(key_attr, (str, int, bool)) and key not in {'id', 'name', 'saved_name', 'enabled', 'subfolder_name'}:
                scrshot_copy_vars[str(key)] = key_attr

        # Get other generic attributes attached to the camera data
        # ob_data_ is a prefix for figuring out data to update
        scrshot_copy_vars['ob_data_passepartout_alpha'] = active_scrshot.camera_ob.data.passepartout_alpha
        scrshot_copy_vars['ob_data_display_size'] = active_scrshot.camera_ob.data.display_size
        scrshot_copy_vars['ob_data_angle'] = active_scrshot.camera_ob.data.angle

        # Add-on root path & temp file path
        addon_path = os.path.dirname(__file__)
        temps_path = os.path.join(addon_path, "temp")

        if not os.path.exists(temps_path):
            os.mkdir(temps_path)

        # Serializing
        scrshot_copy_json = json.dumps(scrshot_copy_vars, indent=2)

        # Writing to file
        with open(os.path.join(temps_path, "latest_screenshot_copy.json"), "w") as outfile:
            outfile.write(scrshot_copy_json)

        self.report({'INFO'}, "Camera Settings Copied!")
        return {'FINISHED'}


class SCRSHOT_OT_paste_screenshot_settings(OpInfo, Operator):
    """Paste the latest copied screenshots settings onto the active screenshot item"""
    bl_idname = "scrshot.paste_screenshot_settings"
    bl_label = "Paste Screenshot Settings"

    @classmethod
    def poll(cls, context):
        addon_path = os.path.dirname(__file__)
        screenshot_copy_path = os.path.join(addon_path, "temp\\latest_screenshot_copy.json")

        return poll_active_screenshot_item(context) and os.path.isfile(screenshot_copy_path)

    def execute(self, context):
        # Add-on root path & temp file path
        addon_path = os.path.dirname(__file__)
        screenshot_copy_path = os.path.join(addon_path, "temp\\latest_screenshot_copy.json")

        # Opening JSON file
        scrshot_copy_json = open(screenshot_copy_path)
        
        # returns JSON object as a dictionary
        scrshot_copy_data = json.load(scrshot_copy_json)
        
        # Iterating through the json list
        active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]
        for key, value in scrshot_copy_data.items():
            log.debug(f'{key} -> {value} {type(value)}')

            if key.startswith('ob_data_'):
                setattr(active_scrshot.camera_ob.data, key[8:], value)
            else:
                setattr(active_scrshot, key, value)

        scrshot_copy_json.close()

        self.report({'INFO'}, "Camera Settings Pasted!")
        return {'FINISHED'}


### OUTLINER SETTINGS OPS ###


class SCRSHOT_OT_copy_viewport_shade_settings(OpInfo, Operator): # TODO
    """Get the viewport shading settings of the actively selected viewport"""
    bl_idname = "scrshot.copy_viewport_shade_settings"
    bl_label = "Clone 3D Viewport Shading"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return poll_active_screenshot_item(context)

    def execute(self, context):
        shading = context.space_data.shading

        active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]

        # Apply all active shading settings
        active_scrshot.lighting_type = str(shading.light).lower()
        active_scrshot.color_type = str(shading.color_type).lower()

        active_scrshot.studio_rotate_z = shading.studiolight_rotate_z
        active_scrshot.use_wsl = shading.use_world_space_lighting

        active_scrshot.use_backface_culling = shading.show_backface_culling
        active_scrshot.use_cavity = shading.show_cavity
        active_scrshot.use_outline = shading.show_object_outline
        active_scrshot.use_spec_lighting = shading.show_specular_highlight

        active_scrshot.cavity_ridge = shading.cavity_ridge_factor
        active_scrshot.cavity_valley = shading.cavity_valley_factor
        active_scrshot.curve_ridge = shading.curvature_ridge_factor
        active_scrshot.curve_valley = shading.curvature_valley_factor

        active_scrshot.outliner_color_value = shading.object_outline_color

        active_scrshot.single_color_value = shading.single_color

        # Apply all studio lights individually
        saved_lighting_type = active_scrshot.lighting_type

        if active_scrshot.render_type == 'workbench':
            active_scrshot.lighting_type = 'studio'
            bpy.ops.scrshot.get_studio_light()

            active_scrshot.lighting_type = 'matcap'
            bpy.ops.scrshot.get_studio_light()
        else: # TODO EEVEE
            pass

        active_scrshot.lighting_type = saved_lighting_type

        self.report({'INFO'}, "Copied shading settings!")
        return {'FINISHED'}


class SCRSHOT_OT_get_studio_light(OpInfo, Operator):
    """Get the active viewports studio light. Ideally in the future you will be able to select a studio light from here directly"""
    bl_idname = "scrshot.get_studio_light"
    bl_label = "Get Studio Light"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return poll_active_screenshot_item(context)

    def execute(self, context):
        shading = context.space_data.shading

        saved_shading_type = shading.type
        saved_shading_light = shading.light

        active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]
        if active_scrshot.render_type == 'workbench':
            shading.type = 'SOLID'

            if active_scrshot.lighting_type == 'studio':
                shading.light = 'STUDIO'
                active_scrshot.studio_light_name = shading.studio_light

            elif active_scrshot.lighting_type == 'matcap':
                shading.light = 'MATCAP'
                active_scrshot.matcap_light_name = shading.studio_light
        else: # TODO EEVEE
            shading.type = 'MATERIAL'

            active_scrshot.eevee_light_name = shading.studio_light

        shading.type = saved_shading_type
        shading.light = saved_shading_light

        self.report({'INFO'}, "Copied studio light name!")
        return {'FINISHED'}


class SCRSHOT_OT_sample_studio_light_rotation(OpInfo, Operator):
    """Move an object with the mouse, example"""
    bl_idname = "scrshot.sample_studio_light_rotation"
    bl_label = "Sample Light Rotation"
    bl_options = {'GRAB_CURSOR', 'BLOCKING'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            offset = event.mouse_x - (event.mouse_prev_x)
            self.shading.studiolight_rotate_z += offset * 0.0075

            if self.shading.studiolight_rotate_z <= -3.141592:
                self.shading.studiolight_rotate_z = 3.141592
            elif self.shading.studiolight_rotate_z >= 3.141592:
                self.shading.studiolight_rotate_z = -3.141592

            self.active_scrshot.studio_rotate_z = self.shading.studiolight_rotate_z
            studiolight_rotate_z_degree = self.shading.studiolight_rotate_z * 180 / 3.14159265359

            context.area.header_text_set(f"Light Rotation Sample: {round(studiolight_rotate_z_degree)}")

        elif event.type == 'LEFTMOUSE':
            context.window.cursor_set('DEFAULT')
            context.area.header_text_set(None)

            self.execute(context)
            self.report({'INFO'}, "Light Rotation Sampled!")
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            context.window.cursor_set('DEFAULT')
            context.area.header_text_set(None)

            self.active_scrshot.studio_rotate_z = self.initial_item_rotate_z

            self.execute(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def execute(self, context):
        self.shading.type = self.initial_type
        self.shading.light = self.initial_light
        self.shading.use_world_space_lighting = self.initial_use_wsl
        self.shading.studiolight_rotate_z = self.initial_studio_rot_z
        return {'FINISHED'}

    def invoke(self, context, event):
        space_data = context.space_data
        self.shading = space_data.shading

        self.initial_type = self.shading.type
        self.initial_light = self.shading.light
        self.initial_use_wsl = self.shading.use_world_space_lighting
        self.initial_studio_rot_z = self.shading.studiolight_rotate_z

        self.shading.type = 'SOLID'
        self.shading.light = 'STUDIO'
        self.shading.use_world_space_lighting = True

        self.initial_mouse_x = event.mouse_x

        camera_index = context.scene.scrshot_camera_index
        self.active_scrshot = context.scene.scrshot_camera_coll[camera_index]

        self.initial_item_rotate_z = self.active_scrshot.studio_rotate_z

        context.window.cursor_set('MOVE_X')
        context.area.header_text_set(f"Light Rotation Sample: {round(self.initial_studio_rot_z)}")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


################################################################################################################
# REGISTRATION
################################################################################################################


classes = (
    SCRSHOT_OT_open_folder,
    SCRSHOT_OT_add_screenshot_item,
    SCRSHOT_OT_delete_screenshot_item,
    SCRSHOT_OT_render_screenshots,
    SCRSHOT_OT_select_and_preview,
    SCRSHOT_OT_copy_screenshot_settings,
    SCRSHOT_OT_paste_screenshot_settings,
    SCRSHOT_OT_copy_viewport_shade_settings,
    SCRSHOT_OT_get_studio_light,
    SCRSHOT_OT_sample_studio_light_rotation
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


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
