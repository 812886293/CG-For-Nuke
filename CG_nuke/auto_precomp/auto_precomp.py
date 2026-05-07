# -*- coding: utf-8 -*-
"""
Nuke插件：自动预合成脚本

功能说明：
    这是一个AOV（Arbitrary Output Variables）自动预合成工具，用于将多灯光渲染输出的
    AOV通道（如 coat_default、diffuse_env、specular_env 等）自动分组并创建预合成节点网络。

使用前提：
    1. 在Nuke中选中一个带有AOV通道的Read节点
    2. AOV命名格式应为：{层类型}_{灯光名称}，例如 coat_default、diffuse_env


支持的AOV层类型：
    diffuse（漫反射）、specular（高光反射）、coat（涂层）、
    transmission（透射）、sss（次表面散射）、volume（体积）、
    emission（自发光）、background（背景）、indirect（间接光照）、
    direct（直接光照）
"""

import nuke

def createAutoPrecomp():
    """
    自动检测渲染器类型并调用相应的预合成函数
    - 如果通道中包含caustics，则调用Redshift预合成
    - 否则调用Arnold预合成
    """
    # 检查是否有节点被选中
    if not nuke.selectedNodes():
        nuke.message("请先选中一个节点")
        return

    # 获取选中的单个节点
    sel = nuke.selectedNode()

    # 获取该节点的所有通道
    channels = sel.channels()
    chan_list = []

    # 提取通道名称（去重）
    for channel in channels:
        channel_name = channel.split('.')[0]
        if channel_name not in chan_list:
            chan_list.append(channel_name)

    # 检查是否找到通道
    if not chan_list:
        nuke.message("未找到任何通道")
        return

    # 检查是否存在caustics通道（Redshift特有）
    has_caustics = any('caustics' in c.lower() for c in chan_list)

    if has_caustics:
        createRedshiftPrecomp()
    else:
        # 调用Arnold预合成
        createArnoldPrecomp()


