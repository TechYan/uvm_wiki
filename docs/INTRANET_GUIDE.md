# UVM Wiki 内网使用指南

## 1. 适用范围

UVM Wiki 用于静态索引 SystemVerilog/UVM 工程，输出：

- `uvm_wiki_ai.json`：供大模型快速查询代码结构。
- `uvm_wiki.html`：供验证工程师浏览架构、继承、Topology、TLM 连接和源码。

工具支持两种输入方式：

| 输入方式 | 行为 | 适用场景 |
| --- | --- | --- |
| `--src` | 递归扫描目录中的 `.sv/.svh/.svp/.v/.vh/.inc/.svi/.pkg` | 代码目录较干净，或者没有维护 filelist |
| `--filelist` | 只索引 filelist 中的源文件及工程内 `` `include`` 文件 | 工程较大，希望结果与实际编译清单一致 |

> UVM Wiki 是静态代码索引工具，不替代仿真器编译和 elaboration。pyslang 用于逐文件语法解析；filelist 用于确定文件范围、include 路径和宏定义。

## 2. 环境与依赖

内网离线包当前面向以下环境：

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Linux x86_64 |
| Python | CPython 3.11，已验证 3.11.10 |
| glibc | 2.27 或更高 |
| 浏览器 | Chrome、Edge 或其他现代浏览器 |
| 网络 | 不需要 |
| root 权限 | 不需要 |

工具依赖：

| 依赖 | 用途 | 是否已打包 |
| --- | --- | --- |
| Python 标准库 | 扫描、索引、HTTP 服务 | 系统 Python 自带 |
| pyslang 11.0.0 | SystemVerilog 语法树解析 | 已提供 Linux CPython 3.11 wheel |
| D3.js 7.9.0 | HTML 图形展示 | 已嵌入 Skill，不访问 CDN |
| Codex | 使用 JSON 索引辅助代码理解 | 按内网环境单独部署 |

不依赖 Graphviz、Node.js、数据库或外部 Web 服务。
仅使用 `--parser light` 时不需要安装任何第三方 Python 库；pyslang 是推荐的增强解析能力。

## 3. 离线安装

### 3.1 校验并解压交付包

将压缩包和 `.sha256` 文件放在同一目录：

```bash
sha256sum -c uvm-wiki-offline-linux-x86_64-py311.tar.gz.sha256

mkdir -p "$HOME/uvm-wiki-package"
tar -xzf uvm-wiki-offline-linux-x86_64-py311.tar.gz \
  -C "$HOME/uvm-wiki-package"

export UVM_WIKI_PACKAGE="$HOME/uvm-wiki-package"
```

将 Skill 复制到个人目录：

```bash
mkdir -p ~/.codex/skills
cp -a "$UVM_WIKI_PACKAGE/uvm-wiki" ~/.codex/skills/
export UVM_WIKI_HOME="$HOME/.codex/skills/uvm-wiki"
```

### 3.2 不安装 pyslang

light parser 只依赖 Python 标准库，可直接运行：

```bash
export UVM_WIKI_PY="$(command -v python3.11)"
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" doctor
```

构建时指定 `--parser light`。

### 3.3 安装离线 pyslang

如需增强语法解析，在个人目录创建虚拟环境并安装已打包的 wheel：

```bash
python3.11 ~/.codex/skills/uvm-wiki/scripts/install_offline.py
```

默认安装位置：

```text
~/.local/share/uvm-wiki/venv
```

如需指定个人安装目录：

```bash
python3.11 ~/.codex/skills/uvm-wiki/scripts/install_offline.py \
  --venv "$HOME/tools/uvm-wiki-venv"
```

检查环境：

```bash
~/.local/share/uvm-wiki/venv/bin/python \
  ~/.codex/skills/uvm-wiki/scripts/uvm_wiki.py doctor
```

正常结果应包含：

```text
Input modes: directory, filelist
Parser light: light
Parser auto: pyslang
Parser pyslang: pyslang (available)
```

安装完成后设置 Python 路径：

```bash
export UVM_WIKI_PY="$HOME/.local/share/uvm-wiki/venv/bin/python"
```

## 4. 先运行脱敏示例

仓库中的 `examples/demo_uvm` 是一个不含项目和协议信息的最小 UVM 环境，包含：

- test、env、agent、driver、sequencer、monitor
- scoreboard、coverage、sequence、sequence item
- seq item 连接和 analysis TLM 连接
- interface、DUT、config-db 和 phase 方法
- 顶层 filelist 与嵌套 `-f` filelist

运行示例：

```bash
mkdir -p "$HOME/uvm_wiki_output/demo"

"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" build \
  --src "$UVM_WIKI_PACKAGE/examples/demo_uvm" \
  --filelist "$UVM_WIKI_PACKAGE/examples/demo_uvm/filelist.f" \
  --parser auto \
  --out "$HOME/uvm_wiki_output/demo"
