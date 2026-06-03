# A 股成长股每日研究报告 — CCR Routine Prompt

## 任务
读取 GitHub repo 中的缓存数据文件，生成 A 股成长股日报，通过 Gmail MCP 发送 HTML 草稿到 samzheng321@gmail.com。

## 第一步：拉取最新数据

```bash
cd /path/to/a-share-research   # 替换为本地 repo 路径
git pull origin main
```

## 第二步：读取以下文件

| 文件 | 用途 |
|------|------|
| `data/market/market_state.json` | 市场状态、CSI300 Stage 2、北向资金信号 |
| `data/market/north_flow.json` | 北向资金原始数据（近5日） |
| `data/screener_results.json` | 筛选结果，按 CANSLIM 评分排序 |
| `data/stocks/{CODE}_fund.json` | 各股基本面（营收增速、ROE、是否ST等） |
| `data/stocks/{CODE}_tech.json` | 各股技术面（Minervini 评分、RS、买点距离等） |

## 第三步：生成 HTML 报告

报告结构（全中文）：

### 1. 今日市场状态
- 日期
- 沪深300 Stage 2：是/否
- 市场状态：**可以新开仓** 或 **保持现金优先**
- 北向资金（5日）：净流入/净流出 X 亿元（信号：strong_inflow / mild_outflow 等）
- 涨停/跌停家数

### 2. 铁律核查总表

| # | 规则 | 状态 |
|---|------|------|
| ① | 沪深300 处于 Stage 2 | ✅/⛔ |
| ② | 个股 Minervini ≥ 6/7 | 每股单独显示 |
| ③ | 买点 +3% 内不追（距 60日高点 ≤ +3%） | 每股单独显示 |
| ④ | 止损 -8%，T+1 生效（次日起有效） | ✅ 恒定提示 |
| ⑤ | 非 ST 股 + 基本面不弱（营收未大幅负增长） | 每股单独显示 |

铁律全部通过 → 标 ✅ 可关注；任一未通过 → 标 ⛔ 不入场。

### 3. 候选股清单（Top 10，按 CANSLIM 评分排序）

每只股票显示一行：
- 股票名称（代码）
- CANSLIM 评分 / 10
- Minervini X/7
- RS vs 沪深300（3个月超跑 %）
- 距52周高点 %
- 营收同比增速 %
- 铁律状态 ✅/⛔

### 4. 重点候选股详情（仅铁律全过的股票，最多3只）

每只股票展开一个小卡片：
- 基本面：营收增速、净利润增速、ROE、PE、市值
- 技术面：Minervini 7条逐条 ✅/❌、RS vs CSI300、距买点 %
- CANSLIM 各项得分说明
- 操作提示：建议关注价位（距60日高点-3%到+3%区间），止损价（当前价 × 0.92，T+1生效）

### 5. 北向资金额外详情

近5日北向资金净流向逐日列表。

---

## 第四步：发送 Gmail 草稿

使用 Gmail MCP 工具创建草稿：
- 收件人：samzheng321@gmail.com
- 主题：`A股日报 {日期} | 市场{可入场/现金优先} | {✅候选数}只候选`
- 正文：上面生成的 HTML 报告

## 注意事项
- 如果 `market_status = CASH_PRIORITY`（CSI300 非 Stage 2），在报告顶部用红色大字提示"⛔ 大盘非 Stage 2，暂停新开仓"
- ST 股（`is_st = true`）直接跳过，不进入详情
- 铁律③（买点距离）：`pct_from_pivot` 为 null 时标"待确认"，不算铁律未过
- 所有百分比保留1位小数
