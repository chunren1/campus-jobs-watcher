#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""campus-jobs-watcher: 27届 SRE/运维岗 MVP 监控脚本（stdlib-first）.

用法: python watcher.py
产出: jobs.md + jobs.csv（按截止时间升序，越紧急越靠前）
邮件: 仅当 SMTP_HOST/SMTP_USER/SMTP_PASS/MAIL_TO 齐全才发送，否则跳过。
容错: 任何网络/解析失败 -> 用内置 SEEDS 兜底，exit 0。
"""
import csv
import datetime as dt
import os
import re
import smtplib
import sys
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

# ---------------------------------------------------------------- seeds
# 字段: company / position / cities / deadline / headcount / requirement / link
SEEDS = [
    {
        "company": "携程",
        "position": "SRE（2027秋招）",
        "cities": "上海",
        "deadline": "2026-12-31",
        "start": "2026-08-24",
        "headcount": "多名",
        "requirement": "本科及以上；Java/Python/Go 任一 + Linux + Docker/K8s 基础",
        "link": "https://ctrip.zhaopin.com/",
        "source": "seed",
    },
    {
        "company": "招银网络科技",
        "position": "运维研发",
        "cities": "深圳，杭州，成都",
        "deadline": "2026-11-30",
        "start": "",
        "headcount": "150人",
        "requirement": "本科及以上 STEM 相关专业；Linux/Python/自动化运维方向优先",
        "link": "https://cmbnt.zhaopin.com/",
        "source": "seed",
    },
    {
        "company": "建信金科",
        "position": "运维岗（系统运维/应用运维方向）",
        "cities": "上海，北京，武汉，成都",
        "deadline": "2026-10-08",
        "start": "",
        "headcount": "30人",
        "requirement": "本科及以上；CET4 425+；Linux/数据库/云原生基础",
        "link": "https://career.ccbft.com/",
        "source": "seed",
    },
    {
        "company": "招商银行",
        "position": "智能运维方向（总行信息技术部）",
        "cities": "深圳，上海",
        "deadline": "2026-10-31",
        "start": "",
        "headcount": "多名",
        "requirement": "本科及以上；Python/Go + 监控/自动化/智能运维/AIOps 方向优先",
        "link": "https://career.cmbchina.com/",
        "source": "seed",
    },
    {
        "company": "北森",
        "position": "应用运维工程师",
        "cities": "北京",
        "deadline": "2026-11-15",
        "start": "",
        "headcount": "多名",
        "requirement": "本科及以上；Linux/Java 应用运维 / 云平台（SaaS）运维基础",
        "link": "https://www.beisen.com/careers",
        "source": "seed",
    },
    {
        "company": "平安银行",
        "position": "运维开发工程师",
        "cities": "深圳，上海",
        "deadline": "2026-10-25",
        "start": "",
        "headcount": "多名",
        "requirement": "本科及以上；Python/Go + DevOps 工具链 / 运维开发经验优先",
        "link": "https://job.pingan.com/",
        "source": "seed",
    },
]

DEFAULT_KEYWORDS = ["SRE", "运维", "DevOps", "系统工程师", "云平台",
                    "智能运维", "应用运维", "运维开发", "运维研发"]
DEFAULT_CITIES: list = []
DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/xixicc186/xixicc2027/main/README.md",
    "https://raw.githubusercontent.com/xixicc186/xixicc2027/master/README.md",
]


# ---------------------------------------------------------------- config
def _manual_config_parse(text):
    """极简 YAML 子集解析（无 pyyaml 时的兜底）：只解析 keywords/cities/sources 列表与标量."""
    cfg = {"keywords": [], "cities": [], "sources": [],
           "email": {}, "output": {}, "fetch_timeout_sec": 15}
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^(keywords|cities|sources)\s*:", line):
            cur = re.match(r"^(\w+)", line).group(1)
            inline = re.search(r"\[(.*)\]", line)
            if inline and inline.group(1).strip():
                cfg[cur] = [s.strip().strip("'\"") for s in inline.group(1).split(",")]
            else:
                cfg[cur] = []
            continue
        if re.match(r"^\w.*:\s*$", line):
            cur = None
            continue
        m = re.match(r'^-\s*["\']?(.*?)["\']?\s*$', line)
        if m and cur in ("keywords", "cities", "sources"):
            cfg[cur].append(m.group(1))
    return cfg


def load_config():
    cfg = {"keywords": list(DEFAULT_KEYWORDS), "cities": list(DEFAULT_CITIES),
           "sources": list(DEFAULT_SOURCES), "email": {"subject_prefix": "[27届SRE/运维秋招]"},
           "output": {"md": "jobs.md", "csv": "jobs.csv"}, "fetch_timeout_sec": 15}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"[warn] {CONFIG_PATH} 不存在，使用默认配置", flush=True)
        return cfg
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        if isinstance(data.get("keywords"), list) and data["keywords"]:
            cfg["keywords"] = [str(k) for k in data["keywords"]]
        if isinstance(data.get("cities"), list):
            cfg["cities"] = [str(c) for c in data["cities"]]
        if isinstance(data.get("sources"), list) and data["sources"]:
            cfg["sources"] = [str(s) for s in data["sources"]]
        if isinstance(data.get("email"), dict):
            cfg["email"].update(data["email"])
        if isinstance(data.get("output"), dict):
            cfg["output"].update(data["output"])
        if data.get("fetch_timeout_sec"):
            cfg["fetch_timeout_sec"] = int(data["fetch_timeout_sec"])
        print("[info] config.yaml 加载成功 (pyyaml)", flush=True)
    except ImportError:
        manual = _manual_config_parse(text)
        for k in ("keywords", "cities", "sources"):
            if manual.get(k):
                cfg[k] = manual[k]
        print("[info] pyyaml 不可用，已用内置解析器加载 config.yaml", flush=True)
    except Exception as e:  # YAML 写坏也不崩
        print(f"[warn] config 解析失败 ({e})，使用默认配置", flush=True)
    return cfg


# ---------------------------------------------------------------- fetch
def http_get(url, timeout=15):
    try:
        import requests  # type: ignore
        r = requests.get(url, timeout=timeout,
                         headers={"User-Agent": "campus-jobs-watcher/1.0"})
        return r.text if r.status_code == 200 else ""
    except ImportError:
        pass
    except Exception as e:
        print(f"[warn] requests 抓取失败 {url}: {e}", flush=True)
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "campus-jobs-watcher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        print(f"[warn] urllib 抓取失败 {url}: {e}", flush=True)
        return ""


def parse_readme_table(md_text, keywords):
    """从 xixicc2027 README 的 markdown 表格里捞出命中关键词的行.

    表格列顺序各年份略有差异，这里不依赖列名：整行含关键词即收录，
    公司取第1列，岗位取整行文本，链接取行内第一个 http 链接。
    """
    jobs = []
    if not md_text:
        return jobs
    kw_lower = [k.lower() for k in keywords]
    for line in md_text.splitlines():
        s = line.strip()
        if not s.startswith("|") or "---" in s:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        row_text = " ".join(cells)
        low = row_text.lower()
        if not any(k in low for k in kw_lower):
            continue
        link_m = re.search(r"https?://[^\s\)\]]+", row_text)
        md_link = re.search(r"\[([^\]]+)\]\((https?://[^\)]+)\)", row_text)
        company = re.sub(r"\[|\]|\(.*?\)", "", cells[0]).strip()[:40] or "未知公司"
        position = re.sub(r"\s+", " ", row_text)[:120]
        jobs.append({
            "company": company,
            "position": position,
            "cities": "",
            "deadline": guess_deadline(row_text),
            "start": "",
            "headcount": "",
            "requirement": "",
            "link": (md_link.group(2) if md_link else link_m.group(0) if link_m else ""),
            "source": "xixicc2027",
        })
    # 去重（公司+岗位前30字）
    seen, out = set(), []
    for j in jobs:
        key = (j["company"], j["position"][:30])
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


def guess_deadline(text):
    """从文本里猜截止日期，返回 YYYY-MM-DD 或 ''."""
    year = dt.date.today().year
    m = re.search(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})[-./月](\d{1,2})[日号截止]*", text)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            return f"{year}-{mm:02d}-{dd:02d}"
    return ""


def fetch_live(cfg):
    for url in cfg["sources"]:
        print(f"[info] 尝试抓取: {url}", flush=True)
        text = http_get(url, timeout=cfg.get("fetch_timeout_sec", 15))
        if not text or len(text) < 500:
            print("[warn] 内容过短/为空，换下一个源", flush=True)
            continue
        jobs = parse_readme_table(text, cfg["keywords"])
        print(f"[info] 命中 {len(jobs)} 条相关行", flush=True)
        if jobs:
            return jobs, url
    return [], ""


# ---------------------------------------------------------------- filter/sort
def deadline_key(j):
    d = (j.get("deadline") or "").strip()
    try:
        return (0, dt.date.fromisoformat(d[:10]))
    except ValueError:
        return (1, dt.date.max)


def job_matches(job, keywords, cities):
    text = f"{job.get('company','')} {job.get('position','')} {job.get('requirement','')}"
    low = text.lower()
    if not any(k.lower() in low for k in keywords):
        return False
    if cities:
        jc = job.get("cities", "") or ""
        if not jc or jc in ("全国", "多地"):
            return True
        return any(c in jc for c in cities)
    return True


# ---------------------------------------------------------------- output
def write_csv(path, jobs):
    fields = ["company", "position", "cities",
              "deadline", "headcount", "requirement",
              "link", "source"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(jobs)


def write_md(path, jobs, live_source, live_count):
    today = dt.date.today().isoformat()
    lines = [
        f"# 27届 SRE / 运维岗秋招监控（{today} 更新）",
        "",
        f"- 共 **{len(jobs)}** 条（内置兜底 6 条 + 实时抓取 {live_count} 条）",
        f"- 实时源：`{live_source or '抓取失败，仅兜底数据'}`",
        "- 按截止时间升序：越靠前越紧急，请优先投递",
        "",
        "| 截止 | 公司 | 岗位 | 城市 | 人数 | 要求 | 投递 |",
        "|---|---|---|---|---|---|---|",
    ]
    for j in jobs:
        dl = j.get("deadline") or "待定"
        link = f"[投递]({j['link']})" if j.get("link") else "-"
        req = (j.get("requirement") or "-").replace("|", "/")[:60]
        lines.append(f"| {dl} | {j.get('company','-')} | {j.get('position','-')} "
                     f"| {j.get('cities') or '-'} | {j.get('headcount') or '-'} "
                     f"| {req} | {link} |")
    lines += ["", "_由 campus-jobs-watcher 每日自动更新；网络失败时自动降级为内置数据。_",
              ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------- email
def send_email(cfg, jobs):
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "465") or "465")
    user = os.getenv("SMTP_USER", "")
    pwd = os.getenv("SMTP_PASS", "")
    to = os.getenv("MAIL_TO", "")
    sender = os.getenv("MAIL_FROM", "") or user
    if not (host and user and pwd and to):
        print("[info] SMTP 环境变量不全，跳过邮件发送 "
              "(需 SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/MAIL_TO)", flush=True)
        return False
    prefix = cfg.get("email", {}).get("subject_prefix", "")
    today = dt.date.today().isoformat()
    urgent = [j for j in jobs if j.get("deadline")][:5]
    body_lines = [f"27届 SRE/运维秋招日报 {today}：共 {len(jobs)} 条，按截止排序：", ""]
    for j in jobs[:20]:
        body_lines.append(f"- [{j.get('deadline') or '待定'}] {j.get('company')} | "
                          f"{j.get('position')} | {j.get('cities') or '-'} | "
                          f"{j.get('link') or '无链接'}")
    if urgent:
        body_lines += ["", f"最紧急：{urgent[0].get('company')} {urgent[0].get('position')} "
                         f"截止 {urgent[0].get('deadline')}"]
    body_lines += ["", "完整表格见附件 jobs.md / 仓库 jobs.csv。"]
    msg = MIMEMultipart()
    msg["From"], msg["To"] = sender, to
    msg["Subject"] = f"{prefix} {today} 共{len(jobs)}条"
    msg.attach(MIMEText("\n".join(body_lines), "plain", "utf-8"))
    md_path = os.path.join(BASE_DIR, cfg["output"]["md"])
    try:
        with open(md_path, encoding="utf-8") as f:
            att = MIMEText(f.read(), "plain", "utf-8")
        att.add_header("Content-Disposition", "attachment", filename="jobs.md")
        msg.attach(att)
    except FileNotFoundError:
        pass
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as s:
                s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls()
                s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        print(f"[info] 邮件已发送至 {to}", flush=True)
        return True
    except Exception as e:
        print(f"[warn] 邮件发送失败（不影响主流程）: {e}", flush=True)
        return False


# ---------------------------------------------------------------- main
def main():
    cfg = load_config()
    try:
        live_jobs, live_source = fetch_live(cfg)
    except Exception as e:
        print(f"[warn] 实时抓取异常，用兜底数据: {e}", flush=True)
        live_jobs, live_source = [], ""
    # 合并去重：种子优先保真，实时做增量
    merged = list(SEEDS)
    seen = {(j["company"], j["position"]) for j in merged}
    added = 0
    for j in live_jobs:
        if (j["company"], j["position"][:30]) not in seen and \
                (j["company"], j["position"]) not in seen:
            # 实时行用“公司+岗位前30字”判重，避免与种子重复收录
            if not any(j["company"] in s["company"] and
                       any(k.lower() in j["position"].lower()
                           for k in [s["position"][:4]]) for s in merged):
                merged.append(j)
                added += 1
    jobs = [j for j in merged if job_matches(j, cfg["keywords"], cfg.get("cities", []))]
    if not jobs:  # 城市过滤太严时回退到不过滤城市，保证 jobs.md 非空
        print("[warn] 城市过滤后为空，回退为不过滤城市", flush=True)
        jobs = [j for j in merged if job_matches(j, cfg["keywords"], [])] or list(SEEDS)
    jobs.sort(key=deadline_key)
    md_path = os.path.join(BASE_DIR, cfg["output"]["md"])
    csv_path = os.path.join(BASE_DIR, cfg["output"]["csv"])
    write_md(md_path, jobs, live_source, added)
    write_csv(csv_path, jobs)
    print(f"[ok] 输出 {md_path} / {csv_path}，共 {len(jobs)} 条", flush=True)
    try:
        send_email(cfg, jobs)
    except Exception as e:
        print(f"[warn] 邮件流程异常（已忽略）: {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