```

参考结果：15 个文件、11 个 class、3 条 TLM/seq item 连接。

## 5. 索引实际工程

### 5.1 目录扫描模式

```bash
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" build \
  --src /project/uvc \
  --parser auto \
  --out "$HOME/uvm_wiki_output/uvc"
```

目录模式会递归读取 `--src` 下的 `.sv`、`.svh`、`.svp`、`.v`、`.vh`、`.inc`、`.svi`、`.pkg`，并跳过 `.git`、`node_modules`、`__pycache__` 等目录。

### 5.2 Filelist 模式

推荐同时指定 `--src` 和 `--filelist`：

```bash
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" build \
  --src /project \
  --filelist /project/sim/filelist.f \
  --parser auto \
  --out "$HOME/uvm_wiki_output/project"
```

- `--filelist` 决定哪些编译单元进入索引。
- `--src` 是源码相对路径和浏览服务的安全边界。
- filelist 未指定 `--src` 时，工具会根据 filelist 目录和源文件计算公共工程根目录。
- filelist 中超出 `--src` 的源文件会直接报错，不会静默忽略。

可重复传入多个顶层 filelist：

```bash
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" build \
  --src /project \
  --filelist /project/sim/rtl.f \
  --filelist /project/sim/tb.f \
  --parser auto \
  --out "$HOME/uvm_wiki_output/project"
```

当前支持的 filelist 写法：

| 写法 | 支持情况 |
| --- | --- |
| `path/to/file.sv` | 支持 |
| `-f nested.f`、`-F nested.f` | 支持嵌套和循环检测 |
| `+incdir+dir1+dir2` | 支持 |
| `-I dir`、`-Idir` | 支持 |
| `+define+NAME+WIDTH=16` | 支持 |
| `-DNAME`、`-DNAME=VALUE` | 支持 |
| `-v library_file.v` | 支持显式库文件 |
| `#`、`//` 注释 | 支持 |
| 行末 `\` 续行 | 支持 |
| `$VAR`、`${VAR}`、`~` | 支持环境变量和用户目录展开 |

filelist 文本支持 UTF-8、GB18030/GBK 和 Latin-1 编码。

`-y`、`+libext+`、`-top`、`-timescale` 等仿真器选项不会参与静态索引，会记录在 `metadata.input.ignored_options` 中。工程内可解析的 `` `include`` 文件会自动加入索引；支持字面量文件名、对象宏和常见 stringify 宏包装。查找顺序为当前源码目录、`+incdir`/`-I`、filelist 所在目录和 `--src`。UVM 库本身不会被复制进工程索引。

构建结束时会打印 include 统计。完整诊断保存在 `uvm_wiki_ai.json` 的 `metadata.input.unresolved_includes`、`outside_root_includes` 和 `warnings` 中。越过 `--src` 的 include 不会静默忽略；需要扩大 `--src` 后重新构建。

### 5.3 Parser 模式

| 参数 | 行为 |
| --- | --- |
| `--parser auto` | 优先使用 pyslang，不可用时使用 light parser |
| `--parser pyslang` | 要求 pyslang 可用；单个异常文件可记录后回退 light parser |
| `--parser light` | 只使用 Python 标准库，适合最受限环境 |

pyslang 会使用 filelist 中解析到的 include 路径和宏定义，但当前仍按文件建立语法树。工具不会执行仿真器的 package 编译、factory override、elaboration 或 UVM runtime phase。

## 6. 输出文件

指定输出目录后会生成：

```text
output/
├── uvm_wiki_ai.json
├── uvm_wiki.html
└── .cache/
    └── parse_cache.json
```

- `uvm_wiki_ai.json`：符号、继承、成员、实例创建、TLM、phase、文件和行号。
- `uvm_wiki.html`：单文件交互界面，内置 D3.js，可离线打开。
- `.cache/parse_cache.json`：增量缓存。重复运行时只重新解析变化文件。

强制完整重建：

```bash
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" build \
  --src /project \
  --filelist /project/sim/filelist.f \
  --parser auto \
  --out "$HOME/uvm_wiki_output/project" \
  --rebuild
```

## 7. 打开和启动界面

### 7.1 直接打开 HTML

直接打开 `uvm_wiki.html` 可以查看图谱和已嵌入的代码片段：

```bash
xdg-open "$HOME/uvm_wiki_output/project/uvm_wiki.html"
```

### 7.2 启动完整源码浏览服务

前台启动：

```bash
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" serve \
  --src /project \
  --filelist /project/sim/filelist.f \
  --parser auto \
  --out "$HOME/uvm_wiki_output/project" \
  --port 8765
```

浏览器打开：

```text
http://127.0.0.1:8765/
```

如果 `uvm_wiki.html` 和 `uvm_wiki_ai.json` 已经生成，可以跳过扫描和解析，直接启动完整源码阅读与全文检索服务：

