#!/usr/bin/env python3
"""기출 코퍼스 인덱서.

references/13-corpus.md 의 폴더 구조를 전제한다.

    corpus/
      2026/수능/국어_문제지.pdf
      2026/수능/국어_정답표.pdf
      2026/수능/국어_정답률.csv      (선택)
      2026/6월/...
      2028예시/국어_예시문항.pdf

사용법:
    python3 corpus_index.py corpus/                     확보 현황 표
    python3 corpus_index.py corpus/ --check             누락 회차 목록
    python3 corpus_index.py corpus/ --template 2026 수능  태깅 CSV 생성
    python3 corpus_index.py corpus/ --validate tags.csv  태깅 CSV 검증
"""

import argparse
import csv
import sys
from pathlib import Path

SITTINGS = ["수능", "6월", "9월"]
REQUIRED = ["국어_문제지.pdf", "국어_정답표.pdf"]
OPTIONAL = ["국어_정답률.csv"]

# 태깅 스키마 (13-corpus.md §4)
FIELDS = [
    "year", "sitting", "qno", "area", "subarea", "set_id",
    "passage_len", "skeleton", "qtype", "bogi", "bogi_cat",
    "points", "answer", "correct_rate", "top_wrong", "wrong_tags",
    "work", "notes",
]

ENUMS = {
    "sitting": {"수능", "6월", "9월", "예시"},
    "area": {"독서", "문학", "화법", "작문", "언어", "매체"},
    "skeleton": set("ABCDEFGH") | {""},
    "qtype": {"전개", "일치", "추론", "보기적용", "어휘", "부분", "기타", ""},
    "bogi": {"Y", "N", ""},
    "points": {"2", "3", ""},
}

VALID_TAGS = {f"T{i}" for i in range(1, 13)}

# 학년도별 국어 문항 수 (02-timeline.md)
def item_count(year: int) -> int:
    if year >= 2014:
        return 45
    if year >= 2008:
        return 50
    return 60


def scan(root: Path):
    """폴더를 훑어 (year, sitting, 상태) 목록을 만든다."""
    rows = []
    for ydir in sorted(root.iterdir()):
        if not ydir.is_dir():
            continue
        label = ydir.name
        for sdir in sorted(ydir.iterdir()):
            if not sdir.is_dir():
                # 2028예시 처럼 회차 폴더 없이 파일이 바로 있는 경우
                continue
            have = {f.name for f in sdir.iterdir() if f.is_file()}
            missing = [r for r in REQUIRED if r not in have]
            extras = [o for o in OPTIONAL if o in have]
            rows.append({
                "year": label,
                "sitting": sdir.name,
                "ok": not missing,
                "missing": missing,
                "extras": extras,
            })
        # 회차 폴더가 없는 경우(예시문항 등) 파일 직접 확인
        loose = {f.name for f in ydir.iterdir() if f.is_file()}
        if loose and not any(d.is_dir() for d in ydir.iterdir()):
            rows.append({
                "year": label,
                "sitting": "-",
                "ok": bool(loose),
                "missing": [],
                "extras": sorted(loose),
            })
    return rows


def cmd_list(root: Path, only_missing: bool):
    rows = scan(root)
    if not rows:
        print(f"'{root}' 아래에서 회차 폴더를 찾지 못했습니다.")
        print("구조: corpus/<학년도>/<수능|6월|9월>/국어_문제지.pdf")
        return 1

    print(f"{'학년도':<10}{'회차':<8}{'상태':<8}{'비고'}")
    print("-" * 60)
    n_ok = sum(1 for r in rows if r["ok"])
    for r in rows:
        if only_missing and r["ok"]:
            continue
        status = "확보" if r["ok"] else "누락"
        note = ""
        if r["missing"]:
            note = "없음: " + ", ".join(r["missing"])
        elif r["extras"]:
            note = "추가: " + ", ".join(r["extras"])
        print(f"{r['year']:<10}{r['sitting']:<8}{status:<8}{note}")

    print("-" * 60)
    print(f"확보 {n_ok} / 전체 {len(rows)} 회차")

    # 연속 학년도 중 빠진 회차 안내
    years = sorted({r["year"] for r in rows if r["year"].isdigit()}, key=int)
    if years:
        present = {(r["year"], r["sitting"]) for r in rows if r["ok"]}
        gaps = [
            f"{y} {s}" for y in years for s in SITTINGS
            if (y, s) not in present
        ]
        if gaps:
            print("\n미확보 회차:")
            for g in gaps:
                print("  -", g)
    return 0


