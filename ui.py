import bpy, os
from .operators import poll_active_screenshot_item


################################################################################################################
# UI
################################################################################################################


class PanelInfo: # Mix-in class
    bl_category = 'Screenshot Saver'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'


class SCRSHOT_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor = .35)
        row = split.row()
        row.prop(item, 'enabled', text='')

        sel_and_preview_scrshot = row.operator('scrshot.select_and_preview', text='', icon='VIEW_CAMERA', emboss=False)
        sel_and_preview_scrshot.scrshot_name = item.name
        sel_and_preview_scrshot.preview_cam = True

        sel_scrshot = row.operator('scrshot.select_and_preview', text='', icon='RESTRICT_SELECT_OFF', emboss=False)
        sel_scrshot.scrshot_name = item.name
        sel_scrshot.preview_cam = False

        row = split.row()
        row.prop(item, 'name', text='', emboss=False)


class SCRSHOT_PT_ui(PanelInfo, bpy.types.Panel):
    bl_label = 'Screenshot Saver'

    def draw(self, context):
        scrshot_saver = context.scene.screenshot_saver

        correct_export_path = os.path.exists(bpy.path.abspath(scrshot_saver.export_path))

        layout = self.layout

        col = layout.column(align=True)

        row = col.row(align=True)
        row.scale_y = 1.75
        row.enabled = correct_export_path
        row.prop(
            scrshot_saver,
            'record_on_save',
            text='Disable Render on Save' if scrshot_saver.record_on_save else 'Enable Render on Save',
            icon='RADIOBUT_ON' if scrshot_saver.record_on_save else 'RADIOBUT_OFF'
            )

        row = col.row(align=True)
        row.scale_y = 1.25
        row.operator('scrshot.render_screenshots', text='Render All Screenshots', icon='RENDER_STILL').render_type = 'enabled'

        box = col.box()
        split = box.split(factor=.35)
        split.label(text='Export Path')

        row = split.row(align=True)
        row.alert = not correct_export_path
        row.prop(scrshot_saver, 'export_path')
        row.alert = False
        row.operator('scrshot.open_folder', text='', icon='FOLDER_REDIRECT')

        box.separator(factor=.5)

        render = context.scene.render
        image_settings = render.image_settings

        
        split = box.split(factor=.35)
        split.label(text='Format')
        split.prop(scrshot_saver, 'format_type', text='')

        # EXR settings not necessary
        if scrshot_saver.format_type == 'png':
            box.prop(image_settings, 'compression', text='Lossless Compression')
        elif scrshot_saver.format_type == 'jpeg':
            box.prop(image_settings, 'quality')


class SCRSHOT_PT_screenshot_manager(PanelInfo, bpy.types.Panel):
    bl_label = 'Screenshot Manager'
    bl_options = {'HEADER_LAYOUT_EXPAND'}
    bl_parent_id = "SCRSHOT_PT_ui"

    def draw(self, context):
        scene = context.scene

        layout = self.layout

        col = layout.column(align=True)
        col.scale_y = 1.25
        col.operator('scrshot.render_screenshots', text='Render Single Screenshot', icon='RENDER_STILL').render_type = 'single'
        
        col = layout.column(align=True)
        col.prop(
            context.space_data,
            'lock_camera',
            text='Lock Camera to View',
            icon='LOCKED' if context.space_data.lock_camera else 'UNLOCKED'
            )

        row = layout.row()

        col1 = row.column(align=True)
        col1.template_list("SCRSHOT_UL_items", "", scene, "scrshot_camera_coll", scene, "scrshot_camera_index", rows=4)

        col2 = row.column(align=True)
        col2.operator("scrshot.add_screenshot_item", text='', icon='ADD')
        col2.operator("scrshot.delete_screenshot_item", text='', icon='REMOVE')

        col2.separator(factor=3)

        col3 = col2.column(align=True)
        col3.operator("scrshot.copy_screenshot_settings", text='', icon='COPYDOWN')
        col3.operator("scrshot.paste_screenshot_settings", text='', icon='PASTEDOWN')

        if not len(scene.scrshot_camera_coll):
            box = layout.box()
            box.label(text='Add a new screenshot', icon='INFO')
            box.label(text='item to get started!', icon='BLANK1')


