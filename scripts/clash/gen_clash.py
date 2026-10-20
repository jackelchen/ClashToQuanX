#!/usr/bin/env python3
"""
Auto-generate Clash ruleset config (output/clash.ini) from filter/*.list.

只处理「非 0 开头」的规则文件（Bahamut.list, Google.list, ... 这些从外部获取的规则）。
0 开头的文件是用户自定义，保持手动维护，脚本不去动。

生成方式（与 output/quanx.list 一样，由 GitHub Actions 生成并提交）:

1. 以 scripts/clash/rule.ini 为模板（只含手动部分：0 开头 ruleset/组、系统组、国家节点、末尾参数）
2. 在 AUTO 标记内重新生成非 0 开头的 ruleset 与 custom_proxy_group（按文件名字母序）
3. 整体写入 output/clash.ini（rule.ini 本身不被修改）

规则文件的策略名取其文件名（不含扩展名）。脚本会校验每个文件里的策略名与文件名一致，
不一致时给出警告（不中断），避免静默产生错误规则。

用法:
    python scripts/clash/gen_clash.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLASH_DIR = ROOT / "filter"
RULE_INI = Path(__file__).resolve().parent / "rule.ini"           # 模板:手动部分
OUTPUT_CLASH = ROOT / "output" / "clash.ini"      # 生成的完整 Clash 配置

GITHUB_OWNER = "jackelchen"
GITHUB_REPO = "SubRule"
BRANCH = "main"
CDN_BASE = f"https://cdn.jsdelivr.net/gh/{GITHUB_OWNER}/{GITHUB_REPO}@{BRANCH}/filter"

# 每个 list 对应的策略组模板（成员结构沿用现有规则）
POLICY_GROUP_TEMPLATE = (
    "custom_proxy_group={name}`select`[]🚀 地区选择`[]🇯🇵 日本节点`[]"
    "🇭🇰 香港节点`[]🇨🇳 台湾节点`[]🇸🇬 新加坡节点`[]🇺🇲 美国节点`[]"
    "🏳️‍🌈 其他节点`[]🚀 手动切换`[]DIRECT"
)

RULESET_BEGIN = "# ===== AUTO ruleset BEGIN ====="
RULESET_END = "# ===== AUTO ruleset END ====="
GROUP_BEGIN = "# ===== AUTO policy-group BEGIN ====="
GROUP_END = "# ===== AUTO policy-group END ====="


def auto_stems() -> list[str]:
    """返回应被脚本自动管理的文件名前缀（非 0 开头）。"""
    return sorted(
        p.stem for p in CLASH_DIR.glob("*.list") if not p.stem.startswith("0")
    )


def check_policy_names(stem: str) -> int:
    """返回该列表文件中策略名与文件名不一致的行数（仅统计）。"""
    path = CLASH_DIR / f"{stem}.list"
    bad = 0
    with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if line.startswith("- "):
                line = line[2:].strip()
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[2] != stem:
                bad += 1
    return bad


def gen_ruleset_line(stem: str) -> str:
    return f"ruleset={stem},{CDN_BASE}/{stem}.list"


def gen_group_line(stem: str) -> str:
    return POLICY_GROUP_TEMPLATE.format(name=stem)


def replace_lineset(
    lines: list[str],
    begin: str,
    end: str,
    new_lines: list[str],
    match_auto,
    anchor_kw: str,
) -> list[str]:
    """自举式替换指定区段。

    若已存在 begin/end 标记 -> 只替换标记之间内容。
    否则 -> 删除所有符合 match_auto 的行，
          再把标记区插到第一个以 anchor_kw 开头的（手动）行之前，
          找不到则追加到末尾。
    """
    try:
        b = lines.index(begin)
        e = lines.index(end, b)
        return lines[: b + 1] + new_lines[1:-1] + lines[e:]
    except ValueError:
        pass

    kept = [ln for ln in lines if not match_auto(ln)]
    anchor = len(kept)  # 默认追加到末尾
    for i, ln in enumerate(kept):
        if ln.startswith(anchor_kw):
            anchor = i
            break
    return kept[:anchor] + new_lines + kept[anchor:]


def generate_clash_ini(stems: list[str], dry_run: bool) -> None:
    """以 scripts/clash/rule.ini 为模板生成 output/clash.ini（AUTO 区段按字母序重排）。"""
    text = RULE_INI.read_text(encoding="utf-8")
    lines = text.splitlines()

    auto = set(stems)

    def is_auto_ruleset(ln: str) -> bool:
        if not ln.startswith("ruleset="):
            return False
        name = ln[len("ruleset="):].split(",")[0].strip()
        return name in auto

    def is_auto_group(ln: str) -> bool:
        if not ln.startswith("custom_proxy_group="):
            return False
        # 用反引号切出组名第一部分
        rest = ln[len("custom_proxy_group="):]
        name = rest.split("`", 1)[0].strip()
        return name in auto

    ruleset_lines = [RULESET_BEGIN] + [gen_ruleset_line(s) for s in stems] + [RULESET_END]
    group_lines = [GROUP_BEGIN] + [gen_group_line(s) for s in stems] + [GROUP_END]

    lines = replace_lineset(lines, RULESET_BEGIN, RULESET_END,
                            ruleset_lines, is_auto_ruleset, "ruleset=")
    lines = replace_lineset(lines, GROUP_BEGIN, GROUP_END,
                            group_lines, is_auto_group, "custom_proxy_group=")

    new_text = "\n".join(lines).rstrip("\n") + "\n"
    if not dry_run:
        OUTPUT_CLASH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_CLASH.write_text(new_text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印将要生成的内容，不写文件")
    args = parser.parse_args()

    if not CLASH_DIR.is_dir():
        print(f"error: {CLASH_DIR} 不存在", file=sys.stderr)
        sys.exit(1)

    stems = auto_stems()
    if not stems:
        print("warning: filter 下没有非 0 开头的 .list 文件", file=sys.stderr)

    # 校验策略名与文件名一致
    inconsistent = [(s, check_policy_names(s)) for s in stems]
    bad = [(s, n) for s, n in inconsistent if n]
    for s, n in bad:
        print(f"warning: {s}.list 有 {n} 行策略名与文件名不一致", file=sys.stderr)
    if bad:
        print("提示: 这些 list 的策略名与文件名不同，自动生成的策略组名可能不匹配。",
              file=sys.stderr)

    print("== 将生成以下 ruleset ==")
    for s in stems:
        print("  " + gen_ruleset_line(s))
    print("== 将生成以下策略组 ==")
    for s in stems:
        print("  " + gen_group_line(s))

    generate_clash_ini(stems, args.dry_run)

    if args.dry_run:
        print("\n[dry-run] 未写入任何文件。")
    else:
        print(f"\n已生成 {OUTPUT_CLASH.name} 于 output/（自动区段每次按字母序重排）")


if __name__ == "__main__":
    main()