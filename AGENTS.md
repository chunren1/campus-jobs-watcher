# AGENTS.md — campus-jobs-watcher

## 概述

- 27 届 SRE / 运维 / DevOps 岗秋招监控脚本（MVP），单个 Python 文件，无框架无 Web 服务。
- 每天抓取 xixicc2027 README 表格 → 关键词/城市过滤 → 输出 `jobs.md` + `jobs.csv`，并 SMTP 发送邮件日报。
- 抓取或邮件失败一律降级（内置 6 条种子兜底 / 跳过发信），脚本始终 exit 0，零运维。

## 技术栈与版本

- Python 3（本机 3.14.4；CI 固定 `3.12`，见 `.github/workflows/daily.yml:20`）。代码用 PEP 585 内建泛型注解（`list`），需 3.9+。
- 零必装依赖：只用标准库 urllib / smtplib / csv / email / re。`requirements.txt` 里 requests、pyyaml 两行均为注释（可选增强）。
- CI：GitHub Actions `ubuntu-latest`，cron `0 0 * * *`（= 08:00 CST）+ `workflow_dispatch` 手动触发。
- 无测试框架、无 lint 配置、无打包流程。

## 常用命令

以下命令原样来自 README，无脚本封装：

```bash
cd /home/user/projects/campus-jobs-watcher
python watcher.py                       # README.md:17-18

# 带邮件发送（README.md:25-29）
export SMTP_HOST="smtp.qq.com" SMTP_PORT="465"
export SMTP_USER="you@qq.com" SMTP_PASS="<授权码，不是登录密码>"
export MAIL_TO="you@qq.com"             # 可选 MAIL_FROM="备注名<you@qq.com>"
python watcher.py
```

- 测试 / 构建 / lint：无（项目无这些命令，勿编造）。

## 目录结构

```
watcher.py                       # 全部逻辑：配置→抓取→解析→过滤→输出→邮件
config.yaml                      # 关键词 / 城市 / 数据源 / 输出文件名
requirements.txt                 # 仅注释（可选依赖说明）
jobs.md                          # 产物：给人看的表格，按截止升序
jobs.csv                         # 产物：投递跟踪表（含 source 列）
.github/workflows/daily.yml      # 每日定时运行 + secrets 注入 + 回写仓库
```

## 项目规范与约定

- stdlib-first：可选库必须先 `try: import`，`ImportError` 时回落标准库分支（`watcher.py:141`、`watcher.py:170`）。
- 调整监控范围只改 `config.yaml`（keywords / cities / sources），不改代码；缺 pyyaml 时由内置极简解析器 `_manual_config_parse` 兜底。
- 日志一律 `print(..., flush=True)`，前缀固定 `[info]` / `[warn]` / `[ok]`，中文描述。
- 输出统一按 deadline 升序、无 deadline 排最后；城市过滤后为空时自动回退为不过滤，保证 `jobs.md` 非空。
- 种子 `SEEDS` 是兜底真值源：合并时种子优先，实时行按「公司 + 岗位前 30 字」判重。
- CSV 用 `utf-8-sig` 写入（Excel 友好）；MD 由 `write_md` 生成 markdown 表格。
- 提交信息遵循既有风格 `feat:` / `fix:` / `chore:`；CI 机器人身份 `jobs-bot`，提交信息 `chore: daily jobs update <date>`。
- 抓取源 / 表格结构 / 关键词相关改动需同步更新 README「配置」「容错说明」段落。

## 禁止

- 禁止在代码或 `config.yaml` 中硬编码 SMTP 账号密码、收件人；只走环境变量或 GitHub Secrets。
- 禁止让抓取、解析、发信异常抛出非零退出码（`main()` 必须 return 0）。
- 禁止手工编辑 `jobs.md` / `jobs.csv`：每次运行以 `"w"` 模式全量重写，手改必被覆盖。
- 禁止把口令类 secrets 写入 `jobs.md` / `jobs.csv` / 提交内容（历史曾强调「绝不硬编码密码」）。
- 非必要不引入第三方依赖——stdlib-first 是本项目的设计约束，要加先说明理由。

## 关键路径

- `watcher.py` — 全部逻辑所在（改行为基本只动这里）
- `config.yaml` — 监控范围（关键词/城市/数据源/输出名）
- `.github/workflows/daily.yml` — 定时、secrets 注入、产物回写
- `jobs.csv` — 投递跟踪产物（8 列，含 source）
- `README.md` — 部署步骤与 secrets 清单