def cmd_template(root: Path, year: str, sitting: str):
    """태깅용 CSV 템플릿을 문항 수만큼 만들어 준다."""
    try:
        n = item_count(int(year))
    except ValueError:
        n = 45  # 예시문항 등
    out = root / f"tags_{year}_{sitting}.csv"
    if out.exists():
        print(f"이미 존재합니다: {out}")
        return 1
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i in range(1, n + 1):
            w.writerow({"year": year, "sitting": sitting, "qno": i})
    print(f"생성: {out}  ({n}문항)")
    print("13-corpus.md §4 의 필드 설명을 보며 채우세요.")
    return 0


def cmd_validate(path: Path):
    """태깅 CSV의 값을 검사한다."""
    if not path.exists():
        print(f"파일이 없습니다: {path}")
        return 1

    problems = []
    seen = set()
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing_cols = [c for c in FIELDS if c not in (reader.fieldnames or [])]
        if missing_cols:
            problems.append(f"헤더 누락: {', '.join(missing_cols)}")

        for i, row in enumerate(reader, start=2):
            loc = f"{path.name}:{i}행"

            key = (row.get("year"), row.get("sitting"), row.get("qno"))
            if key in seen:
                problems.append(f"{loc} 중복 문항 {key}")
            seen.add(key)

            for col, allowed in ENUMS.items():
                v = (row.get(col) or "").strip()
                if v and v not in allowed:
                    problems.append(
                        f"{loc} {col}='{v}' 는 허용값이 아님 "
                        f"({'/'.join(sorted(a for a in allowed if a))})"
                    )

            rate = (row.get("correct_rate") or "").strip()
            if rate:
                try:
                    r = float(rate)
                    if not 0 <= r <= 1:
                        problems.append(f"{loc} correct_rate={r} (0~1 이어야 함)")
                except ValueError:
                    problems.append(f"{loc} correct_rate='{rate}' 는 숫자가 아님")

            tags = (row.get("wrong_tags") or "").strip()
            if tags:
                for part in tags.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    if ":" not in part:
                        problems.append(f"{loc} wrong_tags '{part}' 형식은 '선지번호:T태그'")
                        continue
                    choice, tag = (p.strip() for p in part.split(":", 1))
                    if choice not in {"1", "2", "3", "4", "5"}:
                        problems.append(f"{loc} wrong_tags 선지번호 '{choice}' 이상")
                    if tag not in VALID_TAGS:
                        problems.append(f"{loc} wrong_tags 태그 '{tag}' 는 T1~T12 아님")

            ans = (row.get("answer") or "").strip()
            if ans and ans not in {"1", "2", "3", "4", "5"}:
                problems.append(f"{loc} answer='{ans}' 이상")

    if problems:
        print(f"문제 {len(problems)}건:")
        for p in problems:
            print("  -", p)
        return 1

    print(f"{path.name}: 이상 없음 ({len(seen)}문항)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="수능 국어 기출 코퍼스 인덱서")
    ap.add_argument("root", type=Path, help="코퍼스 루트 폴더")
    ap.add_argument("--check", action="store_true", help="누락 회차만 표시")
    ap.add_argument("--template", nargs=2, metavar=("학년도", "회차"),
                    help="태깅 CSV 템플릿 생성 (예: --template 2026 수능)")
    ap.add_argument("--validate", type=Path, metavar="CSV",
                    help="태깅 CSV 검증")
    args = ap.parse_args()

    if args.validate:
        return cmd_validate(args.validate)

    if not args.root.exists():
        print(f"폴더가 없습니다: {args.root}")
        return 1

    if args.template:
        return cmd_template(args.root, args.template[0], args.template[1])

    return cmd_list(args.root, only_missing=args.check)


if __name__ == "__main__":
    sys.exit(main())
