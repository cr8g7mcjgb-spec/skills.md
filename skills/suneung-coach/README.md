# suneung-coach — 수능 학습 운영체제

2029학년도 수능을 준비하는 고1 학생을 **3년짜리 프로젝트로 관리하는** Claude 스킬.

질문에 답하는 도우미가 아니라, 학생의 현재 수준을 진단하고 → 무너진 초·중등 기초를 찾아
→ 짧게 설명하고 → 수능 출제 방식으로 연결하고 → 문제를 내고 → 오답 원인을 분류하고
→ 복습을 예약하는 **파이프라인**이다.

---

## 왜 커넥터가 아니라 스킬인가

| | 커넥터 (MCP) | 스킬 |
| --- | --- | --- |
| 하는 일 | 외부 데이터/기능을 **가져온다** | 클로드의 **행동 규칙**을 바꾼다 |
| 필요한 경우 | Notion, Gmail, DB 연동 | 설명 방식, 출제 방식, 진단 절차 정의 |

이 프로젝트에 필요한 것은 "학생을 어떻게 가르칠 것인가"라는 **규칙**이므로 스킬이 맞다.
자료 조사(수행평가 근거, 입시 정보)에는 커넥터가 유용하고, 이 스킬은
`references/12-fact-verification.md`에서 그 사용 규칙을 정의한다.

---

## 설치

### 방법 A — 공부 프로젝트에 직접 두기 (권장)

```
공부 프로젝트/
├── .claude/
│   └── skills/
│       └── suneung-coach/     ← 이 폴더를 통째로 복사
│           ├── SKILL.md
│           ├── references/
│           ├── templates/
│           └── scripts/
├── STUDENT_PROFILE.md         ← templates/에서 복사
├── ERROR_LOG.md               ← templates/에서 복사
├── VOCAB.md                   ← templates/에서 복사
└── REVIEW_QUEUE.json          ← 스크립트가 자동 생성
```

```bash
mkdir -p "공부 프로젝트/.claude/skills"
cp -r skills/suneung-coach "공부 프로젝트/.claude/skills/"
cd "공부 프로젝트"
cp .claude/skills/suneung-coach/templates/{STUDENT_PROFILE,ERROR_LOG,VOCAB}.md .
```

`STUDENT_PROFILE.md`를 열어 성적·시간 항목을 채운다. 비워도 동작하지만, 채울수록 계획이 정확해진다.

### 방법 B — 플러그인으로 설치

이 저장소를 마켓플레이스로 추가한 뒤 `suneung-coach` 플러그인을 설치한다.
이 경우 `STUDENT_PROFILE.md` 등은 공부 프로젝트 루트에 직접 만든다.

---

## 사용

```
/suneung-coach 이 국어 지문을 내 수준에 맞게 설명하고, 기초 5문제, 적용 5문제, 고난도 3문제를 만들어줘.
```

명시적으로 호출하지 않아도, 학습 관련 질문이면 자동으로 트리거된다.

### 자주 쓰는 요청

| 요청 | 동작 |
| --- | --- |
| "이 지문 설명해줘" | 구조도 → 어휘 → 출제 포인트 → 문제 세트 |
| "문제 만들어줘" | 기본/적용/고난도 세트, 선지에 오개념 매핑 |
| "왜 틀렸는지 알려줘" | 오답 코드 분류 → 결손 역추적 → 처방 → 복습 예약 |
| "오늘 뭐 해야 해" | 복습 큐 확인 → 핵심 목표 3개 |
| "이 개념 모르겠어" | 초·중등 선수 개념 역추적 → 바닥부터 재구축 |
| "수행평가 도와줘" | 평가표 분석 → 주제 설계 → 개요 (대필 안 함) |
| "수능 어떻게 바뀌어?" | 확정/미확정 구분 + 출처 명시 |

---

## 구조

```
SKILL.md                      항상 로드되는 라우터 + 절대 규칙
├── references/
│   ├── 00-response-protocol   답변 형식, 20초 규칙, 계층화
│   ├── 01-diagnosis-engine    6대 실패 유형 판별
│   ├── 02-prerequisite-map    초·중등 역추적 지도 (과목 전체)
│   ├── 03-korean              국어 (최우선 과목)
│   ├── 04-english             영어 (절대평가 전략)
│   ├── 05-math                수학 (유일한 예외 과목)
│   ├── 06-social-history      통합사회 · 한국사
│   ├── 07-science             통합과학
│   ├── 08-item-design         문제 출제 · 선지 설계 원리
│   ├── 09-snu-thinking        사고력 훈련 6도구
│   ├── 10-memory-review       오답 기록 · 간격 복습
│   ├── 11-performance         수행평가 · 발표 (대필 금지)
│   ├── 12-fact-verification   사실/추정 구분 · 출처 우선순위
│   ├── 13-coaching            계획 · 습관 · 시간 배분
│   └── 14-exam-system         2028 개편 팩트 (재확인 대상)
├── templates/                 STUDENT_PROFILE / ERROR_LOG / VOCAB
└── scripts/review_queue.py    간격 복습 큐
```

**progressive disclosure**: SKILL.md만 항상 로드되고, 나머지는 필요할 때만 읽힌다.
그래서 모듈을 아무리 늘려도 매 대화의 부담이 커지지 않는다.

---

## 복습 큐

```bash
S=.claude/skills/suneung-coach/scripts/review_queue.py

python3 $S add "관계대명사 vs 관계부사" --subject 영어 --level L1 --from-error --code C
python3 $S due          # 오늘 복습할 것
python3 $S done 1 --result ok    # ok / hint / fail
python3 $S stats        # 약한 과목, 반복 실패 항목
```

간격: 일반 `0-1-3-7-14-45일`, 오답 항목 `0-1-3-7-14-30-60일`.
`fail`이면 1단계로 리셋된다.

---

## 설계 원칙 (요약)

1. **결론 먼저, 설명은 20초 안에.** 나머지는 `<details>`로 접는다
2. **빈 칭찬 금지.** "잘했어요" 대신 무엇이 맞고 틀렸는지
3. **정답 선공개 금지.** 학생 시도를 먼저 받는다
4. **기초를 뒤진다.** 고1 질문이 와도 초·중등 결손부터 확인
5. **"왜?"를 붙인다.** 서울대는 암기가 아니라 사고를 본다
6. **사실/추정/확인 필요를 구분한다.** 입시 정보는 출처 없이 단정하지 않는다
7. **기초와 수능을 동시에.** "기초부터 천천히"는 28개월 안에 목표에 못 간다
8. **모든 응답은 "지금 할 것" 한 가지로 끝난다**

---

## 한계

- 학생 프로필은 파일로 관리한다. 클로드가 세션 간 자동으로 기억하지 않으므로
  `STUDENT_PROFILE.md`와 `ERROR_LOG.md`를 **꾸준히 갱신해야** 코치로 작동한다
- `14-exam-system.md`의 입시 정보는 변경될 수 있다. 교육부·평가원·대학 공고로 재확인해야 한다
- 실제 기출문제를 재현하지 않는다. 기출은 EBS·평가원 자료로 별도 확보한다
- 수행평가 제출본을 대신 쓰지 않는다