class SCRSHOT_PT_screenshot_settings(PanelInfo, bpy.types.Panel):
    bl_label = 'Screenshot Settings'
    bl_parent_id = "SCRSHOT_PT_screenshot_manager"

    @classmethod
    def poll(cls, context):
        return poll_active_screenshot_item(context)

    def draw(self, context):
        scene = context.scene

        layout = self.layout

        try:
            active_scrshot = scene.scrshot_camera_coll[scene.scrshot_camera_index]
        except IndexError:
            scene.scrshot_camera_index = -1
            active_scrshot = scene.scrshot_camera_coll[scene.scrshot_camera_index]

        ### GENERAL SETTINGS ###

        col = layout.column(align=True)
        box = col.box()
    
        split = box.split(factor=.3)
        split.label(text='Camera')

        row = split.row()
        row.enabled = not bool(active_scrshot.camera_ob)
        row.prop(active_scrshot, 'camera_ob', icon='OUTLINER_OB_CAMERA')

        if active_scrshot.camera_ob:
            camera_data = active_scrshot.camera_ob.data

            split = box.split(factor=.3)
            split.label(text='Res')

            row = split.row(align=True)
            row.prop(active_scrshot, 'cam_res_x', text='')
            row.prop(active_scrshot, 'cam_res_y', text='')
            row.prop(active_scrshot, 'lock_res', text='', icon='LOCKED' if active_scrshot.lock_res else 'UNLOCKED')

            split = box.split(factor=.3)
            split.label(text='Type')
            split.prop(active_scrshot, 'cam_type', text='')

            if camera_data.type == 'PERSP':
                split = box.split(factor=.3, align=True)
                split.label(text='Focal')

                row = split.row(align=True)
                if active_scrshot.lens_type == 'mm':
                    row.prop(camera_data, 'lens', text='')
                else: # FoV
                    row.prop(camera_data, 'angle', text='')
                row.prop(active_scrshot, 'lens_type', text='')
            else: # Ortho
                split = box.split(factor=.3, align=True)
                split.label(text='Scale')
                split.prop(camera_data, 'ortho_scale', text='')

            col.separator(factor=.5)

            split = box.split()
            split.prop(camera_data, 'passepartout_alpha')

            split = box.split()
            split.prop(camera_data, 'display_size')

        ### EXPORT SETTINGS ###

        box = col.box()

        split = box.split(factor=.35)
        split.label(text='')
        split.prop(active_scrshot, 'use_subfolder')

        split = box.split(factor=.3)
        split.enabled = active_scrshot.use_subfolder
        split.label(text='Dir Name')
        split.prop(active_scrshot, 'subfolder_name', text='')

        ### SHADING SETTINGS ###

        col = layout.column(align=True)

        row = col.row(align=True)
        row.scale_y = 1.2
        row.prop(active_scrshot, 'render_type', expand=True)

        box = col.box()

        split = box.split(factor=.35)
        split.label(text='')
        split.prop(active_scrshot, 'use_defaults')

        col_shading = box.column(align=True)
        col_shading.enabled = not active_scrshot.use_defaults

        if active_scrshot.render_type == 'workbench':
            row_shad = col_shading.row(align=True)
            row_shad.prop(active_scrshot, 'lighting_type', expand=True)

            box_shad = col_shading.box()

            if active_scrshot.lighting_type == 'studio':
                split = box_shad.split(align=True, factor=.15)

                row = split.row()
                row.prop(active_scrshot, 'use_wsl', text='', icon='WORLD')

                row = split.row(align=True)
                row.enabled = active_scrshot.use_wsl
                row.operator("scrshot.sample_studio_light_rotation", text='', icon='EYEDROPPER')
                row.prop(active_scrshot, 'studio_rotate_z')

            #elif active_scrshot.lighting_type == 'matcap':
            #    box_shad.template_icon_view(context.space_data.shading, "studio_light", scale_popup=2.5) # How do I recreate this??
            #else: # flat
            #    pass
        else: # EEVEE
            pass


class SCRSHOT_PT_convert_ui(PanelInfo, bpy.types.Panel):
    bl_label = 'Convert Media'
    bl_parent_id = "SCRSHOT_PT_ui"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout


################################################################################################################
# REGISTRATION
################################################################################################################


classes = (
    SCRSHOT_UL_items,
    SCRSHOT_PT_ui,
    SCRSHOT_PT_screenshot_manager,
    SCRSHOT_PT_screenshot_settings,
    #SCRSHOT_PT_convert_ui
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