def createArnoldPrecomp():
    """
    主函数：创建自动预合成节点网络

    工作流程：
        1. 获取用户选中的节点及其所有通道
        2. 解析通道名称，按灯光组分组建AOV
        3. 为每个灯光组创建独立的节点网络（Backdrop + Dot + Shuffle + Merge）
        4. 特殊处理emission和volume通道
        5. 创建最终的合并链
        6. 显示完成消息

    注意事项：
        - 必须选中一个节点才能执行
        - 节点必须包含AOV通道
        - 通道命名格式：{层类型}_{灯光名称}
    """
    # 检查是否有节点被选中
    if not nuke.selectedNodes():
        nuke.message("请先选中一个节点")
        return

    # 获取选中的单个节点
    sel = nuke.selectedNode()

    # 获取该节点的所有通道
    # channels()返回格式如：['diffuse_light1.red', 'diffuse_light1.green', ...]
    channels = sel.channels()
    chan_list = []

    # 提取通道名称（去重）
    # 通道名格式为 "layer_name"，如 "diffuse_env"
    for channel in channels:
        # 按 '.' 分割，取第一部分作为通道名
        channel_name = channel.split('.')[0]
        if channel_name not in chan_list:
            chan_list.append(channel_name)

    # 检查是否找到通道
    if not chan_list:
        nuke.message("未找到任何通道")
        return

    # 定义标准AOV层类型列表
    # 这些是常见的渲染层类型，用于识别通道的前缀
    standard_aov_layers = [
        'diffuse', 'specular', 'coat', 'transmission', 'sss',
        'volume', 'emission', 'background', 'indirect', 'direct'
    ]

    # 用于存储按灯光分组的AOV通道
    # 字典结构：{灯光名称: {层类型: 完整通道名}}
    # 例如：{'default': {'coat': 'coat_default', 'diffuse': 'diffuse_default'}, 'env': {...}}
    light_aov_groups = {}

    # 用于存储无法归类的通道（如不符合命名规则的通道）
    ungrouped_channels = []

    # 检查是否存在emission和volume通道（特殊处理）
    has_emission = 'emission' in chan_list
    has_volume = 'volume' in chan_list

    # 遍历所有通道，按命名规则分组
    for channel_name in chan_list:
        # 按 '_' 分割通道名
        # 例如 "coat_env" 分割为 ['coat', 'env']，"diffuse_default" 分割为 ['diffuse', 'default']
        parts = channel_name.split('_')

        # 如果通道名包含至少两个部分（符合命名规则）
        if len(parts) >= 2:
            # 第一部分为AOV层类型，转小写以便匹配
            aov_layer = parts[0].lower()
            # 剩余部分用 '_' 连接作为灯光名称
            light_aov = '_'.join(parts[1:])

            # 检查是否为标准AOV层类型
            if aov_layer in standard_aov_layers:
                # 如果该灯光名称尚未在字典中，创建新的子字典
                if light_aov not in light_aov_groups:
                    light_aov_groups[light_aov] = {}
                # 将该层类型添加到对应灯光组
                light_aov_groups[light_aov][aov_layer] = channel_name
            else:
                # 不是标准层类型，添加到未分组列表
                ungrouped_channels.append(channel_name)
        else:
            # 通道名不符合命名规则，添加到未分组列表
            ungrouped_channels.append(channel_name)

    # 从未分组通道中移除emission和volume（这两个会特殊处理）
    ungrouped_channels = [c for c in ungrouped_channels if c not in ['emission', 'volume']]

    # 获取选中节点的坐标位置
    read_x = int(sel.xpos())
    read_y = int(sel.ypos())

    # 计算节点布局的Y坐标（基于new.txt的精确参数）
    # Dot节点位于Read节点下方442像素
    dot_y = read_y + 442
    # Shuffle节点位于Dot节点下方70像素
    shuffle_y = dot_y + 70

    # 节点间距参数
    dot_spacing = 197      # 同一灯光组内Dot节点的水平间距
    group_spacing = 977     # 不同灯光组之间的水平间距

    # 定义层的合并顺序（从前往后合并）
    merge_order = ['coat', 'diffuse', 'specular', 'sss', 'transmission']

    # 用于跟踪最后一个创建的Dot节点（用于连接后续节点）
    last_dot_node = None
    # 存储每个灯光组的最终输出节点（用于最终合并）
    group_outputs = []
    # 存储灯光组输出（仅用于最终合并，不包含emission和volume）
    light_group_outputs = []
    # 存储volume节点的X位置（用于创建Copy节点）
    volume_x = None

    # 创建Read节点下方的第一个Dot节点（Dot74）
    # 这个Dot是整个网络的起点，连接Read节点
    read_dot = nuke.nodes.Dot(note_font_size=35)
    read_dot.setXYpos(read_x + 34, dot_y)  # X偏移34像素
    read_dot.setInput(0, sel)  # 连接到选中的Read节点
    last_dot_node = read_dot  # 更新最后的Dot节点引用

    # 对灯光组进行排序，确保输出顺序一致
    sorted_lights = sorted(light_aov_groups.keys())

    # 遍历每个灯光组，创建独立的预合成网络
    for idx, light_aov in enumerate(sorted_lights):
        # 获取该灯光组包含的所有AOV通道
        aov_channels = light_aov_groups[light_aov]
        # 获取该灯光组存在的层类型（按照merge_order顺序）
        present_layers = [layer for layer in merge_order if layer in aov_channels]

        # 计算该灯光组的第一个Dot的X位置
        # 公式：Read.x + 34（第一个偏移）+ 197（第一个Dot的偏移）+ 组号 * 组间距
        first_dot_x = read_x + 34 + 197 + (idx * group_spacing)
        # Shuffle的X位置（在对应Dot左边34像素）
        shuffle_start_x = first_dot_x - 34

        # 创建Backdrop背景节点（用于标识灯光组的绿色背景框）
        backdrop = nuke.nodes.BackdropNode(
            name=f'Backdrop_{light_aov}',
            label=light_aov,  # 显示灯光组名称
            tile_color=int('0x71c67100', 16),  # 绿色背景
            note_font_size=120,  # 标签字体大小
            xpos=shuffle_start_x - 10,
            ypos=dot_y - 74,
            bdwidth=888,   # Backdrop宽度
            bdheight=1376  # Backdrop高度
        )

        # 创建顶部Dot节点链（横向排列）
        top_dots = []

        # 创建第一个Dot，连接到上一个灯光组的最后一个Dot
        first_dot = nuke.nodes.Dot(note_font_size=35)
        first_dot.setXYpos(first_dot_x, dot_y)
        first_dot.setInput(0, last_dot_node)  # 连接上一个节点
        top_dots.append(first_dot)
        last_dot_node = first_dot  # 更新最后的Dot节点引用

        # 创建后续的Dot节点（在同一水平线上横向排列）
        for i in range(1, len(present_layers)):
            dot = nuke.nodes.Dot(note_font_size=35)
            dot.setXYpos(first_dot_x + (i * dot_spacing), dot_y)
            dot.setInput(0, top_dots[i-1])  # 连接到前一个Dot
            top_dots.append(dot)
            last_dot_node = dot

        # 创建Shuffle节点（用于分离各个AOV通道）
        shuffle_nodes = {}
        bottom_dots = {}

        # 遍历该灯光组存在的每个AOV层
        for i, aov_layer in enumerate(present_layers):
            channel_name = aov_channels[aov_layer]
            # Shuffle节点的X位置
            shuffle_x = shuffle_start_x + (i * dot_spacing)
            # 下方Dot的X位置
            bottom_dot_x = first_dot_x + (i * dot_spacing)

            # 创建Shuffle节点，设置输入通道
            shuffle = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle['in'].setValue(channel_name)  # 设置输入通道
            shuffle.setXYpos(shuffle_x, shuffle_y)
            shuffle.setInput(0, top_dots[i])  # 连接到上方的Dot
            shuffle_nodes[aov_layer] = shuffle

            # 底部Dot的Y偏移（每个层有不同的偏移量）
            y_offsets = [299, 302, 528, 845, 1159]
            bottom_dot = nuke.nodes.Dot(note_font_size=35)
            bottom_dot.setXYpos(bottom_dot_x, shuffle_y + y_offsets[i])
            bottom_dot.setInput(0, shuffle)  # 连接到Shuffle节点
            bottom_dots[aov_layer] = bottom_dot

        # 创建Merge节点（垂直堆叠，依次合并各层）
        merge_y_offsets = [299, 525, 842, 1156]

        prev_merge = None
        for i, aov_layer in enumerate(present_layers):
            if i == 0:
                # 第一个层，直接连接到对应的bottom_dot
                prev_merge = bottom_dots[aov_layer]
            else:
                # 后续层，使用Merge2节点（operation='plus'表示相加）进行合并
                merge = nuke.nodes.Merge2(operation='plus')
                merge.setXYpos(shuffle_start_x, shuffle_y + merge_y_offsets[i-1])
                merge.setInput(0, prev_merge)  # 连接到之前合并的结果
                merge.setInput(1, bottom_dots[aov_layer])  # 连接当前层
                prev_merge = merge

        # 将该灯光组的最终输出添加到列表
        group_outputs.append(prev_merge)
        light_group_outputs.append(prev_merge)

    # ==================== 处理emission（自发光） ====================
    if has_emission:
        # emission的位置：位于最后一个灯光组之后
        emission_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34 + 107
        emission_dot_x = emission_shuffle_x + 34

        # 创建青色Backdrop（用于标识emission区域）
        nuke.nodes.BackdropNode(
            name='BackdropNode_emission',
            label='Emission',
            tile_color=int('0x388e8e00', 16),  # 青色背景
            note_font_size=42,
            xpos=emission_shuffle_x - 40,
            ypos=dot_y - 71,
            bdwidth=223,
            bdheight=1367
        )

        # 创建Dot节点
        emission_dot = nuke.nodes.Dot(note_font_size=35)
        emission_dot.setXYpos(emission_dot_x, dot_y)
        emission_dot.setInput(0, last_dot_node)
        last_dot_node = emission_dot

        # 创建Shuffle节点，分离emission通道
        emission_shuffle = nuke.nodes.Shuffle(name='emission', postage_stamp=True)
        emission_shuffle['in'].setValue('emission')
        emission_shuffle.setXYpos(emission_shuffle_x, shuffle_y + 6)
        emission_shuffle.setInput(0, emission_dot)

        # 创建Grade节点（用于调整emission的色调/亮度）
        emission_grade = nuke.nodes.Grade(name='Grade_emission')
        emission_grade.setXYpos(emission_shuffle_x, shuffle_y + 1137)
        emission_grade.setInput(0, emission_shuffle)

        # 创建Merge节点，将emission添加到主合并链
        emission_merge = nuke.nodes.Merge2(operation='plus', name='Merge_emission')
        emission_merge.setXYpos(emission_shuffle_x, read_y + 1974)
        emission_merge.setInput(1, emission_grade)

        group_outputs.append(emission_merge)

    # ==================== 处理volume（体积） ====================
    if has_volume:
        # volume的位置：位于emission之后（如果有emission）
        if has_emission:
            volume_shuffle_x = emission_shuffle_x + 257
        else:
            volume_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        volume_dot_x = volume_shuffle_x + 34
        volume_x = volume_shuffle_x

        # 创建青色Backdrop
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

        # 创建Dot节点
        volume_dot = nuke.nodes.Dot(note_font_size=35)
        volume_dot.setXYpos(volume_dot_x, dot_y)
        volume_dot.setInput(0, last_dot_node)
        last_dot_node = volume_dot

        # 创建Shuffle节点
        volume_shuffle = nuke.nodes.Shuffle(name='volume', postage_stamp=True)
        volume_shuffle['in'].setValue('volume')
        volume_shuffle.setXYpos(volume_shuffle_x, shuffle_y + 3)
        volume_shuffle.setInput(0, volume_dot)

        # 创建Grade节点
        volume_grade = nuke.nodes.Grade(name='Grade_volume')
        volume_grade.setXYpos(volume_shuffle_x, shuffle_y + 1139)
        volume_grade.setInput(0, volume_shuffle)

        # 创建Merge节点
        volume_merge = nuke.nodes.Merge2(operation='plus', name='Merge_volume')
        volume_merge.setXYpos(volume_shuffle_x, read_y + 1974)
        volume_merge.setInput(1, volume_grade)

        group_outputs.append(volume_merge)

    # ==================== 处理未分组通道 ====================
        if ungrouped_channels:
            # 计算额外通道的起始X位置
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

            # 创建Dot节点
            dot_node = nuke.nodes.Dot(note_font_size=35)
            dot_node.setXYpos(x_pos + 34, dot_y)

            # 连接Dot节点
            if i == 0:
                dot_node.setInput(0, last_dot_node)
            else:
                dot_node.setInput(0, prev_dot)

            prev_dot = dot_node
            last_dot_node = dot_node

            # 创建Shuffle节点
            shuffle_node = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle_node['in'].setValue(channel_name)
            shuffle_node.setXYpos(x_pos, shuffle_y)
            shuffle_node.setInput(0, dot_node)


    #创建第一个灯光组的输出dot节点
    first_light_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 231, ypos=read_y + 1977  )
    
    # ==================== 最终合并链 ====================
    # 只合并灯光组的输出，不包含emission和volume 
    if len(light_group_outputs) > 1:
        # 计算最终Merge节点的Y位置
        final_merge_y = read_y + 1974
        # X位置为第一个灯光组的Shuffle位置
        final_merge_x = read_x + 1174

        # 依次合并所有灯光组的输出（需要 n-1 个 Merge 节点）
        prev_merge = None
        for i, output_node in enumerate(light_group_outputs):
            if i == 0:
                # 第一个灯光组的输出dot节点
                prev_merge = first_light_dot 
                # 连接第一个灯光组的输出dot节点到主合并链
                first_light_dot.setInput(0, output_node)  
            
            else: 
                # 索引从 0 开始，确保有 n-1 个 Merge 节点（索引 0 到 n-2）
                final_merge = nuke.nodes.Merge2(operation='plus', name=f'Final_Merge_{i-1}')
                final_merge.setXYpos(final_merge_x, final_merge_y)
                final_merge.setInput(0, prev_merge)
                final_merge.setInput(1, output_node)
                prev_merge = final_merge
                final_merge_x += 977  # 每个最终Merge节点偏移977像素

        
        #创建copy_dot节点
        copy_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 34, ypos=final_merge_y + 146)
        copy_dot.setInput(0, read_dot) 


        # 如果存在volume，创建Copy节点处理alpha通道
        if has_volume and volume_x is not None:
            copy_node = nuke.nodes.Copy(name='Copy_alpha')
            copy_node['from0'].setValue('rgba.alpha')  # 设置源通道
            copy_node['to0'].setValue('rgba.alpha')    # 设置目标通道
            copy_node.setXYpos(volume_x, final_merge_y + 137)
            copy_node.setInput(0, volume_merge) 
            copy_node.setInput(1, copy_dot)
        
        #连接emission_merge到prev_merge（灯光合并链的最后一个Merge节点）
        emission_merge.setInput(0, prev_merge)
        #
        volume_merge.setInput(0, emission_merge)

    # 显示完成消息
    nuke.message(f"已创建 {len(light_aov_groups)} 个灯光AOV预合成组")

