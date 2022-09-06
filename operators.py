import bpy, os, json, time, subprocess
from bpy.types import Operator
from .pillow import Image
from .exr_parse.parse_metadata import read_exr_header
from pathlib import Path

import logging
log = logging.getLogger(__name__)
if "PYDEVD_USE_FRAME_EVAL" in os.environ: # If using the Python Dev add-on for blender, set config to debug... works sometimes
    logging.basicConfig(level='DEBUG')


################################################################################################################
# FUNCTIONS & MIX-IN
################################################################################################################


def active_screenshot_exists() -> bool:
    '''Poll for the active screenshot item'''
    scene = bpy.context.scene

    if not len(scene.scrshot_camera_coll):
        return False
    elif (scene.scrshot_camera_index + 1) > len(scene.scrshot_camera_coll):
        return False
    return True


def export_path_exists() -> bool:
    '''Poll for if the export path exists'''
    export_path = bpy.context.scene.screenshot_saver.export_path

    if not os.path.exists(bpy.path.abspath(export_path)) and export_path != '//screenshots':
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
    bl_label = "Render All Screenshots"

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
        return active_screenshot_exists() and export_path_exists()

    def get_set_hidden_objects(self, context) -> dict:
        '''Generate a dict of all objects and collections that will be hidden for the viewport render and hide them'''
        vlayer = context.view_layer
        
        def layer_traverse(coll, layer=vlayer.layer_collection) -> bpy.types.LayerCollection:
            '''Traverse all layer collections to find the matching one'''
            if layer.collection == coll:
                yield {'layer_ob': layer, 'layer_vis': layer.hide_viewport}

            for child in layer.children:
                yield from layer_traverse(coll, child)

        ob_hide_states = {ob:{
                    'render_vis': ob.hide_render,
                    'viewport_vis': ob.hide_viewport,
                    'layer_vis': ob.hide_get()
                }
            for ob in vlayer.objects
        }
        coll_hide_states = {coll:{
                    'render_vis': coll.hide_render,
                    'viewport_vis': coll.hide_viewport,
                    'layer': next(layer_traverse(coll))
                }
            for coll in bpy.data.collections
        }

        # Leave local view if currently used
        self.local_view = False
        for area in context.screen.areas:
            if area.type == 'VIEW_3D' and area.spaces[0].local_view:
                for region in area.regions:
                    if region.type == 'WINDOW':
                        self.local_view = True
                        self.report_string = 'Local View exited to render'

                        override = {'area': area, 'region': region}
                        bpy.ops.view3d.localview(override)

        for ob, vis in ob_hide_states.items():
            if vis['render_vis']:
                ob.hide_viewport = True
            else:
                ob.hide_viewport = False
                ob.hide_set(False)

        for coll, vis in coll_hide_states.items():
            if vis['render_vis']:
                coll.hide_viewport = True
            else:
                coll.hide_viewport = False
                vis['layer']['layer_ob'].hide_viewport = False

        return ob_hide_states, coll_hide_states

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
        scene = context.scene

        # Use dir() to save every entry in the UI
        #
        # This will end up saving a lot of unnecessary data, but is very
        # modular compared to saving everything we need individually
        self.saved_settings = {}

        for data in (shading, scene.render, scene.render.image_settings, scene.display, scene.eevee):
            for attr in dir(data):
                if data not in self.saved_settings:
                    self.saved_settings[data] = {}

                self.saved_settings[data][attr] = getattr(data, attr)

        # Manual dict values (only for when we need to cherry pick one or two values from each "group")
        self.saved_settings[overlay] = {'show_overlays': overlay.show_overlays}
        #self.saved_settings[scene] = {'camera': scene.camera} # not working, do manually
        self.saved_settings[scene] = {'frame_current': scene.frame_current}

        # Manual camera sync
        self.saved_camera = scene.camera


    def load_saved_settings(self, context, ob_hide_states, coll_hide_states) -> None:
        '''A "refresh" method that returns all changed attributes to their original values mostly recursively'''
        # Original UI
        if self.saved_area_type is not None:
            context.area.type = self.saved_area_type

        # Original shading, overlay, file path, etc settings
        self.saved_settings_overflow = {}
        for key, values in self.saved_settings.items():
            for name, value in dict(values).items(): # dict() is unecessary but syntax is missing otherwise
                try:
                    setattr(key, name, value)
                except AttributeError: # read_only attr
                    pass
                except TypeError: # This seems to only happen with color depth (bad context), keep debug log for future exceptions
                    log.debug(f'{name}: {value} had a TypeError, this should be normal.')

        # Manual camera sync
        context.scene.camera = self.saved_camera

        # Unhide objects/collections hidden in the viewport
        for ob, vis in ob_hide_states.items():
            ob.hide_viewport = vis['viewport_vis']
            ob.hide_set(vis['layer_vis'])

        for coll, vis in coll_hide_states.items():
            coll.hide_viewport = vis['viewport_vis']
            vis['layer']['layer_ob'].hide_viewport = vis['layer']['layer_vis']

        # Original camera view
        if self.switch_cam:
            bpy.ops.view3d.view_camera()

    def handle_user_settings(self, context, active_scrshot) -> None:
        '''Load per screenshot settings such as file pathing, resolution and render setups'''
        def handle_path_formatting(file_path: str) -> str:
            # Extend folder path if using subfolders
            if active_scrshot.use_subfolder:
                path_end = Path(active_scrshot.subfolder_name, active_scrshot.name)
            else:
                path_end = active_scrshot.name
            
            file_path = Path(file_path, path_end)
            file_path.parent.mkdir(exist_ok=True)

            scene.frame_current = active_scrshot.render_frame

            # Get the file extension type
            if scene.screenshot_saver.format_type == 'open_exr':
                file_format = 'exr'
            else: # PNG, JPEG
                file_format = scene.screenshot_saver.format_type

            file_numbers = []
            for filename in os.listdir(file_path.parent):
                try:
                    if Path(file_path.parent, filename).is_file():
                        file_numbers.append(int(filename.split('_')[-1].split(f'.{file_format}')[0]))
                except ValueError:
                    pass

            # Set the counter & format the path end with 4 digit suffix
            if not len(file_numbers):
                counter = 1
            else:
                counter = max(file_numbers)+1

            file_path = str(file_path) + '_{:04d}'.format(counter)

            return f'{file_path}.{file_format}'

        scene = context.scene
        render = scene.render
        shading = self.space_data.shading

        render.filepath = handle_path_formatting(bpy.path.abspath(scene.screenshot_saver.export_path))

        scene.camera = active_scrshot.camera_ob

        render.resolution_x = active_scrshot.cam_res_x
        render.resolution_y = active_scrshot.cam_res_y

        if active_scrshot.render_type == 'workbench':
            shading.type = 'SOLID'

            if active_scrshot.use_defaults:
                return

            shading.light = str(active_scrshot.lighting_type).upper()

            if active_scrshot.lighting_type == 'studio':
                shading.use_world_space_lighting = active_scrshot.use_wsl
                shading.studiolight_rotate_z = active_scrshot.studio_rotate_z
                shading.studio_light = active_scrshot.studio_light_name
            elif active_scrshot.lighting_type == 'matcap':
                shading.studio_light = active_scrshot.matcap_light_name

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
        else: # EEVEE
            render.engine = 'BLENDER_EEVEE'
            shading.type = 'MATERIAL'

            if active_scrshot.use_defaults:
                return

            shading.use_scene_lights = active_scrshot.use_scene_lights
            shading.use_scene_world = active_scrshot.use_scene_world

            shading.studio_light = active_scrshot.eevee_light_name

            shading.use_studiolight_view_rotation = active_scrshot.eevee_use_rotate
            shading.studiolight_rotate_z = active_scrshot.studio_rotate_z
            shading.studiolight_intensity = active_scrshot.eevee_intensity
            shading.studiolight_background_alpha = active_scrshot.eevee_alpha
            shading.studiolight_background_blur = active_scrshot.eevee_blur

    def handle_misc_sett(self, context) -> None:
        '''Set a handful of render/scene settings that are maintained across all screenshot renders'''
        scene = context.scene
        render = scene.render
        shading = self.space_data.shading
        image_settings = render.image_settings

        scene.display.viewport_aa = 'FXAA'
        scene.eevee.taa_samples = 16

        self.space_data.overlay.show_overlays = False

        shading.use_dof = False
        shading.show_xray = False
        shading.show_shadows = False

        image_settings.color_mode = 'RGB'
        scene.display_settings.display_device = 'sRGB'

        render.use_file_extension = True
        render.use_render_cache = False
        render.use_overwrite = True
        render.use_placeholder = False

        if context.space_data.region_3d.view_perspective != 'CAMERA':
            self.switch_cam = True
            bpy.ops.view3d.view_camera()
        else:
            self.switch_cam = False

        image_settings.file_format = str(scene.screenshot_saver.format_type).upper()
        if scene.screenshot_saver.format_type != 'jpeg':
            image_settings.color_depth = '16'

    def render_screenshot(self, context) -> int:
        '''A base for calling per screenshot setup methods and rendering each screenshot'''
        if self.render_type == 'enabled':
            # Begin looping through screenshots
            rendered_screenshots = [scrshot for scrshot in context.scene.scrshot_camera_coll if scrshot.enabled]
            for scrshot in rendered_screenshots:
                # Load the user settings for this particular screenshot
                self.handle_user_settings(context, active_scrshot=scrshot)

                # Use opengl renders for both workbench and eevee (speed trumps quality here)
                bpy.ops.render.opengl(write_still=True)
            return len(rendered_screenshots)
        else: # Single
            active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]

            self.handle_user_settings(context, active_scrshot)

            bpy.ops.render.opengl(write_still=True)
            return 1

    def execute(self, context):
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Please save a blender file before recording screenshots")
            return {'CANCELLED'}

        # Start counting execution time
        start = time.time()

        self.report_string = ''

        screenshots_path = Path(bpy.path.abspath("//screenshots"))
        screenshots_path.mkdir(exist_ok=True)

        self.get_space_data(context)

        ob_hide_states, coll_hide_states = self.get_set_hidden_objects(context)

        # Save current shading settings
        self.save_settings(context)
        
        # Load misc/generic settings that will apply to all rendered screenshots
        self.handle_misc_sett(context)

        # Prepare and render all screenshots
        render_count = self.render_screenshot(context)

        # Reload original shading/render vis settings
        self.load_saved_settings(context, ob_hide_states, coll_hide_states)

        # This is only seen when rendering manually, will get overwritten by standard saving message
        if self.report_string:
            self.report({'WARNING'}, f"{render_count} Screenshot(s) Rendered!    INFO: {self.report_string}")
        else:
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
        new_camera_ob.lock_scale[0] = new_camera_ob.lock_scale[1] = new_camera_ob.lock_scale[2] = True
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

        idx_count = 0
        name_found = False
        while not name_found:
            idx_count += 1

            if f'screenshot_{idx_count}' not in scene.scrshot_camera_coll:
                item.name = f"screenshot_{idx_count}"
                name_found = True

        item.subfolder_name = item.name

        # Create & link a new camera to the new item
        camera_ob = self.create_coll_and_cam(context, active_scrshot_name=item.name)
        item.camera_ob = camera_ob

        scene.scrshot_camera_index = len(scene.scrshot_camera_coll) - 1
        return {'FINISHED'}


