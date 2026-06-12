---
name: gupiao
description: A股股票技术分析——实时行情、技术指标、评分、走势预测、操作建议。触发词：股票/分析股票/看下这只票/复盘/大盘/gupiao + 6位股票代码。禁止 WebFetch。
---

# A股股票分析

## 工作流

### Step 1: 运行分析

```bash
python3 ~/.claude/skills/gupiao/stock_analyzer.py <CODE> 2>/dev/null
```

- 无参默认执行 `--all`（分析 stocks.json 中全部股票）
- 批量：`--all`；回测：`--backtest`
- 输出卡片报告到 stdout，**原文发回用户，不总结不截断**
- HTML 报告自动保存到 `~/Downloads/gupiao/<日期>/`

🔴 **CHECKPOINT** — 验证 stdout 包含"综合评分"。若只有 error → 跳到失败处理，**禁止自行分析**。

| 失败场景 | 处理 |
|----------|------|
| 脚本返回 error | 告知用户错误信息，禁止自行分析 |
| stocks.json 不存在 | 提示创建配置文件 |
| 数据源均失败 | 告知稍后重试 |

### Step 2: 本地桌面打开报告

```bash
open $(ls -t ~/Downloads/gupiao/$(date +%Y%m%d)/<CODE>_*.html 2>/dev/null | head -1)
```

非 macOS 跳过。

## 🔴 禁止事项

| ❌ 禁止 | ✅ 应该 |
|----------|--------|
| WebFetch/WebSearch 获取行情 | 脚本内置三源容错 |
| 不跑脚本，自己分析 | 必须执行 stock_analyzer.py |
| 只回复"报告已输出"不展示卡片 | stdout 原文呈现 |
| 总结、截断或改写卡片内容 | 原文直接发回 |

## 相关文件

| 文件 | 用途 |
|------|------|
| `stock_analyzer.py` | 分析引擎 + 回测 |
| `stock_report.py` | 报告生成（HTML/卡片/文本/回测） |
| `stocks.json` | 默认自选股列表 |
| `~/Downloads/gupiao/<日期>/` | 报告输出目录 |
