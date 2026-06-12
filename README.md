# gupiao — Claude Code A股股票分析 Skill

实时行情、技术指标、综合评分、走势预测、操作建议。

## 安装

### 1. 环境要求

- Python 3.10+
- Claude Code

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

> `curl_cffi` 安装遇到问题时：macOS → `brew install curl-cffi`；Linux → 参考 [curl_cffi](https://github.com/lexiforest/curl_cffi)

### 3. 安装 Skill

```bash
mkdir -p ~/.claude/skills
cp -r . ~/.claude/skills/gupiao
```

或者克隆仓库直接安装：

```bash
git clone https://github.com/CrownTsui/gupiao-skill.git ~/.claude/skills/gupiao
cd ~/.claude/skills/gupiao && pip install -r requirements.txt
```

### 4. 配置自选股（可选）

编辑 `~/.claude/skills/gupiao/stocks.json`：

```json
{
  "watchlist": ["000001", "600519", "300750"]
}
```

## 使用

在 Claude Code 中：

```
/gupiao 600519          # 分析单只股票
/gupiao --all           # 批量分析全部自选股
/gupiao --backtest      # 回测模式
```

自然语言触发词：`分析股票` `看下这只票` `复盘` `大盘` `gupiao` + 股票代码。

## 输出

- 终端卡片报告（stdout 原文呈现）
- HTML 报告保存到 `~/Downloads/gupiao/<日期>/`

## 文件结构

| 文件 | 用途 |
|------|------|
| `SKILL.md` | Skill 定义（Claude Code 读取入口） |
| `stock_analyzer.py` | 分析引擎：行情拉取、技术指标计算、综合评分 |
| `stock_report.py` | 报告生成：HTML / 终端卡片 / 纯文本 / 回测 |
| `stocks.json` | 默认自选股列表 |
| `requirements.txt` | Python 依赖 |

## 数据源

内置三源容错：东方财富 API → 新浪 API → 本地缓存。无需网络搜索，运行时自动取得实时行情。

## 免责声明

数据仅供参考，不构成投资建议。股市有风险，投资需谨慎。