class SCRSHOT_OT_delete_screenshot_item(OpInfo, Operator):
    """Delete the active screenshot item from the scene"""
    bl_idname = "scrshot.delete_screenshot_item"
    bl_label = "Delete Item"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        scene = context.scene

        try: # TODO Might not be necessary?
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

    scrshot_name: bpy.props.StringProperty()
    preview_cam: bpy.props.BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return active_screenshot_exists()

    def execute(self, context):
        scene = context.scene

        active_scrshot = scene.scrshot_camera_coll[self.scrshot_name]
        camera_ob = active_scrshot.camera_ob

        try:
            context.view_layer.objects.active = camera_ob
        except RuntimeError:
            self.report({'ERROR'}, "Camera could not be found in the current Viewlayer. Have you disabled it?")
            return {'CANCELLED'}

        if self.preview_cam:
            scene.camera = camera_ob

            scene.render.resolution_x = active_scrshot.cam_res_x
            scene.render.resolution_y = active_scrshot.cam_res_y

            if context.space_data.region_3d.view_perspective != 'CAMERA':
                bpy.ops.view3d.view_camera()

        if (len(scene.scrshot_camera_coll)) > active_scrshot.id:
            scene.scrshot_camera_index = active_scrshot.id

        for ob in context.selected_objects:
            ob.select_set(False)

        camera_ob.hide_select = False
        camera_ob.select_set(True)
        return {'FINISHED'}


