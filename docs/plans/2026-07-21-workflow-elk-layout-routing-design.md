# 工作流 ELK 自动布局与布线设计

## 目标

使用成熟布局引擎改善工作流模板和“整理布局”的节点排列、连接点选择、交叉数量与正交折线质量。自动布局结果必须显式保存后才写入数据库；未保存退出时恢复上次保存版本。

## 技术选择

引入 `elkjs`，使用 ELK Layered 算法。它适合具有主方向的节点流图，原生支持正交布线、端口、多重边、边标签和交叉最小化。ELK 在按需加载的 Web Worker 中运行，避免布局计算阻塞页面。

不在本阶段引入 Libavoid JavaScript 封装。其交互式固定节点布线能力适合后续评估，但当前可用封装较新，存在成熟度、WASM 和许可风险。

## ELK 输入与参数

- 活跃状态进入主 ELK 图，节点尺寸固定为 `118 x 42`。
- 停用状态不参与主图，按现有规则排列到独立区域。
- 同状态流转不进入 ELK 边，继续以节点角标显示。
- 每条非同状态流转建立唯一源端口和目标端口。
- 端口固定在主流程的右侧和左侧，并以稳定流转顺序排列。
- 边标签尺寸为 `80 x 26`，提供给 ELK 参与间距计算。

主要选项：

```text
elk.algorithm=layered
elk.direction=RIGHT
elk.edgeRouting=ORTHOGONAL
elk.portConstraints=FIXED_ORDER
elk.layered.crossingMinimization.strategy=LAYER_SWEEP
elk.layered.crossingMinimization.greedySwitch.type=TWO_SIDED
elk.layered.nodePlacement.strategy=BRANDES_KOEPF
elk.layered.nodePlacement.bk.edgeStraightening=IMPROVE_STRAIGHTNESS
elk.layered.spacing.nodeNodeBetweenLayers=180
elk.spacing.nodeNode=80
elk.spacing.edgeNode=24
elk.spacing.edgeEdge=16
```

## 自动生成路径

ELK 输出的端点和 bend points 转换为现有 `diagram_config`：

```json
{
  "version": 1,
  "routing_mode": "generated",
  "source_anchor": {"side": "right", "ratio": 0.5},
  "target_anchor": {"side": "left", "ratio": 0.5},
  "waypoints": []
}
```

转换时移除重复点和共线点，并验证全路径正交。超过 32 个中间点或输出不合法时，该边回退为现有自动路由，不阻止其他边使用 ELK 结果。

`generated` 属于自动布线：抽屉显示“自动布线”，不显示“恢复自动布线”。用户拖动端点或线段后转为 `manual`。后端接受 `manual` 和 `generated`，并执行相同的结构与正交校验。

## 整理与模板

点击“整理布局”后先确认，再调用 ELK。只有 ELK 完整成功后，才一次性替换节点坐标与自动生成路径；失败或超时时保持当前图不变并提示错误。

套用模板获取业务图后，同样运行 ELK 并一次性应用。手工路径仅在成功整理时被新自动路径替换。

## 节点拖拽

保留原子拖拽帧。拖拽期间忽略旧 `generated` 几何，使用最新节点坐标实时计算完整路由；`manual` 路径保留。松手时把最后一帧的非手工路径转换为新的 `generated` 配置，使画面结果与后续保存结果一致。

## 保存与离开

不进行实时保存。加载或成功保存后记录规范化图快照。节点拖拽、整理布局、路径编辑、增删状态和流转都会使当前图与快照不同。

- 点击“保存流程图”才写入数据库并更新快照。
- 路由切换、对象类型切换、刷新或关闭页面前，如果全图有未保存修改则提示。
- 用户确认离开时丢弃修改；取消则停留。
- 抽屉草稿确认与全图确认合并处理，避免连续弹出两个提示。

## 失败与性能

- ELK 模块和 Worker 按需加载。
- 布局设置超时，异常和超时都不部分应用结果。
- 同一时刻只接受最后一次整理请求，旧请求结果不得覆盖新图。
- 增加第三方许可声明。

## 验收标准

- 节点不重叠，主流程从左向右。
- 自动边正交、避开节点，连接点位于节点四边。
- 平行边端口分开，模板交叉数低于当前基线。
- 重复整理结果稳定。
- 保存刷新后位置和路径一致。
- 未保存退出后重新进入恢复上次保存版本。
- 拖拽每个可见帧中的节点、连接点和路径使用同一坐标快照。
