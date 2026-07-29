#!/usr/bin/env python3
"""수능 국어 문제지 PDF에서 텍스트를 뽑아 문항 단위로 쪼갠다.

corpus_index.py 가 만드는 태깅 CSV에 그대로 이어 붙일 수 있는 형태로 출력한다.

준비:
    pip install pypdf pdfplumber
    (cryptography 관련 ImportError 가 나면: pip install --upgrade cffi)

사용법:
    python3 pdf_extract.py 문제지.pdf                 진단 + 미리보기
    python3 pdf_extract.py 문제지.pdf --text out.txt  전체 텍스트 저장
    python3 pdf_extract.py 문제지.pdf --items out.csv 문항 단위로 쪼개 저장
    python3 pdf_extract.py 문제지.pdf --page 3        특정 쪽만 출력

스캔본(이미지 PDF)이면 텍스트가 안 나온다. 그때는 진단이 알려준다.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# 문항 시작: 줄머리의 "12." / "12 ." 형태
ITEM_RE = re.compile(r"^\s*(\d{1,2})\s*\.\s*(\S.*)$")
# 선지: ①~⑤
CHOICE_CHARS = "①②③④⑤"
CHOICE_RE = re.compile(r"[①②③④⑤]")
# 배점
POINT_RE = re.compile(r"\[(\d)\s*점\]")
# <보기> 상자
BOGI_RE = re.compile(r"<\s*보\s*기\s*>")


def load(path: Path):
    try:
        import pdfplumber
    except ImportError:
        sys.exit("pdfplumber 가 없습니다.  pip install pypdf pdfplumber")
    return pdfplumber.open(path)


def extract_pages(path: Path):
    """쪽별 텍스트 리스트를 돌려준다."""
    with load(path) as pdf:
        return [(p.page_number, p.extract_text() or "") for p in pdf.pages]


def diagnose(path: Path, pages):
    total_chars = sum(len(t) for _, t in pages)
    empty = [n for n, t in pages if len(t.strip()) < 20]
    hangul = sum(1 for _, t in pages for ch in t if "가" <= ch <= "힣")

    print(f"파일        : {path.name}")
    print(f"쪽 수       : {len(pages)}")
    print(f"추출 글자   : {total_chars:,}")
    print(f"한글 글자   : {hangul:,}")
    print(f"빈 쪽       : {len(empty)}{' ' + str(empty) if empty else ''}")

    if total_chars < 200 or hangul < 100:
        print()
        print("⚠ 텍스트가 거의 안 나옵니다. 스캔 이미지 PDF로 보입니다.")
        print("  OCR이 필요하며 이 환경에는 tesseract 가 없습니다.")
        print("  → 텍스트 기반 PDF(평가원 원본)를 올려 주세요.")
        return False

    print("✓ 텍스트 기반 PDF입니다. 추출 가능합니다.")
    return True


def split_items(pages):
    """문항 번호를 기준으로 쪼갠다. (번호, 본문) 리스트를 돌려준다."""
    lines = []
    for _, text in pages:
        lines.extend(text.splitlines())

    items = []
    cur_no = None
    buf = []
    last_no = 0

    for line in lines:
        m = ITEM_RE.match(line)
        # 번호가 1씩 늘어날 때만 문항 시작으로 인정 (본문 속 숫자 오인 방지)
        if m and int(m.group(1)) in (last_no + 1, last_no + 2):
            if cur_no is not None:
                items.append((cur_no, "\n".join(buf).strip()))
            cur_no = int(m.group(1))
            last_no = cur_no
            buf = [m.group(2)]
        elif cur_no is not None:
            buf.append(line)

    if cur_no is not None:
        items.append((cur_no, "\n".join(buf).strip()))
    return items


def item_row(no: int, body: str):
    """corpus_index.py 태깅 스키마와 맞물리는 행을 만든다."""
    choices = CHOICE_RE.findall(body)
    pt = POINT_RE.search(body)
    # 발문 = 첫 줄
    stem = body.splitlines()[0] if body else ""
    return {
        "qno": no,
        "points": pt.group(1) if pt else "",
        "bogi": "Y" if BOGI_RE.search(body) else "N",
        "n_choices": len(set(choices)),
        "negative": "Y" if ("않은" in stem or "않는" in stem) else "N",
        "stem": stem[:120],
        "chars": len(body),
    }


def main():
    ap = argparse.ArgumentParser(description="수능 국어 PDF 텍스트 추출기")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--text", type=Path, help="전체 텍스트를 저장할 경로")
    ap.add_argument("--items", type=Path, help="문항 단위 CSV 저장 경로")
    ap.add_argument("--page", type=int, help="이 쪽만 출력")
    args = ap.parse_args()

    if not args.pdf.exists():
        sys.exit(f"파일이 없습니다: {args.pdf}")

    pages = extract_pages(args.pdf)

    if args.page:
        for n, t in pages:
            if n == args.page:
                print(t)
                return 0
        sys.exit(f"{args.page}쪽이 없습니다 (전체 {len(pages)}쪽)")

    ok = diagnose(args.pdf, pages)
    print()

    if args.text:
        args.text.write_text(
            "\n".join(f"\n===== {n}쪽 =====\n{t}" for n, t in pages),
            encoding="utf-8",
        )
        print(f"전체 텍스트 저장: {args.text}")

    if not ok:
        return 1

    items = split_items(pages)
    print(f"인식된 문항 수: {len(items)}")
    if items:
        nos = [n for n, _ in items]
        print(f"번호 범위     : {min(nos)} ~ {max(nos)}")
        missing = sorted(set(range(min(nos), max(nos) + 1)) - set(nos))
        if missing:
            print(f"⚠ 누락 번호   : {missing}  (지문 사이에 끼어 인식 실패 가능)")

    rows = [item_row(n, b) for n, b in items]

    if args.items:
        with args.items.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["qno", "points", "bogi", "n_choices", "negative", "stem", "chars"],
            )
            w.writeheader()
            w.writerows(rows)
        print(f"문항 CSV 저장 : {args.items}")
    else:
        print()
        print(f"{'번호':<5}{'배점':<5}{'보기':<5}{'선지':<5}{'부정':<5}발문")
        print("-" * 78)
        for r in rows[:15]:
            print(
                f"{r['qno']:<5}{r['points']:<5}{r['bogi']:<5}"
                f"{r['n_choices']:<5}{r['negative']:<5}{r['stem'][:44]}"
            )
        if len(rows) > 15:
            print(f"... 외 {len(rows)-15}문항 (--items 로 전체 저장)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
