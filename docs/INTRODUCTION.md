# UVM 验证环境智能导读工具

## 工具定位

面向 SystemVerilog/UVM 工程的静态代码导读工具。一次解析代码后，同时生成面向智能体的结构化索引和面向工程师的交互页面，减少重复搜索代码的时间。

> 图片占位：工具整体界面

## 核心输出

### `uvm_wiki_ai.json`

保存 class、继承、成员、组件创建、TLM port、connect、phase、文件和行号等信息。智能体可先查询索引，再按需读取少量源码。

### `uvm_wiki.html`

单文件离线页面，集中展示：

- UVM Architecture
- Topology
- Class Hierarchy
- TLM Connections
- Phase Map
- Wiki Graph
- Code Explorer

> 图片占位：Architecture 页面

## 主要能力

- 识别 test、env、agent、driver、sequencer、monitor、scoreboard 等组件。
- 展示组件实例层次和 class 继承关系。
- 展示 seq item 与 analysis TLM 连接，并定位 connect 代码。
- 在实例创建位置和类型定义位置之间切换。
- 点击图中节点、port、连线或 phase，跳转到对应源码。
- 支持目录扫描和工程 filelist 两种输入方式。
- 支持 light parser 与 pyslang，适配完全离线环境。

> 图片占位：Topology 与 Class Hierarchy

> 图片占位：TLM Connections

> 图片占位：源码跳转

## 使用流程

```text
SystemVerilog/UVM 源码或 filelist
              ↓
       UVM Wiki 静态解析
              ↓
   uvm_wiki_ai.json + uvm_wiki.html
              ↓
      智能体查询 + 工程师浏览
```

## Filelist 支持

目录模式适合快速扫描完整代码树；filelist 模式更接近工程实际编译范围，可读取嵌套 `-f`、include 路径、宏定义和工程内头文件。

工具进行静态解析，不替代仿真器编译和 elaboration。factory override、动态实例数量和运行期 config-db 结果仍需结合仿真信息确认。

## 脱敏示例

项目提供 `examples/demo_uvm`，包含完整的最小 UVM 数据通路和嵌套 filelist，可用于内网安装检查、界面演示和文档截图。

> 图片占位：脱敏示例生成结果

## 当前状态

- 已支持 Linux x86_64、Python 3.11 完全离线部署。
- pyslang、D3.js 和许可证文件随工具打包。
- 输出可供 Codex 复用，也可由验证工程师直接浏览。