class SCRSHOT_OT_copy_screenshot_settings(OpInfo, Operator):
    """Copy the active screenshots settings, to be pasted on other screenshots"""
    bl_idname = "scrshot.copy_screenshot_settings"
    bl_label = "Copy Screenshot Settings"
    bl_options = {'INTERNAL'}

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

        temps_path = Path(addon_path, "temp")
        temps_path.mkdir(exist_ok=True)

        # Serializing
        scrshot_copy_json = json.dumps(scrshot_copy_vars, indent=2)

        # Writing to file
        with open(Path(temps_path, "latest_screenshot_copy.json"), "w") as outfile:
            outfile.write(scrshot_copy_json)

        self.report({'INFO'}, "Camera Settings Copied!")
        return {'FINISHED'}


class SCRSHOT_OT_paste_screenshot_settings(OpInfo, Operator):
    """Paste the latest copied screenshots settings onto the active screenshot item"""
    bl_idname = "scrshot.paste_screenshot_settings"
    bl_label = "Paste Screenshot Settings"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # Add-on root path & temp file path
        addon_path = os.path.dirname(__file__)
        screenshot_copy_path = os.path.join(addon_path, "temp\\latest_screenshot_copy.json")
        if not os.path.isfile(screenshot_copy_path):
            self.report({'ERROR'}, "You haven't copied anything yet!")
            return {'FINISHED'}

        with open(screenshot_copy_path) as scrshot_copy_json:
            # Return JSON object as a dictionary
            scrshot_copy_data = json.load(scrshot_copy_json)
            
            # Iterate through the json list
            active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]
            for key, value in scrshot_copy_data.items():
                log.debug(f'{key} -> {value} {type(value)}')

                if key.startswith('ob_data_'):
                    setattr(active_scrshot.camera_ob.data, key[8:], value)
                else:
                    setattr(active_scrshot, key, value)

        self.report({'INFO'}, "Camera Settings Pasted!")
        return {'FINISHED'}


