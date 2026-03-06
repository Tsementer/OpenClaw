#!/usr/bin/env python3
import os, re, sys, json, subprocess

GOG="/data/bin/gog"

def main():
    if len(sys.argv) != 2:
        print("usage: extract_forward_meta.py <messageId>", file=sys.stderr)
        sys.exit(2)

    mid=sys.argv[1]
    env=os.environ.copy()
    if not env.get("GOG_KEYRING_PASSWORD"):
        print("GOG_KEYRING_PASSWORD missing", file=sys.stderr)
        sys.exit(3)

    r=subprocess.run([GOG,"gmail","get",mid,"--format","full"], text=True, capture_output=True, env=env)
    text=r.stdout or ""

    def pick(pattern):
        m=re.search(pattern, text)
        return m.group(1).strip() if m else None

    orig_from = pick(r'(?mi)^\s*(?:Saatja|From)\s*:\s*(.+)$')
    orig_subj = pick(r'(?mi)^\s*(?:Teema|Subject)\s*:\s*(.+)$')
    orig_sent = pick(r'(?mi)^\s*(?:Saadetud|Sent)\s*:\s*(.+)$')

    print(json.dumps({"origFrom":orig_from,"origSubject":orig_subj,"origSent":orig_sent}, ensure_ascii=False))

if __name__=="__main__":
    main()