```bash
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" serve-existing \
  --src /project \
  --out "$HOME/uvm_wiki_output/project" \
  --port 8765
```

`serve-existing` 不需要 `--filelist`、`--parser` 或 pyslang。`--src` 仍然必须指向原工程源码根目录，它同时是完整源码读取和全文检索的安全边界。

后台启动：

```bash
OUT="$HOME/uvm_wiki_output/project"
mkdir -p "$OUT"

nohup "$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" serve \
  --src /project \
  --filelist /project/sim/filelist.f \
  --parser auto \
  --out "$OUT" \
  --port 8765 \
  > "$OUT/server.log" 2>&1 &

echo $! > "$OUT/server.pid"
```

检查服务：

```bash
curl http://127.0.0.1:8765/api/status
```

停止服务：

```bash
kill "$(cat "$HOME/uvm_wiki_output/project/server.pid")"
```

服务只允许绑定 `127.0.0.1`、`localhost` 或 `::1`。如端口被占用，改用 `--port 8766` 等其他端口。

## 8. 给 Codex 使用

推荐让智能体优先读取 `uvm_wiki_ai.json`，再按文件和行号读取少量源码。例如：

```text
使用 UVM Wiki Skill。先读取 /path/to/uvm_wiki_ai.json，说明 test 到 agent 的组件层次、
driver 与 sequencer 的连接，以及 monitor 数据最终送到哪些组件。仅在需要确认实现细节时读取对应源码。
```

处理较大的 JSON 时，不建议一次把全部内容放入模型上下文。优先查询：

1. `metadata` 和 `stats`
2. `uvm_architecture`
3. `tlm.connections`
4. `hierarchies`
5. 目标 class 对应的 `symbols` 和 `relations`

## 9. 脱敏与安全

- 源码不会上传到网络。
- HTTP 服务为只读并仅绑定本机回环地址。
- `--src` 限制源码读取边界，拒绝 `..` 路径穿越。
- HTML 默认嵌入有限代码片段；对外传递结果时可使用 `--no-source`。
- JSON 和 HTML 仍会包含 class 名、相对路径、行号及工程根路径。跨项目传递前应检查这些内容。
- pyslang 安装在个人虚拟环境，不修改系统 Python。

不在 HTML 中嵌入源码片段：

```bash
"$UVM_WIKI_PY" "$UVM_WIKI_HOME/scripts/uvm_wiki.py" build \
  --src /project \
  --filelist /project/sim/filelist.f \
  --parser auto \
  --out "$HOME/uvm_wiki_output/project" \
  --no-source
```

## 10. 常见问题

### pyslang unavailable

重新运行离线安装脚本并执行 `doctor`。临时使用时可指定 `--parser light`。

### filelist 报源文件不存在

工具按“当前 filelist 所在目录”解析相对路径。检查嵌套 filelist 中的相对路径和环境变量是否正确。

### 图中缺少 runtime 实例

UVM Wiki 基于静态源码。factory override、条件 build、循环创建数量和最终 config-db 结果需要结合仿真日志确认。

如果 factory create 带有 parent 参数，但目标 class 定义没有进入索引，Architecture 和 Topology 都会分别显示每条静态实例证据，不再按相同 type 合并；Topology 中同一父组件下的多个同类型实例也会保留为独立节点。大型工程采用按需展开：先在 Topology 搜索框中查找 test、env 或 agent，通过下拉框设为根节点，再点击卡片右侧的 `+` 逐层展开；单个场景有节点数量上限，达到上限后可把更深层组件设为新根节点。`Back`、`Focus selected`、`Collapse`、`Fit` 和 `Reset view` 用于切换和整理视图。点击节点还会跳到各自的 create 语句。右侧 Related 区域可以按 `creates`、`has_member`、`extends` 等 relation 类型筛选并搜索。优先检查构建日志以及 `metadata.input.unresolved_includes`；这通常表示 package 引入的 VIP 文件没有被找到或超出了 `--src`。

### TLM 连接缺失

确认连接使用标准 `.connect(...)` 形式，并检查 `uvm_wiki_ai.json` 中的 `metadata.input.warnings`。宏封装或运行期动态连接可能无法完整恢复。

### 完整源码搜索范围与 filelist 不同

图谱和 JSON 只使用 filelist 选中的文件。serve 模式的全文搜索以 `--src` 为安全边界，可以搜索该目录中的其他 HDL 文件。

## 11. 交付检查

- `doctor` 显示目标 Python 和 parser 状态正常。
- 脱敏示例可分别用 `light` 和 `pyslang` 生成结果。
- 第二次运行显示 `reparsed=0`。
- `uvm_wiki.html` 的 Architecture、Topology、Class Hierarchy、TLM Connections、Phase Map、Wiki Graph、Code Explorer 可打开。
- serve 模式能够查看完整源码，且不能读取 `--src` 之外的文件。
- 交付目录中包含 wheel、校验和、D3.js 及第三方许可证。