### OUTLINER SETTINGS OPS ###


class SCRSHOT_OT_copy_viewport_shade_settings(OpInfo, Operator):
    """Get the viewport shading settings of the actively selected viewport"""
    bl_idname = "scrshot.copy_viewport_shade_settings"
    bl_label = "Clone 3D Viewport Shading"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return active_screenshot_exists()

    def execute(self, context):
        shading = context.space_data.shading
        active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]

        saved_shading_type = shading.type

        if active_scrshot.render_type == 'workbench':
            shading.type = 'SOLID'

            active_scrshot.lighting_type = str(shading.light).lower()
            active_scrshot.color_type = str(shading.color_type).lower()

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

            saved_lighting_type = active_scrshot.lighting_type

            active_scrshot.lighting_type = 'studio'
            bpy.ops.scrshot.get_studio_light(light_type = 'workbench')

            active_scrshot.lighting_type = 'matcap'
            bpy.ops.scrshot.get_studio_light(light_type = 'workbench')
 
            active_scrshot.lighting_type = saved_lighting_type
            
        else: # EEVEE
            shading.type = 'MATERIAL'

            active_scrshot.eevee_use_rotate = shading.use_studiolight_view_rotation
            active_scrshot.eevee_intensity = shading.studiolight_intensity
            active_scrshot.eevee_alpha = shading.studiolight_background_alpha
            active_scrshot.eevee_blur = shading.studiolight_background_blur

            active_scrshot.use_scene_lights = shading.use_scene_lights
            active_scrshot.use_scene_world = shading.use_scene_world

            bpy.ops.scrshot.get_studio_light(light_type = 'eevee')

        active_scrshot.studio_rotate_z = shading.studiolight_rotate_z

        shading.type = saved_shading_type

        self.report({'INFO'}, "Copied shading settings!")
        return {'FINISHED'}


