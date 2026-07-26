# -*- coding: utf-8 -*-

import nuke

def createAutoPrecomp():
    if not nuke.selectedNodes():
        nuke.message("请先选中一个节点")
        return

    sel = nuke.selectedNode()
    channels = sel.channels()
    chan_list = []

    for channel in channels:
        channel_name = channel.split('.')[0]
        if channel_name not in chan_list:
            chan_list.append(channel_name)

    if not chan_list:
        nuke.message("未找到任何通道")
        return

    has_caustics = any('caustics' in c.lower() for c in chan_list)
    has_blender_cycles = any(c in chan_list for c in ['Diffuse_Direct', 'Diffuse_Indirect', 'Diffuse_Color', 'Glossy_Direct', 'Glossy_Indirect', 'Glossy_Color', 'Transmission_Direct', 'Transmission_Indirect', 'Transmission_Color'])

    if has_blender_cycles:
        createBlender_cyclesPrecomp()
    elif has_caustics:
        createRedshiftPrecomp()
    else:
        createArnoldPrecomp()


def createArnoldPrecomp():
    if not nuke.selectedNodes():
        nuke.message("请先选中一个节点")
        return

    sel = nuke.selectedNode()
    channels = sel.channels()
    chan_list = []

    for channel in channels:
        channel_name = channel.split('.')[0]
        if channel_name not in chan_list:
            chan_list.append(channel_name)

    if not chan_list:
        nuke.message("未找到任何通道")
        return

    standard_aov_layers = [
        'diffuse', 'specular', 'coat', 'transmission', 'sss',
        'volume', 'emission', 'background', 'indirect', 'direct'
    ]

    light_aov_groups = {}
    ungrouped_channels = []

    has_emission = 'emission' in chan_list
    has_volume = 'volume' in chan_list

    for channel_name in chan_list:
        parts = channel_name.split('_')

        if len(parts) >= 2:
            aov_layer = parts[0].lower()
            light_aov = '_'.join(parts[1:])

            if aov_layer in standard_aov_layers:
                if light_aov not in light_aov_groups:
                    light_aov_groups[light_aov] = {}
                light_aov_groups[light_aov][aov_layer] = channel_name
            else:
                ungrouped_channels.append(channel_name)
        else:
            ungrouped_channels.append(channel_name)

    ungrouped_channels = [c for c in ungrouped_channels if c not in ['emission', 'volume']]

    read_x = int(sel.xpos())
    read_y = int(sel.ypos())

    dot_y = read_y + 442
    shuffle_y = dot_y + 70

    dot_spacing = 197
    group_spacing = 977

    merge_order = ['coat', 'diffuse', 'specular', 'sss', 'transmission']

    last_dot_node = None
    group_outputs = []
    light_group_outputs = []
    volume_x = None

    read_dot = nuke.nodes.Dot(note_font_size=35)
    read_dot.setXYpos(read_x + 34, dot_y)
    read_dot.setInput(0, sel)
    last_dot_node = read_dot

    sorted_lights = sorted(light_aov_groups.keys())

    for idx, light_aov in enumerate(sorted_lights):
        aov_channels = light_aov_groups[light_aov]
        present_layers = [layer for layer in merge_order if layer in aov_channels]

        first_dot_x = read_x + 34 + 197 + (idx * group_spacing)
        shuffle_start_x = first_dot_x - 34

        backdrop = nuke.nodes.BackdropNode(
            name=f'Backdrop_{light_aov}',
            label=light_aov,
            tile_color=int('0x71c67100', 16),
            note_font_size=120,
            xpos=shuffle_start_x - 10,
            ypos=dot_y - 74,
            bdwidth=888,
            bdheight=1376
        )

        top_dots = []

        first_dot = nuke.nodes.Dot(note_font_size=35)
        first_dot.setXYpos(first_dot_x, dot_y)
        first_dot.setInput(0, last_dot_node)
        top_dots.append(first_dot)
        last_dot_node = first_dot

        for i in range(1, len(present_layers)):
            dot = nuke.nodes.Dot(note_font_size=35)
            dot.setXYpos(first_dot_x + (i * dot_spacing), dot_y)
            dot.setInput(0, top_dots[i-1])
            top_dots.append(dot)
            last_dot_node = dot

        shuffle_nodes = {}
        bottom_dots = {}

        for i, aov_layer in enumerate(present_layers):
            channel_name = aov_channels[aov_layer]
            shuffle_x = shuffle_start_x + (i * dot_spacing)
            bottom_dot_x = first_dot_x + (i * dot_spacing)

            shuffle = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle['in'].setValue(channel_name)
            shuffle.setXYpos(shuffle_x, shuffle_y)
            shuffle.setInput(0, top_dots[i])
            shuffle_nodes[aov_layer] = shuffle

            y_offsets = [299, 302, 528, 845, 1159]
            bottom_dot = nuke.nodes.Dot(note_font_size=35)
            bottom_dot.setXYpos(bottom_dot_x, shuffle_y + y_offsets[i])
            bottom_dot.setInput(0, shuffle)
            bottom_dots[aov_layer] = bottom_dot

        merge_y_offsets = [299, 525, 842, 1156]

        prev_merge = None
        for i, aov_layer in enumerate(present_layers):
            if i == 0:
                prev_merge = bottom_dots[aov_layer]
            else:
                merge = nuke.nodes.Merge2(operation='plus')
                merge.setXYpos(shuffle_start_x, shuffle_y + merge_y_offsets[i-1])
                merge.setInput(0, prev_merge)
                merge.setInput(1, bottom_dots[aov_layer])
                prev_merge = merge

        group_outputs.append(prev_merge)
        light_group_outputs.append(prev_merge)

    if has_emission:
        emission_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34 + 107
        emission_dot_x = emission_shuffle_x + 34

        nuke.nodes.BackdropNode(
            name='BackdropNode_emission',
            label='Emission',
            tile_color=int('0x388e8e00', 16),
            note_font_size=42,
            xpos=emission_shuffle_x - 40,
            ypos=dot_y - 71,
            bdwidth=223,
            bdheight=1367
        )

        emission_dot = nuke.nodes.Dot(note_font_size=35)
        emission_dot.setXYpos(emission_dot_x, dot_y)
        emission_dot.setInput(0, last_dot_node)
        last_dot_node = emission_dot

        emission_shuffle = nuke.nodes.Shuffle(name='emission', postage_stamp=True)
        emission_shuffle['in'].setValue('emission')
        emission_shuffle.setXYpos(emission_shuffle_x, shuffle_y + 6)
        emission_shuffle.setInput(0, emission_dot)

        emission_grade = nuke.nodes.Grade(name='Grade_emission')
        emission_grade.setXYpos(emission_shuffle_x, shuffle_y + 1137)
        emission_grade.setInput(0, emission_shuffle)

        emission_merge = nuke.nodes.Merge2(operation='plus', name='Merge_emission')
        emission_merge.setXYpos(emission_shuffle_x, read_y + 1974)
        emission_merge.setInput(1, emission_grade)

        group_outputs.append(emission_merge)

    if has_volume:
        if has_emission:
            volume_shuffle_x = emission_shuffle_x + 257
        else:
            volume_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        volume_dot_x = volume_shuffle_x + 34
        volume_x = volume_shuffle_x

        nuke.nodes.BackdropNode(
            name='BackdropNode_volume',
            label='volume',
            tile_color=int('0x388e8e00', 16),
            note_font_size=42,
            xpos=volume_shuffle_x - 40,
            ypos=dot_y - 72,
            bdwidth=208,
            bdheight=1368
        )

        volume_dot = nuke.nodes.Dot(note_font_size=35)
        volume_dot.setXYpos(volume_dot_x, dot_y)
        volume_dot.setInput(0, last_dot_node)
        last_dot_node = volume_dot

        volume_shuffle = nuke.nodes.Shuffle(name='volume', postage_stamp=True)
        volume_shuffle['in'].setValue('volume')
        volume_shuffle.setXYpos(volume_shuffle_x, shuffle_y + 3)
        volume_shuffle.setInput(0, volume_dot)

        volume_grade = nuke.nodes.Grade(name='Grade_volume')
        volume_grade.setXYpos(volume_shuffle_x, shuffle_y + 1139)
        volume_grade.setInput(0, volume_shuffle)

        volume_merge = nuke.nodes.Merge2(operation='plus', name='Merge_volume')
        volume_merge.setXYpos(volume_shuffle_x, read_y + 1974)
        volume_merge.setInput(1, volume_grade)

        group_outputs.append(volume_merge)

        if ungrouped_channels:
            if has_emission and has_volume:
                extra_start_x = volume_shuffle_x + 257
            elif has_volume:
                extra_start_x = volume_shuffle_x + 257
            elif has_emission:
                extra_start_x = emission_shuffle_x + 257
            else:
                extra_start_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        prev_dot = None
        for i, channel_name in enumerate(ungrouped_channels):
            x_pos = extra_start_x + (i * dot_spacing)

            dot_node = nuke.nodes.Dot(note_font_size=35)
            dot_node.setXYpos(x_pos + 34, dot_y)

            if i == 0:
                dot_node.setInput(0, last_dot_node)
            else:
                dot_node.setInput(0, prev_dot)

            prev_dot = dot_node
            last_dot_node = dot_node

            shuffle_node = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle_node['in'].setValue(channel_name)
            shuffle_node.setXYpos(x_pos, shuffle_y)
            shuffle_node.setInput(0, dot_node)


    first_light_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 231, ypos=read_y + 1977)

    if len(light_group_outputs) > 1:
        final_merge_y = read_y + 1974
        final_merge_x = read_x + 1174

        prev_merge = None
        for i, output_node in enumerate(light_group_outputs):
            if i == 0:
                prev_merge = first_light_dot
                first_light_dot.setInput(0, output_node)

            else:
                final_merge = nuke.nodes.Merge2(operation='plus', name=f'Final_Merge_{i-1}')
                final_merge.setXYpos(final_merge_x, final_merge_y)
                final_merge.setInput(0, prev_merge)
                final_merge.setInput(1, output_node)
                prev_merge = final_merge
                final_merge_x += 977


        copy_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 34, ypos=final_merge_y + 146)
        copy_dot.setInput(0, read_dot)


        if has_volume and volume_x is not None:
            copy_node = nuke.nodes.Copy(name='Copy_alpha')
            copy_node['from0'].setValue('rgba.alpha')
            copy_node['to0'].setValue('rgba.alpha')
            copy_node.setXYpos(volume_x, final_merge_y + 137)
            copy_node.setInput(0, volume_merge)
            copy_node.setInput(1, copy_dot)

        emission_merge.setInput(0, prev_merge)
        volume_merge.setInput(0, emission_merge)

    nuke.message(f"已创建 {len(light_aov_groups)} 个Arnold AOV预合成组")


