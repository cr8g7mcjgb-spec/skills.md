#!/usr/bin/env python3
"""간격 복습 큐 관리.

날짜 계산은 모델이 직접 하지 않는다. 이 스크립트가 한다.

사용법:
    python review_queue.py add "관계대명사 vs 관계부사" --subject 영어 --level L1
    python review_queue.py due
    python review_queue.py list [--subject 영어]
    python review_queue.py done 7 --result ok|hint|fail
    python review_queue.py stats
    python review_queue.py remove 7

큐 파일은 기본적으로 현재 작업 디렉터리의 REVIEW_QUEUE.json 이다.
--file 로 바꿀 수 있다.
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

# 일반 학습 항목 / 오답에서 나온 항목의 복습 간격 (일 단위)
INTERVALS_NORMAL = [0, 1, 3, 7, 14, 45]
INTERVALS_ERROR = [0, 1, 3, 7, 14, 30, 60]

DEFAULT_FILE = "REVIEW_QUEUE.json"


def load(path):
    if not os.path.exists(path):
        return {"next_id": 1, "items": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def today():
    return date.today()


def iso(d):
    return d.isoformat()


def parse(s):
    return date.fromisoformat(s)


def intervals_for(item):
    return INTERVALS_ERROR if item.get("from_error") else INTERVALS_NORMAL


def cmd_add(args):
    data = load(args.file)
    intervals = INTERVALS_ERROR if args.from_error else INTERVALS_NORMAL
    item = {
        "id": data["next_id"],
        "topic": args.topic,
        "subject": args.subject,
        "level": args.level,
        "from_error": args.from_error,
        "error_code": args.code,
        "note": args.note,
        "created": iso(today()),
        "stage": 0,
        "due": iso(today() + timedelta(days=intervals[0])),
        "history": [],
        "done": False,
    }
    data["items"].append(item)
    data["next_id"] += 1
    save(args.file, data)
    print(f"추가됨 #{item['id']}  {item['topic']}  (다음 복습: {item['due']})")


def _fmt(item, show_due=True):
    tag = "⚠️" if item.get("from_error") else "  "
    parts = [f"{tag} #{item['id']:>3}", f"[{item.get('subject') or '-'}]"]
    if item.get("level"):
        parts.append(item["level"])
    parts.append(item["topic"])
    if show_due and not item["done"]:
        parts.append(f"→ {item['due']}")
    stages = len(intervals_for(item))
    parts.append(f"({min(item['stage'] + 1, stages)}/{stages})")
    return "  ".join(parts)


def cmd_due(args):
    data = load(args.file)
    now = today()
    due = [
        i for i in data["items"]
        if not i["done"] and parse(i["due"]) <= now
    ]
    due.sort(key=lambda i: (i["due"], -int(bool(i.get("from_error")))))

    if not due:
        print("오늘 복습할 항목 없음.")
        return

    overdue = [i for i in due if parse(i["due"]) < now]
    print(f"복습 대상 {len(due)}개 (밀린 것 {len(overdue)}개)\n")
    for i in due:
        late = (now - parse(i["due"])).days
        mark = f"  [{late}일 밀림]" if late > 0 else ""
        print(_fmt(i) + mark)


def cmd_list(args):
    data = load(args.file)
    items = [i for i in data["items"] if args.all or not i["done"]]
    if args.subject:
        items = [i for i in items if i.get("subject") == args.subject]
    items.sort(key=lambda i: i["due"])

    if not items:
        print("항목 없음.")
        return
    for i in items:
        status = "✔ 완료" if i["done"] else ""
        print(_fmt(i) + ("  " + status if status else ""))


def cmd_done(args):
    data = load(args.file)
    item = next((i for i in data["items"] if i["id"] == args.id), None)
    if item is None:
        print(f"#{args.id} 없음.", file=sys.stderr)
        return 1

    intervals = intervals_for(item)
    item["history"].append({"date": iso(today()), "result": args.result})

    if args.result == "ok":
        item["stage"] += 1
    elif args.result == "hint":
        pass  # 같은 간격 유지
    else:  # fail
        item["stage"] = 0

    if item["stage"] >= len(intervals):
        item["done"] = True
        item["due"] = iso(today())
        print(f"#{item['id']} {item['topic']} — 장기기억 정착 완료.")
        save(args.file, data)
        return 0

    gap = intervals[item["stage"]]
    # 같은 날 다시 뜨지 않도록 최소 1일
    item["due"] = iso(today() + timedelta(days=max(gap, 1)))
    save(args.file, data)

    label = {"ok": "성공", "hint": "힌트 후 성공", "fail": "실패 → 1단계 리셋"}[args.result]
    print(f"#{item['id']} {item['topic']} — {label}. 다음 복습: {item['due']}")
    return 0


def cmd_remove(args):
    data = load(args.file)
    before = len(data["items"])
    data["items"] = [i for i in data["items"] if i["id"] != args.id]
    if len(data["items"]) == before:
        print(f"#{args.id} 없음.", file=sys.stderr)
        return 1
    save(args.file, data)
    print(f"#{args.id} 삭제됨.")
    return 0


def cmd_stats(args):
    data = load(args.file)
    items = data["items"]
    if not items:
        print("항목 없음.")
        return

    active = [i for i in items if not i["done"]]
    settled = [i for i in items if i["done"]]
    now = today()
    overdue = [i for i in active if parse(i["due"]) < now]

    print(f"전체 {len(items)}  |  진행 중 {len(active)}  |  정착 {len(settled)}  |  밀림 {len(overdue)}")

    by_subject = {}
    for i in items:
        s = i.get("subject") or "미분류"
        by_subject.setdefault(s, {"n": 0, "fail": 0})
        by_subject[s]["n"] += 1
        by_subject[s]["fail"] += sum(
            1 for h in i["history"] if h["result"] == "fail"
        )

    print("\n과목별")
    print(f"{'과목':<10}{'항목':>6}{'실패':>6}{'실패율':>9}")
    for s, v in sorted(by_subject.items(), key=lambda kv: -kv[1]["fail"]):
        attempts = sum(
            len(i["history"]) for i in items if (i.get("subject") or "미분류") == s
        )
        rate = f"{v['fail'] / attempts * 100:.0f}%" if attempts else "-"
        print(f"{s:<10}{v['n']:>6}{v['fail']:>6}{rate:>9}")

    # 반복 실패 항목
    weak = [
        i for i in items
        if sum(1 for h in i["history"] if h["result"] == "fail") >= 2
    ]
    if weak:
        print("\n반복 실패 (2회 이상) — 학습 방식 재검토 대상")
        for i in weak:
            fails = sum(1 for h in i["history"] if h["result"] == "fail")
            print(f"  #{i['id']:>3} [{i.get('subject') or '-'}] {i['topic']}  실패 {fails}회")

    codes = {}
    for i in items:
        c = i.get("error_code")
        if c:
            codes[c] = codes.get(c, 0) + 1
    if codes:
        print("\n오답 코드 분포")
        for c, n in sorted(codes.items(), key=lambda kv: -kv[1]):
            flag = " ⚠️" if n >= 3 else ""
            print(f"  {c}: {n}{flag}")


def main():
    p = argparse.ArgumentParser(description="간격 복습 큐")
    p.add_argument("--file", default=DEFAULT_FILE, help="큐 파일 경로")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="복습 항목 추가")
    a.add_argument("topic")
    a.add_argument("--subject", default=None, help="국어/영어/수학/사회/과학/한국사")
    a.add_argument("--level", default=None, help="L0~L4")
    a.add_argument("--from-error", action="store_true", help="오답에서 나온 항목 (간격 촘촘)")
    a.add_argument("--code", default=None, help="오답 코드 P/C/R/M/L/K/X/T")
    a.add_argument("--note", default=None)
    a.set_defaults(func=cmd_add)

    d = sub.add_parser("due", help="오늘 복습할 항목")
    d.set_defaults(func=cmd_due)

    l = sub.add_parser("list", help="전체 목록")
    l.add_argument("--subject", default=None)
    l.add_argument("--all", action="store_true", help="정착 완료 항목도 포함")
    l.set_defaults(func=cmd_list)

    o = sub.add_parser("done", help="복습 완료 처리")
    o.add_argument("id", type=int)
    o.add_argument("--result", choices=["ok", "hint", "fail"], default="ok")
    o.set_defaults(func=cmd_done)

    r = sub.add_parser("remove", help="항목 삭제")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_remove)

    s = sub.add_parser("stats", help="통계")
    s.set_defaults(func=cmd_stats)

    args = p.parse_args()
    try:
        sys.exit(args.func(args) or 0)
    except BrokenPipeError:
        # `... | head` 같은 파이프에서 정상 동작
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)


if __name__ == "__main__":
    main()