class SCRSHOT_OT_get_studio_light(OpInfo, Operator):
    """Get the active viewports studio light. Ideally in the future you will be able to select a studio light from here directly"""
    bl_idname = "scrshot.get_studio_light"
    bl_label = "Get Studio Light"
    bl_options = {'INTERNAL'}

    light_type: bpy.props.EnumProperty(
        items=(
            ('workbench', "Workbench", ""),
            ('eevee', "EEVEE", "")
        ),
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        return active_screenshot_exists()

    def execute(self, context):
        shading = context.space_data.shading

        saved_shading_type = shading.type
        saved_shading_light = shading.light

        active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]

        if self.light_type == 'workbench':
            shading.type = 'SOLID'

            if active_scrshot.lighting_type == 'studio':
                shading.light = 'STUDIO'
                active_scrshot.studio_light_name = shading.studio_light

            elif active_scrshot.lighting_type == 'matcap':
                shading.light = 'MATCAP'
                active_scrshot.matcap_light_name = shading.studio_light
        else: # EEVEE
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
    bl_options = {'GRAB_CURSOR', 'BLOCKING', 'INTERNAL'}

    light_type: bpy.props.EnumProperty(
        items=(
            ('workbench', "Workbench", ""),
            ('eevee', "EEVEE", "")
        ),
        options={'HIDDEN'}
    )

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            offset = event.mouse_x - event.mouse_prev_x
            self.shading.studiolight_rotate_z += offset * .0075

            if self.shading.studiolight_rotate_z <= -3.141592:
                self.shading.studiolight_rotate_z = 3.141592
            elif self.shading.studiolight_rotate_z >= 3.141592:
                self.shading.studiolight_rotate_z = -3.141592
            
            self.active_scrshot.studio_rotate_z = self.shading.studiolight_rotate_z

            studiolight_rotate_z_degree = self.shading.studiolight_rotate_z * 180 / 3.14159265359

            context.area.header_text_set(f"Light Rotation Sample: {round(studiolight_rotate_z_degree)}")

        if event.type == 'LEFTMOUSE':
            context.window.cursor_set('DEFAULT')
            context.area.header_text_set(None)

            self.execute(context)
            self.report({'INFO'}, "Light Rotation Sampled!")
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            context.window.cursor_set('DEFAULT')
            context.area.header_text_set(None)

            self.active_scrshot.studio_rotate_z = self.saved_item_rotate_z

            self.execute(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def execute(self, context):
        self.shading.type = self.saved_type
        self.shading.light = self.saved_light
        self.shading.use_world_space_lighting = self.saved_use_wsl
        self.shading.studiolight_rotate_z = self.saved_studiolight_rot_z

        self.shading.use_scene_world = self.saved_use_scene_world
        self.shading.use_studiolight_view_rotation = self.saved_use_studiolight_view_rotation
        return {'FINISHED'}

    def invoke(self, context, event):
        self.shading = context.space_data.shading

        self.active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]

        self.saved_type = self.shading.type
        self.saved_light = self.shading.light
        self.saved_use_wsl = self.shading.use_world_space_lighting

        self.saved_studiolight_rot_z = self.shading.studiolight_rotate_z

        self.saved_use_scene_world = self.shading.use_scene_world
        self.saved_use_studiolight_view_rotation = self.shading.use_studiolight_view_rotation

        self.saved_item_rotate_z = self.active_scrshot.studio_rotate_z

        if self.light_type == 'workbench':
            self.shading.type = 'SOLID'
            self.shading.light = 'STUDIO'
            self.shading.use_world_space_lighting = True
        else: # EEVEE
            self.shading.type = 'MATERIAL'
            self.shading.use_scene_world = False
            self.shading.use_studiolight_view_rotation = True

        if self.active_scrshot.studio_rotate_z != 0:
            self.shading.studiolight_rotate_z = self.active_scrshot.studio_rotate_z
        else:
            self.active_scrshot.studio_rotate_z = self.shading.studiolight_rotate_z

        context.window.cursor_set('MOVE_X')
        context.area.header_text_set(f"Light Rotation Sample: {round(self.active_scrshot.studio_rotate_z)}")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class SCRSHOT_OT_generate_mp4(OpInfo, Operator):
    """Generate an MP4 or GIF of the selected active screenshot"""
    bl_idname = "scrshot.generate_mp4"
    bl_label = "Generate MP4/GIF"

    @classmethod
    def poll(cls, context):
        return active_screenshot_exists() and export_path_exists()

    def generate_palette(self, concat_file_path) -> str:
        '''Generate a color palette from a given image sequence'''
        palette_file_path = Path(Path(os.path.abspath(__file__)).parent, "temp", "palette.png")

        # Create args
        call_args = [
            f'{Path(Path(os.path.abspath(__file__)).parent, "ffmpeg", "bin", "ffmpeg.exe")}',
            '-y',
            '-f', 'concat', '-safe', '0',
            '-i', f'{concat_file_path}',
            '-vf', 'palettegen=reserve_transparent=1:transparency_color=000000:stats_mode=full',
            f'{palette_file_path}'
        ]

        if bpy.context.scene.screenshot_saver.format_type == 'open_exr':
            call_args.insert(2, '-apply_trc')
            call_args.insert(3, 'iec61966_2_1')

        subprocess.call(call_args)
        return palette_file_path

    def generate_text_file(self, input_path, file_format) -> str:
        '''Generate a text file that outlines the image sequences order and length'''
        render_files = []
        for filename in sorted(os.listdir(input_path.parent)):
            if filename.startswith(input_path.stem + '_') and filename.endswith(file_format):
                render_files.append(filename)

        temp_path = Path(Path(os.path.abspath(__file__)).parent, "temp")
        temp_path.mkdir(exist_ok=True)
        concat_file_path = Path(temp_path, 'concat.txt')
        with open(concat_file_path, 'w') as f:
            for idx, file_path in enumerate(render_files):
                if idx == 0: # If start repeat has been set, add the first iterable in render_files to the txt file x amount of times
                    for _ in range(bpy.context.scene.screenshot_saver.mp4_start_repeat_count):
                        f.write(f"file '{Path(input_path.parent, file_path)}'\nduration 1\n")

                f.write(f"file '{Path(input_path.parent, file_path)}'\nduration 1\n") # Add duration to get rid of warnings

            # If end repeat has been set, add the final iterable in render_files to the txt file x amount of times
            for _ in range(bpy.context.scene.screenshot_saver.mp4_end_repeat_count):
                f.write(f"file '{Path(input_path.parent, file_path)}'\nduration 1\n")
        return concat_file_path

    def handle_path_formatting_mp4(self, input_path) -> Path:
        '''Handle output file formatting'''
        scrshot_saver = bpy.context.scene.screenshot_saver

        file_numbers = []
        for filename in os.listdir(input_path.parent):
            try:
                if Path(input_path.parent, filename).is_file():
                    file_numbers.append(int(filename.split('_')[-1].split(f'.{scrshot_saver.mp4_format_type}')[0]))
            except ValueError:
                pass

        # Set the counter & format the path end with 4 digit suffix
        if not len(file_numbers):
            counter = 1
        else:
            counter = max(file_numbers)+1

        file_path = str(input_path) + '_{:04d}'.format(counter)

        return Path(f'{file_path}.{scrshot_saver.mp4_format_type}')

    def execute(self, context):
        scrshot_saver = context.scene.screenshot_saver
        active_scrshot = context.scene.scrshot_camera_coll[context.scene.scrshot_camera_index]

        # Set input path
        if active_scrshot.use_subfolder:
            path_end = Path(active_scrshot.subfolder_name, active_scrshot.name)
        else:
            path_end = active_scrshot.name

        input_path = Path(bpy.path.abspath(scrshot_saver.export_path), path_end)

        # Verify directory and file existence
        if not input_path.parent.is_dir():
            self.report({'ERROR'}, 'The render directory does not exist')
            return{'CANCELLED'}

        # Get the file extension type
        file_format = 'exr' if scrshot_saver.format_type == 'open_exr' else scrshot_saver.format_type

        # Look for any files of the correct format
        files_list = [
                    Path(input_path.parent, file_name) for file_name in os.listdir(input_path.parent)
                    if Path(input_path.parent, file_name).is_file()
                    and os.path.join(input_path.parent, file_name).endswith(file_format)
                ]
        if not len(files_list):
            self.report({'ERROR'}, 'There are no files of the correct type in this directory')
            return{'CANCELLED'}

        # Calculate the end result resolutions, and catch anything with a resolution not divisible by 2
        bad_res = False
        if scrshot_saver.mp4_crop_type == 'none':
            if scrshot_saver.format_type == 'open_exr':
                for file in files_list:
                    exr = read_exr_header(str(file))

                    exr_width, exr_height  = int(exr['dataWindow']['xMax'])+1, int(exr['dataWindow']['yMax'])+1
                    if (exr_width % 2) or (exr_height % 2):
                        bad_res = True
                        break
            else: # PNG, JPEG
                for file in files_list:
                    img = Image.open(str(file))

                    width, height = img.size
                    if (width % 2) or (height % 2):
                        bad_res = True
                        break
        else: # Using crop
            if scrshot_saver.mp4_crop_type == 'to_resolution':
                if (scrshot_saver.mp4_crop_res_x % 2) or (scrshot_saver.mp4_crop_res_y % 2):
                    bad_res = True
            else: # from_border
                for file in files_list:
                    img = Image.open(str(file))

                    width, height = img.size
                    if ((width-scrshot_saver.mp4_crop_amt_width) % 2) or ((height-scrshot_saver.mp4_crop_amt_height) % 2):
                        bad_res = True
                        break

        if bad_res:
            self.report({'ERROR'}, 'An image with a resolution (or crop res) that is not divisible by 2 was found.\n\nConsider using the crop feature to encode.')
            return{'CANCELLED'}

        # Generate an ordered list of the frames to render
        concat_file_path = self.generate_text_file(input_path, file_format)

        # Handle file path formatting/versioning
        output_path = self.handle_path_formatting_mp4(input_path)

        # Get the path of the local ffmpeg lib
        ffmpeg_path = Path(Path(os.path.abspath(__file__)).parent, "ffmpeg", "bin", "ffmpeg.exe")

        # Get crop width + height
        if scrshot_saver.mp4_crop_type == 'from_border':
            crop_amt = f"crop=in_w-{scrshot_saver.mp4_crop_amt_width}:in_h-{scrshot_saver.mp4_crop_amt_height}"
        elif scrshot_saver.mp4_crop_type == 'to_resolution':
            crop_amt = f"crop={scrshot_saver.mp4_crop_res_x}:{scrshot_saver.mp4_crop_res_y}"
        else:
            crop_amt = "crop=in_w:in_h"

        # Get downscale amount
        scale_amt = f"scale=-1:ih/{scrshot_saver.mp4_res_downscale}"

        # Create args
        if scrshot_saver.mp4_format_type == 'mp4':
            call_args = [
                f'{ffmpeg_path}',
                '-y',
                '-f', 'concat', '-safe', '0',
                '-r', f'{scrshot_saver.mp4_framerate}',
                '-i', f'{concat_file_path}',
                '-filter_complex', f"[0:v]{crop_amt}[z];[z]{scale_amt}",
                "-c:v", 'libx264',
                '-preset', 'slow',
                '-crf', '20',
                '-pix_fmt', 'yuv420p',
                f'{output_path}'
            ]
        else: # GIF
            palette_file_path = self.generate_palette(concat_file_path)

            call_args = [
                f'{ffmpeg_path}',
                '-y',
                '-f', 'concat', '-safe', '0',
                '-r', f'{scrshot_saver.mp4_framerate}',
                '-i', f'{concat_file_path}',
                '-i', f'{palette_file_path}',
                '-filter_complex', f"[0:v]{crop_amt}[z];[z]{scale_amt}[z];[z][1:v]paletteuse",
                f'{output_path}'
            ]

        if scrshot_saver.format_type == 'open_exr':
            call_args.insert(2, '-apply_trc')
            call_args.insert(3, 'iec61966_2_1')

        try:
            subprocess.check_output(call_args)
        except subprocess.CalledProcessError:
            self.report({'ERROR'}, f"An error occured, and your {scrshot_saver.mp4_format_type.upper()} was not encoded properly.\n\nPlease send a screenshot of your console to ethan.simon.3d@gmail.com")
            return {'CANCELLED'}

        if output_path.is_file():
            self.report({'INFO'}, f"{scrshot_saver.mp4_format_type.upper()} Generated!")
        else:
            self.report({'ERROR'}, f"An error occured, and your {scrshot_saver.mp4_format_type.upper()} was not encoded properly.\n\nPlease send a screenshot of your console to ethan.simon.3d@gmail.com")
        return {'FINISHED'}


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
    SCRSHOT_OT_sample_studio_light_rotation,
    SCRSHOT_OT_generate_mp4
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