def createRedshiftPrecomp():
    """
    主函数：为Redshift渲染器创建AOV自动预合成节点网络

    工作流程：
        1. 获取用户选中的节点及其所有通道
        2. 解析通道名称，识别Redshift AOV类型
        3. 为每个AOV类型创建独立的节点网络（Backdrop + Dot + Shuffle + Merge）
        4. 特殊处理emission和volume通道
        5. 创建最终的合并链
        6. 显示完成消息

    Redshift标准AOV层类型：
        DiffuseLighting、Reflections、SpecularLighting、Refractions、SSS、GI
    """
    # 检查是否有节点被选中
    if not nuke.selectedNodes():
        nuke.message("请先选中一个节点")
        return

    # 获取选中的单个节点
    sel = nuke.selectedNode()

    # 获取该节点的所有通道
    channels = sel.channels()
    chan_list = []

    # 提取通道名称（去重）
    for channel in channels:
        channel_name = channel.split('.')[0]
        if channel_name not in chan_list:
            chan_list.append(channel_name)

    # 检查是否找到通道
    if not chan_list:
        nuke.message("未找到任何通道")
        return

    # Redshift标准AOV层类型列表（支持大小写混合）
    redshift_aov_layers = [
        'DiffuseLighting', 'Reflections', 'SpecularLighting',
        'Refractions', 'SSS', 'GI', 'Emission', 'Volume'
    ]

    # 用于存储按灯光分组的AOV通道
    light_aov_groups = {}
    # 用于存储无法归类的通道
    ungrouped_channels = []

    # 检查是否存在emission、volume和caustics通道（特殊处理）
    has_emission = any('emission' in c.lower() for c in chan_list)
    has_volume = any('volume' in c.lower() for c in chan_list)
    has_caustics = any('caustics' in c.lower() for c in chan_list)

    # 遍历所有通道，按命名规则分组
    for channel_name in chan_list:
        # 检查是否为标准Redshift AOV类型
        matched = False
        
        for aov_layer in redshift_aov_layers:
            if channel_name.startswith(aov_layer):
                # 提取灯光名称（如果存在）
                if len(channel_name) > len(aov_layer):
                    light_name = channel_name[len(aov_layer):]
                    # 处理下划线分隔的情况
                    if light_name.startswith('_'):
                        light_name = light_name[1:]
                    # 只有当灯光名称非空时才创建灯光组
                    if light_name:
                        if light_name not in light_aov_groups:
                            light_aov_groups[light_name] = {}
                        light_aov_groups[light_name][aov_layer] = channel_name
                        matched = True
                        break
        
        if not matched:
            ungrouped_channels.append(channel_name)

    # 从未分组通道中移除emission和volume（这两个会特殊处理）
    ungrouped_channels = [c for c in ungrouped_channels 
                          if 'emission' not in c.lower() and 'volume' not in c.lower()]

    # 获取选中节点的坐标位置
    read_x = int(sel.xpos())
    read_y = int(sel.ypos())

    # 计算节点布局的Y坐标
    dot_y = read_y + 442
    shuffle_y = dot_y + 70

    # 节点间距参数 - 增加group_spacing避免backdrop重叠
    dot_spacing = 197
    group_spacing = 1150

    # 定义层的合并顺序（从前往后合并）
    merge_order = ['DiffuseLighting', 'SSS', 'Reflections', 'SpecularLighting', 'Refractions', 'GI']

    # 用于跟踪最后一个创建的Dot节点
    last_dot_node = None
    # 存储每个灯光组的最终输出节点
    group_outputs = []
    light_group_outputs = []
    # 存储volume和caustics节点的X位置
    volume_x = None
    caustics_x = None

    # 创建Read节点下方的第一个Dot节点
    read_dot = nuke.nodes.Dot(note_font_size=35)
    read_dot.setXYpos(read_x + 34, dot_y)
    read_dot.setInput(0, sel)
    last_dot_node = read_dot

    # 对灯光组进行排序
    sorted_lights = sorted(light_aov_groups.keys())

    # 遍历每个灯光组，创建独立的预合成网络
    for idx, light_aov in enumerate(sorted_lights):
        aov_channels = light_aov_groups[light_aov]
        present_layers = [layer for layer in merge_order if layer in aov_channels]

        # 计算该灯光组的第一个Dot的X位置
        first_dot_x = read_x + 34 + 197 + (idx * group_spacing)
        shuffle_start_x = first_dot_x - 34

        # 创建Backdrop背景节点（绿色背景框）- 支持6个AOV，增加高度
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

        # 创建顶部Dot节点链
        top_dots = []

        # 创建第一个Dot
        first_dot = nuke.nodes.Dot(note_font_size=35)
        first_dot.setXYpos(first_dot_x, dot_y)
        first_dot.setInput(0, last_dot_node)
        top_dots.append(first_dot)
        last_dot_node = first_dot

        # 创建后续的Dot节点
        for i in range(1, len(present_layers)):
            dot = nuke.nodes.Dot(note_font_size=35)
            dot.setXYpos(first_dot_x + (i * dot_spacing), dot_y)
            dot.setInput(0, top_dots[i-1])
            top_dots.append(dot)
            last_dot_node = dot

        # 创建Shuffle节点
        shuffle_nodes = {}
        bottom_dots = {}

        # 遍历该灯光组存在的每个AOV层
        for i, aov_layer in enumerate(present_layers):
            channel_name = aov_channels[aov_layer]
            shuffle_x = shuffle_start_x + (i * dot_spacing)
            bottom_dot_x = first_dot_x + (i * dot_spacing)

            # 创建Shuffle节点
            shuffle = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle['in'].setValue(channel_name)
            shuffle.setXYpos(shuffle_x, shuffle_y)
            shuffle.setInput(0, top_dots[i])
            shuffle_nodes[aov_layer] = shuffle

            # 第一个AOV层不创建bottom_dot，其他层创建
            if i > 0:
                # 底部Dot的Y偏移 - 6个AOV层
                y_offsets = [299, 302, 528, 845, 1159, 1473]
                bottom_dot = nuke.nodes.Dot(note_font_size=35)
                bottom_dot.setXYpos(bottom_dot_x, shuffle_y + y_offsets[i])
                bottom_dot.setInput(0, shuffle)
                bottom_dots[aov_layer] = bottom_dot

        # 创建Merge节点（垂直堆叠）- 6个AOV需要5个Merge
        merge_y_offsets = [299, 525, 842, 1156, 1473]

        prev_merge = None
        for i, aov_layer in enumerate(present_layers):
            if i == 0:
                # 第一个层直接使用shuffle节点，不经过dot
                prev_merge = shuffle_nodes[aov_layer]
            else:
                merge = nuke.nodes.Merge2(operation='plus')
                merge.setXYpos(shuffle_start_x, shuffle_y + merge_y_offsets[i-1])
                merge.setInput(0, prev_merge)
                merge.setInput(1, bottom_dots[aov_layer])
                prev_merge = merge

        # 将该灯光组的最终输出添加到列表
        group_outputs.append(prev_merge)
        light_group_outputs.append(prev_merge)

    # ==================== 处理Emission（自发光） ====================
    emission_merge = None
    if has_emission:
        emission_channel = next(c for c in chan_list if 'emission' in c.lower())
        emission_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34 + 107
        emission_dot_x = emission_shuffle_x + 34

        # 创建青色Backdrop
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

        # 创建Dot节点
        emission_dot = nuke.nodes.Dot(note_font_size=35)
        emission_dot.setXYpos(emission_dot_x, dot_y)
        emission_dot.setInput(0, last_dot_node)
        last_dot_node = emission_dot

        # 创建Shuffle节点
        emission_shuffle = nuke.nodes.Shuffle(name=emission_channel, postage_stamp=True)
        emission_shuffle['in'].setValue(emission_channel)
        emission_shuffle.setXYpos(emission_shuffle_x, shuffle_y + 6)
        emission_shuffle.setInput(0, emission_dot)

        # 创建Grade节点
        emission_grade = nuke.nodes.Grade(name='Grade_emission')
        emission_grade.setXYpos(emission_shuffle_x, shuffle_y + 1137)
        emission_grade.setInput(0, emission_shuffle)

        # 创建Merge节点 - 向下移动
        emission_merge = nuke.nodes.Merge2(operation='plus', name='Merge_emission')
        emission_merge.setXYpos(emission_shuffle_x, read_y + 2180)
        emission_merge.setInput(1, emission_grade)

        group_outputs.append(emission_merge)

    # ==================== 处理Volume（体积） ====================
    volume_merge = None
    if has_volume:
        volume_channel = next(c for c in chan_list if 'volume' in c.lower())
        if has_emission:
            volume_shuffle_x = emission_shuffle_x + 257
        else:
            volume_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        volume_dot_x = volume_shuffle_x + 34
        volume_x = volume_shuffle_x

        # 创建青色Backdrop
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

        # 创建Dot节点
        volume_dot = nuke.nodes.Dot(note_font_size=35)
        volume_dot.setXYpos(volume_dot_x, dot_y)
        volume_dot.setInput(0, last_dot_node)
        last_dot_node = volume_dot

        # 创建Shuffle节点
        volume_shuffle = nuke.nodes.Shuffle(name=volume_channel, postage_stamp=True)
        volume_shuffle['in'].setValue(volume_channel)
        volume_shuffle.setXYpos(volume_shuffle_x, shuffle_y + 3)
        volume_shuffle.setInput(0, volume_dot)

        # 创建Grade节点
        volume_grade = nuke.nodes.Grade(name='Grade_volume')
        volume_grade.setXYpos(volume_shuffle_x, shuffle_y + 1139)
        volume_grade.setInput(0, volume_shuffle)

        # 创建Merge节点 - 向下移动
        volume_merge = nuke.nodes.Merge2(operation='plus', name='Merge_volume')
        volume_merge.setXYpos(volume_shuffle_x, read_y + 2180)
        volume_merge.setInput(1, volume_grade)

        group_outputs.append(volume_merge)

    # ==================== 处理Caustics（焦散） ====================
    caustics_merge = None
    if has_caustics:
        caustics_channel = next(c for c in chan_list if 'caustics' in c.lower())
        
        # Caustics的位置：位于volume之后（如果有volume）
        if has_volume:
            caustics_shuffle_x = volume_shuffle_x + 257
        elif has_emission:
            caustics_shuffle_x = emission_shuffle_x + 257
        else:
            caustics_shuffle_x = read_x + 34 + 197 + (len(sorted_lights) * group_spacing) - 34

        caustics_dot_x = caustics_shuffle_x + 34
        caustics_x = caustics_shuffle_x

        # 创建青色Backdrop
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

        # 创建Dot节点
        caustics_dot = nuke.nodes.Dot(note_font_size=35)
        caustics_dot.setXYpos(caustics_dot_x, dot_y)
        caustics_dot.setInput(0, last_dot_node)
        last_dot_node = caustics_dot

        # 创建Shuffle节点
        caustics_shuffle = nuke.nodes.Shuffle(name=caustics_channel, postage_stamp=True)
        caustics_shuffle['in'].setValue(caustics_channel)
        caustics_shuffle.setXYpos(caustics_shuffle_x, shuffle_y + 3)
        caustics_shuffle.setInput(0, caustics_dot)

        # 创建Grade节点
        caustics_grade = nuke.nodes.Grade(name='Grade_caustics')
        caustics_grade.setXYpos(caustics_shuffle_x, shuffle_y + 1139)
        caustics_grade.setInput(0, caustics_shuffle)

        # 创建Merge节点
        caustics_merge = nuke.nodes.Merge2(operation='plus', name='Merge_caustics')
        caustics_merge.setXYpos(caustics_shuffle_x, read_y + 2180)
        caustics_merge.setInput(1, caustics_grade)

        group_outputs.append(caustics_merge)

    # ==================== 处理未分组通道 ====================
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

            # 创建Dot节点
            dot_node = nuke.nodes.Dot(note_font_size=35)
            dot_node.setXYpos(x_pos + 34, dot_y)

            # 连接Dot节点
            if i == 0:
                dot_node.setInput(0, last_dot_node)
            else:
                dot_node.setInput(0, prev_dot)

            prev_dot = dot_node
            last_dot_node = dot_node

            # 创建Shuffle节点
            shuffle_node = nuke.nodes.Shuffle(name=channel_name, postage_stamp=True)
            shuffle_node['in'].setValue(channel_name)
            shuffle_node.setXYpos(x_pos, shuffle_y)
            shuffle_node.setInput(0, dot_node)

    # 创建第一个灯光组的输出dot节点 - 向下移动
    first_light_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 231, ypos=read_y + 2200)

    # ==================== 最终合并链 ====================
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
                final_merge_x += 1150 # 每个最终Merge节点偏移1150像素

        # 创建copy_dot节点
        copy_dot = nuke.nodes.Dot(note_font_size=35, xpos=read_x + 34, ypos=final_merge_y + 146)
        copy_dot.setInput(0, read_dot)

        # 如果存在caustics，创建Copy节点处理alpha通道
        if has_caustics and caustics_x is not None and caustics_merge is not None:
            copy_node = nuke.nodes.Copy(name='Copy_alpha')
            copy_node['from0'].setValue('rgba.alpha')
            copy_node['to0'].setValue('rgba.alpha')
            copy_node.setXYpos(caustics_x, final_merge_y + 137)
            copy_node.setInput(0, caustics_merge)
            copy_node.setInput(1, copy_dot)

        # 连接emission_merge到prev_merge
        if emission_merge is not None and prev_merge is not None:
            emission_merge.setInput(0, prev_merge)

        # 连接volume_merge到emission_merge
        if volume_merge is not None and emission_merge is not None:
            volume_merge.setInput(0, emission_merge)
        elif volume_merge is not None and prev_merge is not None:
            volume_merge.setInput(0, prev_merge)

        # 连接caustics_merge到emission_merge或volume_merge
        if caustics_merge is not None and emission_merge is not None:
            caustics_merge.setInput(0, emission_merge)
        elif caustics_merge is not None and volume_merge is not None:
            caustics_merge.setInput(0, volume_merge)
        elif caustics_merge is not None and prev_merge is not None:
            caustics_merge.setInput(0, prev_merge)

    # 显示完成消息
    nuke.message(f"已创建 {len(light_aov_groups)} 个Redshift AOV预合成组")

if __name__ == '__main__':
    # 直接运行脚本时执行主函数
    createAutoPrecomp()