def createRedshiftPrecomp():
    if not nuke.selectedNodes():
        nuke.message("请先选中一个节点")
        return

    sel = nuke.selectedNode()
    channels = sel.channels()
    chan_list = []

    for channel in channels:
        channel_name = channel.split('.')[0]
        if channel_name not in chan_list:
            chan_list.append(channel_name)

    if not chan_list:
        nuke.message("未找到任何通道")
        return

    redshift_aov_layers = [
        'DiffuseLighting', 'Reflections', 'SpecularLighting',
        'Refractions', 'SSS', 'GI', 'Emission', 'Volume'
    ]

    light_aov_groups = {}
    ungrouped_channels = []

    has_emission = any('emission' in c.lower() for c in chan_list)
    has_volume = any('volume' in c.lower() for c in chan_list)
    has_caustics = any('caustics' in c.lower() for c in chan_list)

    for channel_name in chan_list:
        matched = False

        for aov_layer in redshift_aov_layers:
            if channel_name.startswith(aov_layer):
                if len(channel_name) > len(aov_layer):
                    light_name = channel_name[len(aov_layer):]
                    if light_name.startswith('_'):
                        light_name = light_name[1:]
                    if light_name:
                        if light_name not in light_aov_groups:
                            light_aov_groups[light_name] = {}
                        light_aov_groups[light_name][aov_layer] = channel_name
                        matched = True
                        break

        if not matched:
            ungrouped_channels.append(channel_name)

    ungrouped_channels = [c for c in ungrouped_channels
                          if 'emission' not in c.lower() and 'volume' not in c.lower()]

    read_x = int(sel.xpos())
    read_y = int(sel.ypos())

    dot_y = read_y + 442
    shuffle_y = dot_y + 70

    dot_spacing = 197
    group_spacing = 1150

    merge_order = ['DiffuseLighting', 'SSS', 'Reflections', 'SpecularLighting', 'Refractions', 'GI']

    last_dot_node = None
    group_outputs = []
    light_group_outputs = []
    volume_x = None
    caustics_x = None

    read_dot = nuke.nodes.Dot(note_font_size=35)
    read_dot.setXYpos(read_x + 34, dot_y)
    read_dot.setInput(0, sel)
    last_dot_node = read_dot

    sorted_lights = sorted(light_aov_groups.keys())

    for idx, light_aov in enumerate(sorted_lights):
        aov_channels = light_aov_groups[light_aov]
        present_layers = [layer for layer in merge_order if layer in aov_channels]

        first_dot_x = read_x + 34 + 197 + (idx * group_spacing)
        shuffle_start_x = first_dot_x - 34

        backdrop = nuke.nodes.BackdropNode(
            name=f'Backdrop_{light_aov}',
            label=light_aov,
            tile_color=int('0x71c67100', 16),
            note_font_size=120,
            xpos=shuffle_start_x - 10,
            ypos=dot_y - 74,
            bdwidth=1100,
            bdheight=1650
        )

        top_dots = []

        first_dot = nuke.nodes.Dot(note_font_size=35)
        first_dot.setXYpos(first_dot_x, dot_y)
        first_dot.setInput(0, last_dot_node)
        top_dots.append(first_dot)
        last_dot_node = first_dot

        for i in range(1, len(present_layers)):
            dot = nuke.nodes.Dot(note_font_size=35)
            dot.setXYpos(first_dot_x + (i * dot_spacing), dot_y)
            dot.setInput(0, top_dots[i-1])
            top_dots.append(dot)
            last_dot_node = dot

        shuffle_nodes = {}
        bottom_dots = {}

        for i, aov_layer in enumerate(present_layers):
            channel_name = aov_channels[aov_layer]
            shuffle_x = shuffle_start_x + (i * dot_spacing)
            bottom_dot_x = first_dot_x + (i * dot_spacing)

            shuffle = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle['in'].setValue(channel_name)
            shuffle.setXYpos(shuffle_x, shuffle_y)
            shuffle.setInput(0, top_dots[i])
            shuffle_nodes[aov_layer] = shuffle

            if i > 0:
                y_offsets = [299, 302, 528, 845, 1159, 1473]
                bottom_dot = nuke.nodes.Dot(note_font_size=35)
                bottom_dot.setXYpos(bottom_dot_x, shuffle_y + y_offsets[i])
                bottom_dot.setInput(0, shuffle)
                bottom_dots[aov_layer] = bottom_dot

        merge_y_offsets = [299, 525, 842, 1156, 1473]

        prev_merge = None
        for i, aov_layer in enumerate(present_layers):
            if i == 0:
                prev_merge = shuffle_nodes[aov_layer]
            else:
                merge = nuke.nodes.Merge2(operation='plus')
                merge.setXYpos(shuffle_start_x, shuffle_y + merge_y_offsets[i-1])
                merge.setInput(0, prev_merge)
                merge.setInput(1, bottom_dots[aov_layer])
                prev_merge = merge

        group_outputs.append(prev_merge)
        light_group_outputs.append(prev_merge)

    emission_merge = None
    if has_emission:
        emission_channel = next(c for c in chan_list if 'emission' in c.lower())
        emission_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34 + 107
        emission_dot_x = emission_shuffle_x + 34

        nuke.nodes.BackdropNode(
            name='BackdropNode_emission',
            label='Emission',
            tile_color=int('0x388e8e00', 16),
            note_font_size=42,
            xpos=emission_shuffle_x - 40,
            ypos=dot_y - 71,
            bdwidth=223,
            bdheight=1367
        )

        emission_dot = nuke.nodes.Dot(note_font_size=35)
        emission_dot.setXYpos(emission_dot_x, dot_y)
        emission_dot.setInput(0, last_dot_node)
        last_dot_node = emission_dot

        emission_shuffle = nuke.nodes.Shuffle(name=emission_channel, postage_stamp=True)
        emission_shuffle['in'].setValue(emission_channel)
        emission_shuffle.setXYpos(emission_shuffle_x, shuffle_y + 6)
        emission_shuffle.setInput(0, emission_dot)

        emission_grade = nuke.nodes.Grade(name='Grade_emission')
        emission_grade.setXYpos(emission_shuffle_x, shuffle_y + 1137)
        emission_grade.setInput(0, emission_shuffle)

        emission_merge = nuke.nodes.Merge2(operation='plus', name='Merge_emission')
        emission_merge.setXYpos(emission_shuffle_x, read_y + 2180)
        emission_merge.setInput(1, emission_grade)

        group_outputs.append(emission_merge)

    volume_merge = None
    if has_volume:
        volume_channel = next(c for c in chan_list if 'volume' in c.lower())
        if has_emission:
            volume_shuffle_x = emission_shuffle_x + 257
        else:
            volume_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        volume_dot_x = volume_shuffle_x + 34
        volume_x = volume_shuffle_x

        nuke.nodes.BackdropNode(
            name='BackdropNode_volume',
            label='Volume',
            tile_color=int('0x388e8e00', 16),
            note_font_size=42,
            xpos=volume_shuffle_x - 40,
            ypos=dot_y - 72,
            bdwidth=208,
            bdheight=1368
        )

        volume_dot = nuke.nodes.Dot(note_font_size=35)
        volume_dot.setXYpos(volume_dot_x, dot_y)
        volume_dot.setInput(0, last_dot_node)
        last_dot_node = volume_dot

        volume_shuffle = nuke.nodes.Shuffle(name=volume_channel, postage_stamp=True)
        volume_shuffle['in'].setValue(volume_channel)
        volume_shuffle.setXYpos(volume_shuffle_x, shuffle_y + 3)
        volume_shuffle.setInput(0, volume_dot)

        volume_grade = nuke.nodes.Grade(name='Grade_volume')
        volume_grade.setXYpos(volume_shuffle_x, shuffle_y + 1139)
        volume_grade.setInput(0, volume_shuffle)

        volume_merge = nuke.nodes.Merge2(operation='plus', name='Merge_volume')
        volume_merge.setXYpos(volume_shuffle_x, read_y + 2180)
        volume_merge.setInput(1, volume_grade)

        group_outputs.append(volume_merge)

    caustics_merge = None
    if has_caustics:
        caustics_channel = next(c for c in chan_list if 'caustics' in c.lower())

        if has_volume:
            caustics_shuffle_x = volume_shuffle_x + 257
        elif has_emission:
            caustics_shuffle_x = emission_shuffle_x + 257
        else:
            caustics_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        caustics_dot_x = caustics_shuffle_x + 34
        caustics_x = caustics_shuffle_x

        nuke.nodes.BackdropNode(
            name='BackdropNode_caustics',
            label='Caustics',
            tile_color=int('0x388e8e00', 16),
            note_font_size=42,
            xpos=caustics_shuffle_x - 40,
            ypos=dot_y - 72,
            bdwidth=208,
            bdheight=1650
        )

        caustics_dot = nuke.nodes.Dot(note_font_size=35)
        caustics_dot.setXYpos(caustics_dot_x, dot_y)
        caustics_dot.setInput(0, last_dot_node)
        last_dot_node = caustics_dot

        caustics_shuffle = nuke.nodes.Shuffle(name=caustics_channel, postage_stamp=True)
        caustics_shuffle['in'].setValue(caustics_channel)
        caustics_shuffle.setXYpos(caustics_shuffle_x, shuffle_y + 3)
        caustics_shuffle.setInput(0, caustics_dot)

        caustics_grade = nuke.nodes.Grade(name='Grade_caustics')
        caustics_grade.setXYpos(caustics_shuffle_x, shuffle_y + 1139)
        caustics_grade.setInput(0, caustics_shuffle)

        caustics_merge = nuke.nodes.Merge2(operation='plus', name='Merge_caustics')
        caustics_merge.setXYpos(caustics_shuffle_x, read_y + 2180)
        caustics_merge.setInput(1, caustics_grade)

        group_outputs.append(caustics_merge)

    if ungrouped_channels:
        if has_emission and has_volume:
            extra_start_x = volume_shuffle_x + 257
        elif has_volume:
            extra_start_x = volume_shuffle_x + 257
        elif has_emission:
            extra_start_x = emission_shuffle_x + 257
        else:
            extra_start_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        prev_dot = None
        for i, channel_name in enumerate(ungrouped_channels):
            x_pos = extra_start_x + (i * dot_spacing)

            dot_node = nuke.nodes.Dot(note_font_size=35)
            dot_node.setXYpos(x_pos + 34, dot_y)

            if i == 0:
                dot_node.setInput(0, last_dot_node)
            else:
                dot_node.setInput(0, prev_dot)

            prev_dot = dot_node
            last_dot_node = dot_node

            shuffle_node = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle_node['in'].setValue(channel_name)
            shuffle_node.setXYpos(x_pos, shuffle_y)
            shuffle_node.setInput(0, dot_node)

    first_light_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 231, ypos=read_y + 2200)

    if len(light_group_outputs) > 0:
        final_merge_y = read_y + 2197
        final_merge_x = read_x + 1347

        prev_merge = None
        for i, output_node in enumerate(light_group_outputs):
            if i == 0:
                prev_merge = first_light_dot
                first_light_dot.setInput(0, output_node)
            else:
                final_merge = nuke.nodes.Merge2(operation='plus', name=f'Final_Merge_{i-1}')
                final_merge.setXYpos(final_merge_x, final_merge_y)
                final_merge.setInput(0, prev_merge)
                final_merge.setInput(1, output_node)
                prev_merge = final_merge
                final_merge_x += 1150

        copy_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 34, ypos=final_merge_y + 146)
        copy_dot.setInput(0, read_dot)

        if has_caustics and caustics_x is not None and caustics_merge is not None:
            copy_node = nuke.nodes.Copy(name='Copy_alpha')
            copy_node['from0'].setValue('rgba.alpha')
            copy_node['to0'].setValue('rgba.alpha')
            copy_node.setXYpos(caustics_x, final_merge_y + 137)
            copy_node.setInput(0, caustics_merge)
            copy_node.setInput(1, copy_dot)

        if emission_merge is not None and prev_merge is not None:
            emission_merge.setInput(0, prev_merge)

        if volume_merge is not None and emission_merge is not None:
            volume_merge.setInput(0, emission_merge)
        elif volume_merge is not None and prev_merge is not None:
            volume_merge.setInput(0, prev_merge)

        if caustics_merge is not None and emission_merge is not None:
            caustics_merge.setInput(0, emission_merge)
        elif caustics_merge is not None and volume_merge is not None:
            caustics_merge.setInput(0, volume_merge)
        elif caustics_merge is not None and prev_merge is not None:
            caustics_merge.setInput(0, prev_merge)

    nuke.message(f"已创建 {len(light_aov_groups)} 个Redshift AOV预合成组")


