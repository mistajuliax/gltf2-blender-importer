"""
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * Contributor(s): Julien Duroure.
 *
 * ***** END GPL LICENSE BLOCK *****
 """

import bpy
from .texture import *

class Pbr():

    SIMPLE  = 1
    TEXTURE = 2
    TEXTURE_FACTOR = 3

    def __init__(self, json, gltf):
        self.json = json # pbrMetallicRoughness json
        self.gltf = gltf # Reference to global glTF instance

        self.color_type = self.SIMPLE
        self.vertex_color = False
        self.metallic_type = self.SIMPLE

        # Default values
        self.baseColorFactor = [1,1,1,1]
        self.baseColorTexture = None
        self.metallicFactor = 1
        self.roughnessFactor = 1
        self.metallicRoughnessTexture = None
        self.extensions = None
        self.extras = None

    def read(self):
        if self.json is None:
            return # will use default values

        if 'baseColorTexture' in self.json.keys():
            self.color_type = self.TEXTURE
            self.baseColorTexture = Texture(self.json['baseColorTexture']['index'], self.gltf.json['textures'][self.json['baseColorTexture']['index']], self.gltf)
            self.baseColorTexture.read()
            self.baseColorTexture.debug_missing()

            if 'texCoord' in self.json['baseColorTexture']:
                self.baseColorTexture.texcoord = int(self.json['baseColorTexture']['texCoord'])
            else:
                self.baseColorTexture.texcoord = 0

        if 'metallicRoughnessTexture' in self.json.keys():
            self.metallic_type = self.TEXTURE
            self.metallicRoughnessTexture = Texture(self.json['metallicRoughnessTexture']['index'], self.gltf.json['textures'][self.json['metallicRoughnessTexture']['index']], self.gltf)
            self.metallicRoughnessTexture.read()
            self.metallicRoughnessTexture.debug_missing()

            if 'texCoord' in self.json['metallicRoughnessTexture']:
                self.metallicRoughnessTexture.texcoord = int(self.json['metallicRoughnessTexture']['texCoord'])
            else:
                self.metallicRoughnessTexture.texcoord = 0

        if 'baseColorFactor' in self.json.keys():
            self.baseColorFactor = self.json['baseColorFactor']
            if self.color_type == self.TEXTURE and self.baseColorFactor != [1.0,1.0,1.0]:
                self.color_type = self.TEXTURE_FACTOR

        if 'metallicFactor' in self.json.keys():
            self.metallicFactor = self.json['metallicFactor']
            if self.metallic_type == self.TEXTURE and self.metallicFactor != 1.0 and self.roughnessFactor != 1.0:
                self.metallic_type = self.TEXTURE_FACTOR

        if 'roughnessFactor' in self.json.keys():
            self.roughnessFactor = self.json['roughnessFactor']
            if self.metallic_type == self.TEXTURE and self.roughnessFactor != 1.0 and self.metallicFactor != 1.0:
                self.metallic_type = self.TEXTURE_FACTOR

    def use_vertex_color(self):
        self.vertex_color = True

    def create_blender(self, mat_name):
        engine = bpy.context.scene.render.engine
        if engine == 'CYCLES':
            self.create_blender_cycles(mat_name)
        else:
            pass #TODO for internal / Eevee in future 2.8

    def create_blender_cycles(self, mat_name):
        material = bpy.data.materials[mat_name]
        material.use_nodes = True
        node_tree = material.node_tree

        # delete all nodes except output
        for node in list(node_tree.nodes):
            if not node.type == 'OUTPUT_MATERIAL':
                node_tree.nodes.remove(node)

        output_node = node_tree.nodes[0]

        # create PBR node
        principled = node_tree.nodes.new('ShaderNodeBsdfPrincipled')

        if self.color_type == self.SIMPLE:

            if not self.vertex_color:

                # change input values
                principled.inputs[0].default_value = self.baseColorFactor
                principled.inputs[5].default_value = self.metallicFactor #TODO : currently set metallic & specular in same way
                principled.inputs[7].default_value = self.roughnessFactor

            else:
                # Create attribute node to get COLOR_0 data
                attribute_node = node_tree.nodes.new('ShaderNodeAttribute')
                attribute_node.attribute_name = 'COLOR_0'

                principled.inputs[5].default_value = self.metallicFactor #TODO : currently set metallic & specular in same way
                principled.inputs[7].default_value = self.roughnessFactor

                # links
                node_tree.links.new(principled.inputs[0], attribute_node.outputs[1])

        elif self.color_type == self.TEXTURE_FACTOR:

            #TODO alpha ?
            if self.vertex_color:
                # Create attribute / separate / math nodes
                attribute_node = node_tree.nodes.new('ShaderNodeAttribute')
                attribute_node.attribute_name = 'COLOR_0'

                separate_vertex_color = node_tree.nodes.new('ShaderNodeSeparateRGB')
                math_vc_R = node_tree.nodes.new('ShaderNodeMath')
                math_vc_R.operation = 'MULTIPLY'

                math_vc_G = node_tree.nodes.new('ShaderNodeMath')
                math_vc_G.operation = 'MULTIPLY'

                math_vc_B = node_tree.nodes.new('ShaderNodeMath')
                math_vc_B.operation = 'MULTIPLY'

            self.baseColorTexture.blender_create()

            # create UV Map / Mapping / Texture nodes / separate & math and combine
            text_node = node_tree.nodes.new('ShaderNodeTexImage')
            text_node.image = bpy.data.images[self.baseColorTexture.image.blender_image_name]

            combine = node_tree.nodes.new('ShaderNodeCombineRGB')

            math_R  = node_tree.nodes.new('ShaderNodeMath')
            math_R.operation = 'MULTIPLY'
            math_R.inputs[1].default_value = self.baseColorFactor[0]

            math_G  = node_tree.nodes.new('ShaderNodeMath')
            math_G.operation = 'MULTIPLY'
            math_G.inputs[1].default_value = self.baseColorFactor[1]

            math_B  = node_tree.nodes.new('ShaderNodeMath')
            math_B.operation = 'MULTIPLY'
            math_B.inputs[1].default_value = self.baseColorFactor[2]

            separate = node_tree.nodes.new('ShaderNodeSeparateRGB')

            mapping = node_tree.nodes.new('ShaderNodeMapping')

            uvmap = node_tree.nodes.new('ShaderNodeUVMap')
            uvmap["gltf2_texcoord"] = self.baseColorTexture.texcoord # Set custom flag to retrieve TexCoord
            # UV Map will be set after object/UVMap creation

            # Create links
            if self.vertex_color:
                node_tree.links.new(separate_vertex_color.inputs[0], attribute_node.outputs[0])
                node_tree.links.new(math_vc_R.inputs[1], separate_vertex_color.outputs[0])
                node_tree.links.new(math_vc_G.inputs[1], separate_vertex_color.outputs[1])
                node_tree.links.new(math_vc_B.inputs[1], separate_vertex_color.outputs[2])
                node_tree.links.new(math_vc_R.inputs[0], math_R.outputs[0])
                node_tree.links.new(math_vc_G.inputs[0], math_G.outputs[0])
                node_tree.links.new(math_vc_B.inputs[0], math_B.outputs[0])
                node_tree.links.new(combine.inputs[0], math_vc_R.outputs[0])
                node_tree.links.new(combine.inputs[1], math_vc_G.outputs[0])
                node_tree.links.new(combine.inputs[2], math_vc_B.outputs[0])

            else:
                node_tree.links.new(combine.inputs[0], math_R.outputs[0])
                node_tree.links.new(combine.inputs[1], math_G.outputs[0])
                node_tree.links.new(combine.inputs[2], math_B.outputs[0])

            # Common for both mode (non vertex color / vertex color)
            node_tree.links.new(math_R.inputs[0], separate.outputs[0])
            node_tree.links.new(math_G.inputs[0], separate.outputs[1])
            node_tree.links.new(math_B.inputs[0], separate.outputs[2])

            node_tree.links.new(mapping.inputs[0], uvmap.outputs[0])
            node_tree.links.new(text_node.inputs[0], mapping.outputs[0])
            node_tree.links.new(separate.inputs[0], text_node.outputs[0])


            node_tree.links.new(principled.inputs[0], combine.outputs[0])

        elif self.color_type == self.TEXTURE:

            self.baseColorTexture.blender_create()

            #TODO alpha ?
            if self.vertex_color:
                # Create attribute / separate / math nodes
                attribute_node = node_tree.nodes.new('ShaderNodeAttribute')
                attribute_node.attribute_name = 'COLOR_0'

                separate_vertex_color = node_tree.nodes.new('ShaderNodeSeparateRGB')
                math_vc_R = node_tree.nodes.new('ShaderNodeMath')
                math_vc_R.operation = 'MULTIPLY'

                math_vc_G = node_tree.nodes.new('ShaderNodeMath')
                math_vc_G.operation = 'MULTIPLY'

                math_vc_B = node_tree.nodes.new('ShaderNodeMath')
                math_vc_B.operation = 'MULTIPLY'


                combine = node_tree.nodes.new('ShaderNodeCombineRGB')

                math_R  = node_tree.nodes.new('ShaderNodeMath')
                math_R.operation = 'MULTIPLY'
                math_R.inputs[1].default_value = self.baseColorFactor[0]

                math_G  = node_tree.nodes.new('ShaderNodeMath')
                math_G.operation = 'MULTIPLY'
                math_G.inputs[1].default_value = self.baseColorFactor[1]

                math_B  = node_tree.nodes.new('ShaderNodeMath')
                math_B.operation = 'MULTIPLY'
                math_B.inputs[1].default_value = self.baseColorFactor[2]

                separate = node_tree.nodes.new('ShaderNodeSeparateRGB')

            # create UV Map / Mapping / Texture nodes / separate & math and combine
            text_node = node_tree.nodes.new('ShaderNodeTexImage')
            text_node.image = bpy.data.images[self.baseColorTexture.image.blender_image_name]

            mapping = node_tree.nodes.new('ShaderNodeMapping')

            uvmap = node_tree.nodes.new('ShaderNodeUVMap')
            uvmap["gltf2_texcoord"] = self.baseColorTexture.texcoord # Set custom flag to retrieve TexCoord
            # UV Map will be set after object/UVMap creation

            # Create links
            if self.vertex_color:
                node_tree.links.new(separate_vertex_color.inputs[0], attribute_node.outputs[0])

                node_tree.links.new(math_R.inputs[1], separate_vertex_color.outputs[0])
                node_tree.links.new(math_G.inputs[1], separate_vertex_color.outputs[1])
                node_tree.links.new(math_B.inputs[1], separate_vertex_color.outputs[2])

                node_tree.links.new(combine.inputs[0], math_R.outputs[0])
                node_tree.links.new(combine.inputs[1], math_G.outputs[0])
                node_tree.links.new(combine.inputs[2], math_B.outputs[0])

                node_tree.links.new(separate.inputs[0], text_node.outputs[0])

                node_tree.links.new(math_R.inputs[0], separate.outputs[0])
                node_tree.links.new(math_G.inputs[0], separate.outputs[1])
                node_tree.links.new(math_B.inputs[0], separate.outputs[2])

                node_tree.links.new(principled.inputs[0], combine.outputs[0])

            else:
                node_tree.links.new(principled.inputs[0], text_node.outputs[0])

            # Common for both mode (non vertex color / vertex color)

            node_tree.links.new(mapping.inputs[0], uvmap.outputs[0])
            node_tree.links.new(text_node.inputs[0], mapping.outputs[0])


        # Says metallic, but it means metallic & Roughness values
        if self.metallic_type == self.SIMPLE:
            principled.inputs[4].default_value = self.metallicFactor
            principled.inputs[7].default_value = self.roughnessFactor

        elif self.metallic_type == self.TEXTURE:
            self.metallicRoughnessTexture.blender_create()
            metallic_text = node_tree.nodes.new('ShaderNodeTexImage')
            metallic_text.image = bpy.data.images[self.metallicRoughnessTexture.image.blender_image_name]
            metallic_text.color_space = 'NONE'

            metallic_separate = node_tree.nodes.new('ShaderNodeSeparateRGB')

            metallic_mapping = node_tree.nodes.new('ShaderNodeMapping')

            metallic_uvmap = node_tree.nodes.new('ShaderNodeUVMap')
            metallic_uvmap["gltf2_texcoord"] = self.metallicRoughnessTexture.texcoord # Set custom flag to retrieve TexCoord

            # links
            node_tree.links.new(metallic_separate.inputs[0], metallic_text.outputs[0])
            node_tree.links.new(principled.inputs[4], metallic_separate.outputs[2]) # metallic
            node_tree.links.new(principled.inputs[7], metallic_separate.outputs[1]) # Roughness

            node_tree.links.new(metallic_mapping.inputs[0], metallic_uvmap.outputs[0])
            node_tree.links.new(metallic_text.inputs[0], metallic_mapping.outputs[0])

        elif self.metallic_type == self.TEXTURE_FACTOR:

            self.metallicRoughnessTexture.blender_create()

            metallic_text = node_tree.nodes.new('ShaderNodeTexImage')
            metallic_text.image = bpy.data.images[self.metallicRoughnessTexture.image.blender_image_name]
            metallic_text.color_space = 'NONE'
            
            metallic_separate = node_tree.nodes.new('ShaderNodeSeparateRGB')

            metallic_math     = node_tree.nodes.new('ShaderNodeMath')
            metallic_math.operation = 'MULTIPLY'
            metallic_math.inputs[1].default_value = self.metallicFactor

            roughness_math = node_tree.nodes.new('ShaderNodeMath')
            roughness_math.operation = 'MULTIPLY'
            roughness_math.inputs[1].default_value = self.roughnessFactor

            metallic_mapping = node_tree.nodes.new('ShaderNodeMapping')

            metallic_uvmap = node_tree.nodes.new('ShaderNodeUVMap')
            metallic_uvmap["gltf2_texcoord"] = self.metallicRoughnessTexture.texcoord # Set custom flag to retrieve TexCoord


            # links
            node_tree.links.new(metallic_separate.inputs[0], metallic_text.outputs[0])

            # metallic
            node_tree.links.new(metallic_math.inputs[0], metallic_separate.outputs[2])
            node_tree.links.new(principled.inputs[4], metallic_math.outputs[0])

            # roughness
            node_tree.links.new(roughness_math.inputs[0], metallic_separate.outputs[1])
            node_tree.links.new(principled.inputs[7], roughness_math.outputs[0])

            node_tree.links.new(metallic_mapping.inputs[0], metallic_uvmap.outputs[0])
            node_tree.links.new(metallic_text.inputs[0], metallic_mapping.outputs[0])

        # link node to output
        node_tree.links.new(output_node.inputs[0], principled.outputs[0])

    def debug_missing(self):
        if self.json is None:
            return
        keys = [
                'baseColorFactor',
                'metallicFactor',
                'roughnessFactor',
                'baseColorTexture',
                'metallicRoughnessTexture'
                ]

        for key in self.json.keys():
            if key not in keys:
                print("PBR MISSING " + key)
