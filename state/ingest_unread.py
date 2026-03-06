#!/usr/bin/env python3
import os, sys, subprocess, json, time

GOG="/data/bin/gog"
LEDGER="/data/.openclaw/state/ledger.jsonl"
QUERY="is:unread in:inbox"
MAX_FIELD_LEN=500

def run(cmd):
    env=os.environ.copy()
    if not env.get("GOG_KEYRING_PASSWORD"):
        print("ERROR: GOG_KEYRING_PASSWORD missing", file=sys.stderr)
        sys.exit(2)
    return subprocess.run(cmd, text=True, capture_output=True, env=env)

def load_latest_status():
    latest={}
    if not os.path.exists(LEDGER):
        return latest
    with open(LEDGER,"r",encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                obj=json.loads(line)
            except:
                continue
            tid=obj.get("threadId")
            if tid:
                latest[tid]=obj
    return latest

def parse_plain(out):
    out=out.strip()
    if not out or out.startswith("No results"):
        return []
    lines=out.splitlines()
    if lines and lines[0].startswith("ID"):
        lines=lines[1:]
    rows=[]
    for line in lines:
        if not line.strip():
            continue
        parts=line.split("\t")
        if len(parts) < 5:
            continue
        msg_id=parts[0].strip()
        thread_id=parts[1].strip()
        date=parts[2].strip()
        from_=parts[3].strip()
        subject=parts[4].strip()
        rows.append((thread_id,msg_id,date,from_,subject))
    return rows

def append_event(ev):
    with open(LEDGER,"a",encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")

def sanitize_field(value):
    if value is None:
        return ""
    clean=value.replace("\r"," ").replace("\n"," ").replace("\t"," ")
    clean="".join(ch for ch in clean if ch.isprintable())
    return clean.strip()[:MAX_FIELD_LEN]

def main():
    r=run([GOG,"gmail","messages","search",QUERY,"--plain"])
    if r.returncode != 0:
        print("ERROR: search failed:", (r.stderr or r.stdout).strip(), file=sys.stderr)
        sys.exit(3)

    rows=parse_plain(r.stdout)
    if not rows:
        print("INBOX_EMPTY")
        return

    latest=load_latest_status()
    done={"TRIAGED","DRAFTED","EDITED","NOTIFIED","SKIPPED"}
    now=time.time()

    new_items=[]
    for thread_id,msg_id,date,from_,subject in rows:
        thread_id=sanitize_field(thread_id)
        msg_id=sanitize_field(msg_id)
        date=sanitize_field(date)
        from_=sanitize_field(from_)
        subject=sanitize_field(subject)
        if not thread_id or not msg_id:
            continue

        prev=latest.get(thread_id)
        if prev and prev.get("status") in done:
            continue

        ev={
            "event":"NEW",
            "threadId":thread_id,
            "messageId":msg_id,
            "subject":subject,
            "from":from_,
            "receivedAt":date,
            "prescore":None,
            "finalscore":None,
            "status":"NEW",
            "docsLinks":[],
            "lastError":None,
            "createdAt":now,
            "updatedAt":now
        }
        append_event(ev)
        new_items.append((thread_id,msg_id,date,from_,subject))

        # mark thread read
        run([GOG,"gmail","labels","modify",thread_id,"--remove","UNREAD"])

    if not new_items:
        print("NO_NEW_AFTER_DEDUPE")
        return

    for thread_id,msg_id,date,from_,subject in new_items:
        print(f"NEW\t{thread_id}\t{msg_id}\t{date}\t{from_}\t{subject}")
    print(f"TOTAL_NEW={len(new_items)}")

if __name__=="__main__":
    main()