def createBlender_cyclesPrecomp():
    if not nuke.selectedNodes():
        nuke.message("请先选中一个节点")
        return

    sel = nuke.selectedNode()
    channels = sel.channels()
    chan_list = []

    for channel in channels:
        channel_name = channel.split('.')[0]
        if channel_name not in chan_list:
            chan_list.append(channel_name)

    if not chan_list:
        nuke.message("未找到任何通道")
        return

    read_x = int(sel.xpos())
    read_y = int(sel.ypos())

    dot_y = read_y + 442
    shuffle_y = dot_y + 70

    dot_spacing = 197
    group_spacing = 977

    last_dot_node = None
    light_group_outputs = []
    volume_x = None

    unpremult_node = nuke.nodes.Unpremult(name='Unpremult_all')
    unpremult_node['channels'].setValue('all')
    unpremult_node.setXYpos(read_x, dot_y - 140)
    unpremult_node.setInput(0, sel)

    read_dot = nuke.nodes.Dot(note_font_size=35)
    read_dot.setXYpos(read_x + 34, dot_y)
    read_dot.setInput(0, unpremult_node)
    last_dot_node = read_dot

    used_channels = set()

    aov_categories = [
        ('Diffuse', ['Diffuse_Direct', 'Diffuse_Indirect', 'Diffuse_Color']),
        ('Glossy', ['Glossy_Direct', 'Glossy_Indirect', 'Glossy_Color']),
        ('Transmission', ['Transmission_Direct', 'Transmission_Indirect', 'Transmission_Color']),
    ]

    for idx, (category, channels_needed) in enumerate(aov_categories):
        present_channels = [c for c in channels_needed if c in chan_list]
        if not present_channels:
            continue

        for c in present_channels:
            used_channels.add(c)

        first_dot_x = read_x + 34 + 197 + (idx * group_spacing)
        shuffle_start_x = first_dot_x - 34

        backdrop = nuke.nodes.BackdropNode(
            name=f'Backdrop_{category}',
            label=category,
            tile_color=int('0x71c67100', 16),
            note_font_size=120,
            xpos=shuffle_start_x - 10,
            ypos=dot_y - 74,
            bdwidth=888,
            bdheight=1376
        )

        top_dots = []
        first_dot = nuke.nodes.Dot(note_font_size=35)
        first_dot.setXYpos(first_dot_x, dot_y)
        first_dot.setInput(0, last_dot_node)
        top_dots.append(first_dot)
        last_dot_node = first_dot

        for i in range(1, len(present_channels)):
            dot = nuke.nodes.Dot(note_font_size=35)
            dot.setXYpos(first_dot_x + (i * dot_spacing), dot_y)
            dot.setInput(0, top_dots[i-1])
            top_dots.append(dot)
            last_dot_node = dot

        shuffle_nodes = {}
        bottom_dots = {}
        for i, channel_name in enumerate(present_channels):
            shuffle_x = shuffle_start_x + (i * dot_spacing)
            bottom_dot_x = first_dot_x + (i * dot_spacing)
            shuffle = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle['in'].setValue(channel_name)
            shuffle.setXYpos(shuffle_x, shuffle_y)
            shuffle.setInput(0, top_dots[i])
            shuffle_nodes[channel_name] = shuffle

            y_offsets = [299, 302, 528]
            bottom_dot = nuke.nodes.Dot(note_font_size=35)
            bottom_dot.setXYpos(bottom_dot_x, shuffle_y + y_offsets[i])
            bottom_dot.setInput(0, shuffle)
            bottom_dots[channel_name] = bottom_dot

        has_direct = channels_needed[0] in shuffle_nodes
        has_indirect = channels_needed[1] in shuffle_nodes
        has_color = channels_needed[2] in shuffle_nodes

        prev_merge = None

        if has_direct and has_indirect:
            direct_indirect_merge = nuke.nodes.Merge2(operation='plus', name=f'{category}_Direct_Indirect_Merge')
            direct_indirect_merge.setXYpos(shuffle_start_x, shuffle_y + 299)
            direct_indirect_merge.setInput(0, bottom_dots[channels_needed[0]])
            direct_indirect_merge.setInput(1, bottom_dots[channels_needed[1]])

            if has_color:
                multiply_node = nuke.nodes.Merge2(operation='multiply', name=f'{category}_Multiply')
                multiply_node.setXYpos(shuffle_start_x, shuffle_y + 525)
                multiply_node.setInput(0, direct_indirect_merge)
                multiply_node.setInput(1, bottom_dots[channels_needed[2]])
                prev_merge = multiply_node
            else:
                prev_merge = direct_indirect_merge
        elif has_direct:
            if has_color:
                multiply_node = nuke.nodes.Merge2(operation='multiply', name=f'{category}_Multiply')
                multiply_node.setXYpos(shuffle_start_x, shuffle_y + 299)
                multiply_node.setInput(0, bottom_dots[channels_needed[0]])
                multiply_node.setInput(1, bottom_dots[channels_needed[2]])
                prev_merge = multiply_node
            else:
                prev_merge = shuffle_nodes[channels_needed[0]]
        elif has_indirect:
            if has_color:
                multiply_node = nuke.nodes.Merge2(operation='multiply', name=f'{category}_Multiply')
                multiply_node.setXYpos(shuffle_start_x, shuffle_y + 299)
                multiply_node.setInput(0, bottom_dots[channels_needed[1]])
                multiply_node.setInput(1, bottom_dots[channels_needed[2]])
                prev_merge = multiply_node
            else:
                prev_merge = shuffle_nodes[channels_needed[1]]
        elif has_color:
            prev_merge = shuffle_nodes[channels_needed[2]]

        if prev_merge:
            light_group_outputs.append(prev_merge)

    emission_merge = None
    has_emission = 'Emission' in chan_list
    extra_start_x = read_x + 34 + 197 + (len(aov_categories) * group_spacing) - 34

    if has_emission:
        used_channels.add('Emission')

        nuke.nodes.BackdropNode(
            name='BackdropNode_emission',
            label='Emission',
            tile_color=int('0x388e8e00', 16),
            note_font_size=42,
            xpos=extra_start_x - 40,
            ypos=dot_y - 71,
            bdwidth=223,
            bdheight=1367
        )

        emission_dot = nuke.nodes.Dot(note_font_size=35)
        emission_dot.setXYpos(extra_start_x + 34, dot_y)
        emission_dot.setInput(0, last_dot_node)
        last_dot_node = emission_dot

        emission_shuffle = nuke.nodes.Shuffle(name='Emission', postage_stamp=True)
        emission_shuffle['in'].setValue('Emission')
        emission_shuffle.setXYpos(extra_start_x, shuffle_y + 6)
        emission_shuffle.setInput(0, emission_dot)

        emission_grade = nuke.nodes.Grade(name='Grade_emission')
        emission_grade.setXYpos(extra_start_x, shuffle_y + 1137)
        emission_grade.setInput(0, emission_shuffle)

        emission_merge = nuke.nodes.Merge2(operation='plus', name='Merge_emission')
        emission_merge.setXYpos(extra_start_x, read_y + 1974)
        emission_merge.setInput(1, emission_grade)

        extra_start_x += 257

    environment_merge = None
    has_environment = 'Environment' in chan_list
    if has_environment:
        used_channels.add('Environment')

        nuke.nodes.BackdropNode(
            name='BackdropNode_environment',
            label='Environment',
            tile_color=int('0x388e8e00', 16),
            note_font_size=42,
            xpos=extra_start_x - 40,
            ypos=dot_y - 71,
            bdwidth=223,
            bdheight=1367
        )

        env_dot = nuke.nodes.Dot(note_font_size=35)
        env_dot.setXYpos(extra_start_x + 34, dot_y)
        env_dot.setInput(0, last_dot_node)
        last_dot_node = env_dot

        env_shuffle = nuke.nodes.Shuffle(name='Environment', postage_stamp=True)
        env_shuffle['in'].setValue('Environment')
        env_shuffle.setXYpos(extra_start_x, shuffle_y + 6)
        env_shuffle.setInput(0, env_dot)

        env_grade = nuke.nodes.Grade(name='Grade_environment')
        env_grade.setXYpos(extra_start_x, shuffle_y + 1137)
        env_grade.setInput(0, env_shuffle)

        environment_merge = nuke.nodes.Merge2(operation='plus', name='Merge_environment')
        environment_merge.setXYpos(extra_start_x, read_y + 1974)
        environment_merge.setInput(1, env_grade)

        extra_start_x += 257

    volume_merge = None
    vol_channels = ['Volume_Direct', 'Volume_Indirect']
    has_volume_direct = vol_channels[0] in chan_list
    has_volume_indirect = vol_channels[1] in chan_list

    if has_volume_direct or has_volume_indirect:
        for c in vol_channels:
            if c in chan_list:
                used_channels.add(c)

        volume_backdrop_width = 208
        if has_volume_direct and has_volume_indirect:
            volume_backdrop_width = 400

        nuke.nodes.BackdropNode(
            name='BackdropNode_volume',
            label='Volume',
            tile_color=int('0x388e8e00', 16),
            note_font_size=84,
            xpos=extra_start_x - 40,
            ypos=dot_y - 72,
            bdwidth=volume_backdrop_width,
            bdheight=1368
        )

        volume_dot = nuke.nodes.Dot(note_font_size=35)
        volume_dot.setXYpos(extra_start_x + 34, dot_y)
        volume_dot.setInput(0, last_dot_node)
        last_dot_node = volume_dot

        volume_x = extra_start_x
        vol_merge_input = None

        if has_volume_direct and has_volume_indirect:
            vol_direct_shuffle = nuke.nodes.Shuffle(name='Volume_Direct', postage_stamp=True)
            vol_direct_shuffle['in'].setValue('Volume_Direct')
            vol_direct_shuffle.setXYpos(extra_start_x, shuffle_y + 3)
            vol_direct_shuffle.setInput(0, volume_dot)

            vol_direct_bottom_dot = nuke.nodes.Dot(note_font_size=35)
            vol_direct_bottom_dot.setXYpos(extra_start_x + 34, shuffle_y + 299)
            vol_direct_bottom_dot.setInput(0, vol_direct_shuffle)

            vol_indirect_dot = nuke.nodes.Dot(note_font_size=35)
            vol_indirect_dot.setXYpos(extra_start_x + dot_spacing + 34, dot_y)
            vol_indirect_dot.setInput(0, volume_dot)
            last_dot_node = vol_indirect_dot

            vol_indirect_shuffle = nuke.nodes.Shuffle(name='Volume_Indirect', postage_stamp=True)
            vol_indirect_shuffle['in'].setValue('Volume_Indirect')
            vol_indirect_shuffle.setXYpos(extra_start_x + dot_spacing, shuffle_y + 3)
            vol_indirect_shuffle.setInput(0, vol_indirect_dot)

            vol_indirect_bottom_dot = nuke.nodes.Dot(note_font_size=35)
            vol_indirect_bottom_dot.setXYpos(extra_start_x + dot_spacing + 34, shuffle_y + 302)
            vol_indirect_bottom_dot.setInput(0, vol_indirect_shuffle)

            vol_merge = nuke.nodes.Merge2(operation='plus', name='Volume_Merge')
            vol_merge.setXYpos(extra_start_x, shuffle_y + 299)
            vol_merge.setInput(0, vol_direct_bottom_dot)
            vol_merge.setInput(1, vol_indirect_bottom_dot)

            vol_merge_input = vol_merge
        elif has_volume_direct:
            vol_shuffle = nuke.nodes.Shuffle(name='Volume_Direct', postage_stamp=True)
            vol_shuffle['in'].setValue('Volume_Direct')
            vol_shuffle.setXYpos(extra_start_x, shuffle_y + 3)
            vol_shuffle.setInput(0, volume_dot)
            vol_merge_input = vol_shuffle
        elif has_volume_indirect:
            vol_shuffle = nuke.nodes.Shuffle(name='Volume_Indirect', postage_stamp=True)
            vol_shuffle['in'].setValue('Volume_Indirect')
            vol_shuffle.setXYpos(extra_start_x, shuffle_y + 3)
            vol_shuffle.setInput(0, volume_dot)
            vol_merge_input = vol_shuffle

        volume_grade = nuke.nodes.Grade(name='Grade_volume')
        volume_grade.setXYpos(extra_start_x, shuffle_y + 1139)
        volume_grade.setInput(0, vol_merge_input)

        volume_merge = nuke.nodes.Merge2(operation='plus', name='Merge_volume')
        volume_merge.setXYpos(extra_start_x, read_y + 1974)
        volume_merge.setInput(1, volume_grade)

        extra_start_x += volume_backdrop_width + 20

    ungrouped_channels = [c for c in chan_list if c not in used_channels and c != 'rgba' and c != 'Ambient_Occlusion']

    if ungrouped_channels:
        prev_dot = None
        for i, channel_name in enumerate(ungrouped_channels):
            x_pos = extra_start_x + (i * dot_spacing)

            dot_node = nuke.nodes.Dot(note_font_size=35)
            dot_node.setXYpos(x_pos + 34, dot_y)

            if i == 0:
                dot_node.setInput(0, last_dot_node)
            else:
                dot_node.setInput(0, prev_dot)

            prev_dot = dot_node
            last_dot_node = dot_node

            shuffle_node = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle_node['in'].setValue(channel_name)
            shuffle_node.setXYpos(x_pos, shuffle_y)
            shuffle_node.setInput(0, dot_node)

    first_light_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 231, ypos=read_y + 1977)

    if len(light_group_outputs) > 0:
        final_merge_y = read_y + 1974
        final_merge_x = read_x + 1174

        prev_merge = None
        for i, output_node in enumerate(light_group_outputs):
            if i == 0:
                prev_merge = first_light_dot
                first_light_dot.setInput(0, output_node)
            else:
                final_merge = nuke.nodes.Merge2(operation='plus', name=f'Final_Merge_{i-1}')
                final_merge.setXYpos(final_merge_x, final_merge_y)
                final_merge.setInput(0, prev_merge)
                final_merge.setInput(1, output_node)
                prev_merge = final_merge
                final_merge_x += group_spacing

        if emission_merge is not None and prev_merge is not None:
            emission_merge.setInput(0, prev_merge)

        if environment_merge is not None and emission_merge is not None:
            environment_merge.setInput(0, emission_merge)
        elif environment_merge is not None and prev_merge is not None:
            environment_merge.setInput(0, prev_merge)

        if volume_merge is not None and environment_merge is not None:
            volume_merge.setInput(0, environment_merge)
        elif volume_merge is not None and emission_merge is not None:
            volume_merge.setInput(0, emission_merge)
        elif volume_merge is not None and prev_merge is not None:
            volume_merge.setInput(0, prev_merge)

        last_chain_node = None
        last_chain_x = read_x + 231

        if volume_merge is not None:
            last_chain_node = volume_merge
            last_chain_x = volume_x
        elif environment_merge is not None:
            last_chain_node = environment_merge
            last_chain_x = extra_start_x - 257
        elif emission_merge is not None:
            last_chain_node = emission_merge
            last_chain_x = extra_start_x - 257
        elif prev_merge is not None:
            last_chain_node = prev_merge
            last_chain_x = read_x + 231

        if last_chain_node is not None:
            copy_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 34, ypos=final_merge_y + 146)
            copy_dot.setInput(0, read_dot)

            copy_node = nuke.nodes.Copy(name='Copy_alpha')
            copy_node['from0'].setValue('rgba.alpha')
            copy_node['to0'].setValue('rgba.alpha')
            copy_node.setXYpos(last_chain_x, final_merge_y + 137)
            copy_node.setInput(0, last_chain_node)
            copy_node.setInput(1, copy_dot)

            premult_node = nuke.nodes.Premult(name='Premult_all')
            premult_node['channels'].setValue('all')
            premult_node.setXYpos(last_chain_x, final_merge_y + 280)
            premult_node.setInput(0, copy_node)

            if 'Ambient_Occlusion' in chan_list:
                ao_x = extra_start_x
                if has_volume_direct and has_volume_indirect:
                    ao_x = extra_start_x + dot_spacing

                ao_top_dot = nuke.nodes.Dot(note_font_size=35)
                ao_top_dot.setXYpos(ao_x + dot_spacing - 100, dot_y)
                ao_top_dot.setInput(0, last_dot_node)
                last_dot_node = ao_top_dot

                ao_shuffle = nuke.nodes.Shuffle(name='Ambient_Occlusion', postage_stamp=True)
                ao_shuffle['in'].setValue('Ambient_Occlusion')
                ao_shuffle.setXYpos(ao_x + dot_spacing - 134, shuffle_y)
                ao_shuffle.setInput(0, ao_top_dot)

                ao_bottom_dot = nuke.nodes.Dot(note_font_size=35)
                ao_bottom_dot.setXYpos(ao_x + dot_spacing - 100, final_merge_y + 423)
                ao_bottom_dot.setInput(0, ao_shuffle)

                ao_merge = nuke.nodes.Merge2(operation='multiply', name='Merge_Ambient_Occlusion')
                ao_merge.setXYpos(last_chain_x, final_merge_y + 420)
                ao_merge.setInput(0, premult_node)
                ao_merge.setInput(1, ao_bottom_dot)

    nuke.message(f"已创建Blender Cycles预合成组")


if __name__ == '__main__':
    createAutoPrecomp()
