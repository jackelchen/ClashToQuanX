import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASH_DIR = ROOT / "filter"

POLICY_BY_FILE = {
    "0games.list": "DMMCOJP",
    "Bahamut.list": "巴哈姆特",
    "BanAD.list": "🛑 全球拦截",
    "BanProgramAD.list": "🛑 全球拦截",
    "ChatGPT.list": "ChatGPT",
    "Discord.list": "Discord",
    "Epic.list": "Epic",
    "Facebook.list": "Facebook",
    "GitHub.list": "GitHub",
    "Google.list": "Google",
    "Microsoft.list": "Microsoft",
    "OpenAI.list": "OpenAI",
    "Pixiv.list": "Pixiv",
    "ProxyGFWlist.list": "♻️ 自动选择",
    "Reddit.list": "Reddit",
    "Steam.list": "Steam",
    "Telegram.list": "Telegram",
    "TikTok.list": "TikTok",
    "Twitch.list": "Twitch",
    "Twitter.list": "Twitter",
    "Ubisoft.list": "Ubi",
    "YouTube.list": "YouTube",
}


def add_policy(path: Path, policy: str) -> int:
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    changed = 0
    for i, line in enumerate(lines):
        content = line.rstrip("\r")
        stripped = content.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = content.split(",")
        if fields[-1] == "no-resolve" and len(fields) >= 3:
            if len(fields) == 3:
                fields.insert(-1, policy)
            else:
                if fields[-2] == policy:
                    continue
                fields[-2] = policy
            lines[i] = ",".join(fields)
            changed += 1
        elif len(fields) >= 3:
            if fields[2] == policy:
                continue
            fields[2] = policy
            lines[i] = ",".join(fields)
            changed += 1
        else:
            lines[i] = content + "," + policy
            changed += 1
    data = newline.join(lines).encode("utf-8")
    if has_bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    return changed


def main() -> None:
    total = 0
    for name, policy in POLICY_BY_FILE.items():
        path = CLASH_DIR / name
        if not path.exists():
            print(f"[MISS] {name} 文件不存在")
            continue
        changed = add_policy(path, policy)
        total += changed
        print(f"[OK] {name}: 更新 {changed} 行, 策略={policy}")
    print(f"共更新 {total} 行")


if __name__ == "__main__":
    main()
