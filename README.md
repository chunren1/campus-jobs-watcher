# campus-jobs-watcher 🎯 27届 SRE / 运维岗秋招监控（MVP）

每天自动抓取 27 届 SRE / 运维 / DevOps 相关秋招信息，按**截止时间排序**输出，
并通过邮件推送。网络失败自动降级为内置数据，零运维。

## 功能

- 实时抓取 [`xixicc2027`](https://github.com/xixicc186/xixicc2027) README 表格，关键词过滤
- 抓不到 → 内置 6 条真实种子兜底（携程 SRE / 招银网络科技 / 建信金科 / 招行智能运维 / 北森 / 平安银行）
- 输出 `jobs.md`（阅读）+ `jobs.csv`（投递跟踪），按 deadline 升序
- SMTP 发邮件日报；本地无 secrets 时自动跳过
- GitHub Actions 每天 08:00（CST）自动运行 + 回写仓库

## 本地运行

```bash
cd /home/user/projects/campus-jobs-watcher
python watcher.py        # 仅标准库即可跑；有 requests/pyyaml 会自动用
```

产物：`jobs.md`、`jobs.csv`。

带邮件的本地运行：

```bash
export SMTP_HOST="smtp.qq.com" SMTP_PORT="465"
export SMTP_USER="you@qq.com" SMTP_PASS="<授权码，不是登录密码>"
export MAIL_TO="you@qq.com"   # 可选: MAIL_FROM="备注名<you@qq.com>"
python watcher.py
```

> 常见邮箱 SMTP：QQ `smtp.qq.com:465`（授权码在 账户-安全-授权码 开）；
> 163 `smtp.163.com:465`；Gmail `smtp.gmail.com:587`（需应用专用密码）。

## 配置（config.yaml）

```yaml
keywords: [SRE, 运维, DevOps, 系统工程师, 云平台, 智能运维, 应用运维, ...]
cities: [深圳, 杭州, 成都, 上海, 北京, 武汉]  # [] = 不限
sources: [xixicc2027 README raw 链接...]
```

- 加关键词/城市：改 `config.yaml` 即可，不用碰代码
- 城市过滤太严导致为空时，脚本自动回退为不过滤，保证 `jobs.md` 非空

## GitHub Actions + 邮件（零运维）步骤

1. 新建 GitHub 仓库，把本目录 4 个文件推上去：
   `watcher.py`、`config.yaml`、`.github/workflows/daily.yml`、`README.md`
2. 仓库页 → **Settings → Secrets and variables → Actions → New repository secret**，逐个添加：
   | Secret 名 | 示例值 | 说明 |
   |---|---|---|
   | `SMTP_HOST` | `smtp.qq.com` | 邮箱 SMTP 服务器 |
   | `SMTP_PORT` | `465` | QQ/163 用 465；Gmail 用 587 |
   | `SMTP_USER` | `you@qq.com` | 发件邮箱 |
   | `SMTP_PASS` | `<授权码>` | QQ/163/163 的授权码，不是登录密码 |
   | `MAIL_TO` | `you@qq.com` | 收件邮箱（自己的邮箱） |
   | `MAIL_FROM` | （可选） | 留空则等于 SMTP_USER |
3. **Actions → daily-jobs → Run workflow** 手动触发一次验证：
   - 日志出现 `[ok] 输出 ... 共 N 条` + `[info] 邮件已发送至 ...` 即成功
   - 去收件箱查收 `[27届SRE/运维秋招]` 日报
4. 之后每天 08:00 自动运行，`jobs.md`/`jobs.csv` 自动 commit 回仓库。

## 容错说明

- 抓取源连不上 / 表格结构变化 / SMTP 没配 → 只打 `[warn]` 日志，脚本 **exit 0**
- Actions 里 `pip install -r requirements.txt` 失败也继续（stdlib 兜底）
- 绝不在代码里硬编码密码：全部走环境变量 / GitHub Secrets

## 求职备忘（SRE/运维开发，民办本科突围要点）

- CET4 425+ 是银行科技子（建信金科等）硬门槛，先保证达标
- 主攻：Linux + Python/Go + Docker/K8s + 监控自动化；每项都要有可演示项目
- 银行系（招银网络/建信金科/招行/平安）对学历相对友好 + HC 大，优先海投
