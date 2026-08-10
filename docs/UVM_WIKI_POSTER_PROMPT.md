# UVM Wiki 手绘介绍海报提示词

## 海报用途

用于技术汇报中介绍 **UVM Wiki 验证环境智能导读助手**。画面应让数字验证工程师快速理解：工具对 SystemVerilog/UVM 工程进行一次静态解析，同时生成面向 AI 的结构化索引和面向工程师的交互式知识图谱。

## Gemini Banana 主提示词

请生成一张 **横版 16:9、高清、手绘技术信息图风格**的中文海报，主题为：

> **UVM Wiki 验证环境智能导读助手**<br>
> 一次解析，同时服务 AI 与验证工程师

整体采用专业、清晰、克制的手绘白板风格。背景为浅色纸张纹理，使用黑色手绘线条，搭配蓝色、绿色、橙色和少量红色作为功能区分。线条自然但不潦草，文字端正易读，结构像优秀工程师在白板上绘制的系统架构图。不要使用卡通人物，不要使用机器人头像，不要使用夸张的科幻装饰。

### 画面主体

画面从左到右表现一条完整工作流：

```text
SystemVerilog / UVM 工程
          ↓
    UVM Wiki 静态解析
       ↙         ↘
uvm_wiki_ai.json  uvm_wiki.html
       ↓               ↓
 AI 快速理解       工程师交互阅读
```
### 左侧：工程输入

绘制一组手绘代码文件和文件夹，标题为 **SystemVerilog / UVM 工程**。

包含两个输入入口：

- **工程目录**：递归扫描 `.sv / .svh / .v / .vh`
- **Filelist**：读取 `-f`、include path、define 和编译文件范围

在文件旁边用小标签标注：

- test
- env
- agent
- sequence
- interface
- package

### 中间：解析引擎

绘制一个醒目的手绘处理模块，标题为 **UVM Wiki 静态解析引擎**。

模块内部包含：

- **pyslang parser**
- **light parser**
- **增量缓存**
- **文件与行号定位**

在模块下方增加一句小字：

> 静态索引，不替代仿真器编译与 elaboration

### 中部下方：简化 UVM 架构

用嵌套方框画出一套典型 UVM 验证环境：

```text
uvm_test
└── env
    ├── agent
    │   ├── sequencer
    │   ├── driver ─────→ DUT interface
    │   └── monitor
    ├── scoreboard
    └── coverage
```

使用清晰箭头表现：

- sequencer → driver：seq item connection
- monitor → scoreboard：analysis TLM connection
- monitor → coverage：analysis TLM connection

连接线旁标注 **port / export / imp / connect**。层次关系使用实线边框，TLM 数据流使用彩色箭头，避免线条交叉和堆叠。

### 右上：面向 AI 的输出

绘制一张结构化 JSON 文档，文件名清晰显示为：

> **uvm_wiki_ai.json**

文档周围标注其包含的信息：

- class 与继承关系
- component topology
- TLM ports 与 connections
- UVM phase
- 文件与行号

从 JSON 指向一个简洁的 AI 对话框，文字为：

> 先查结构索引，再按需读取源码

旁边突出两个收益：

- **减少重复 grep**
- **降低上下文与 Token 消耗**

### 右下：面向工程师的输出

绘制一个简洁的浏览器窗口，文件名显示为：

> **uvm_wiki.html**

窗口内用小型缩略图表现以下页面：

- Architecture
- Topology
- Class Hierarchy
- TLM Connections
- Phase Map
- Wiki Graph
- Code Explorer

突出三项交互能力：

- 点击节点查看关系
- 点击 port 或连线定位 connect
- 跳转到对应源码和行号

### 底部能力条

在海报底部放置一条简洁的手绘能力总结：

> **完全离线 · 项目级安装 · 支持 pyslang / light 双模式 · 单文件 HTML · 源码只读浏览**

## 视觉要求

- 横版 16:9，适合插入 PPT、周报或技术汇报。
- 信息层级明确，中心解析引擎最醒目，左右输入输出关系清楚。
- 使用手绘矩形、文件页、箭头和少量荧光笔底色。
- 保持足够留白，不要把所有文字挤在一起。
- UVM 层次图和 TLM 箭头必须逻辑正确，箭头方向清晰。
- 中文使用简体中文，英文技术名词保持原样。
- 不要生成无法辨认的伪文字，不要增加未提供的产品名称或公司名称。
- 不要出现厂商 Logo、芯片 Logo、机器人、人物头像或装饰性 3D 元素。
- 整体风格接近专业工程白板、手绘架构图和技术笔记，不要做成营销广告。

## 建议保留的海报文字

```text
UVM Wiki 验证环境智能导读助手
一次解析，同时服务 AI 与验证工程师

SystemVerilog / UVM 工程
UVM Wiki 静态解析引擎
uvm_wiki_ai.json
uvm_wiki.html

减少重复 grep
降低上下文与 Token 消耗
快速理解 UVM 架构与 TLM 数据流
点击图谱，定位源码

完全离线 · 项目级安装 · 双解析模式 · 源码只读浏览
```

## 负面提示词

```text
避免写实人物，避免机器人，避免赛博朋克，避免深色背景，避免复杂渐变，
避免密集小字，避免箭头交叉，避免错误的 UVM 层次，避免无意义伪代码，
避免无法辨认的中文，避免厂商名称和 Logo，避免夸张宣传语，避免 3D 渲染。
```
