# 5시간 완성·이해 가이드

이 문서는 코드를 외우는 대신 **입력 → 검증 → 업무 규칙 → 저장** 흐름을 이해하기 위한 안내서다.

## 1. 5시간 사용법

| 시간 | 할 일 | 완료 기준 |
| --- | --- | --- |
| 0:00–0:30 | README 명령을 직접 실행 | 데이터 파일 3개가 생기는 것을 확인 |
| 0:30–1:20 | `models.py`, `validators.py`, `services.py` 읽기 | 거래 추가 흐름을 말로 설명 |
| 1:20–2:10 | `repositories.py` 읽기 | JSONL, 제너레이터, 원자적 교체 설명 |
| 2:10–2:50 | `cli.py`, `decorators.py` 읽기 | CLI와 데코레이터의 책임 설명 |
| 2:50–3:30 | 테스트 읽고 새 테스트 1개 직접 작성 | 실패 → 수정 → 통과를 경험 |
| 3:30–4:15 | 아래 시연 시나리오를 처음부터 수행 | 10개 기능 동작 확인 |
| 4:15–5:00 | 예상 질문에 소리 내어 답변 | 코드를 보지 않고 핵심 답변 |

## 2. 전체 구조 한 문장

`cli.py`가 사용자 입력을 받고, `BudgetService`가 검증과 업무 규칙을 적용한 뒤, `DataStore`가 모델을 JSONL 파일에 안전하게 저장한다.

```text
터미널 명령
    ↓ argparse
cli.py (입출력)
    ↓ 메서드 호출
services.py (검증 + 업무 규칙)
    ↓ 저장 요청
repositories.py (파일 I/O)
    ↕ 변환
models.py (Transaction)
    ↓
data/*.jsonl
```

이렇게 나눈 이유는 **변경 이유가 서로 다르기 때문**이다. 화면 문구가 바뀌면 CLI만, 저장 형식이 바뀌면 저장소만, 예산 규칙이 바뀌면 서비스만 주로 수정한다.

## 3. 반드시 이해할 여섯 가지

### dataclass

`Transaction`은 거래 한 건의 데이터 계약이다. 일반 클래스에서 반복되는 생성자와 비교/표현 기능을 `@dataclass`가 자동 생성한다. `to_dict()`와 `from_dict()`는 파이썬 객체와 JSON 저장 형태의 경계를 담당한다.

### JSONL

JSONL은 한 줄에 JSON 객체 하나를 둔다. 새 거래는 파일 끝에 한 줄만 추가할 수 있고, 읽을 때도 한 줄씩 해석할 수 있다. 하나의 거대한 JSON 배열은 끝 괄호를 유지해야 하고 보통 전체 구조를 읽게 되므로 스트리밍에 덜 적합하다.

### 제너레이터와 yield

`stream_transactions()`는 리스트를 반환하지 않고 `yield`로 거래를 하나씩 건넨다. 호출 즉시 전체 파일을 읽지 않으며, 반복문이 다음 값을 요구할 때만 다음 행을 읽는다. 검색과 요약은 이 값을 한 건씩 소비하므로 파일 크기만큼의 리스트가 생기지 않는다.

최신순 목록은 `_read_lines_reverse()`가 파일 끝에서 고정 크기 블록을 읽는다. 그래서 최신 몇 건을 보기 위해 전체 파일을 메모리에 올리거나 전체를 정렬하지 않는다.

### 데코레이터

`@friendly_errors`는 `run()` 앞뒤를 감싸는 함수다. 모든 명령에 같은 `try/except`를 복사하지 않고, 예상 가능한 `AppError`와 파일 오류를 한곳에서 잡아 원인·힌트와 종료 코드 1로 바꾼다. `functools.wraps`는 감싼 함수의 이름과 설명 같은 메타데이터를 보존한다.

### 원자적 재작성

JSONL에서 한가운데 있는 행을 직접 안전하게 늘이거나 줄이기 어렵다. 그래서 update/delete는 원본을 읽으면서 변경 결과를 임시 파일에 쓰고, 쓰기가 완전히 성공한 뒤 `os.replace()`로 교체한다. 중간에 오류가 나면 기존 원본이 남는다. 같은 파일 시스템 안의 교체는 원자적으로 처리된다.

### 타입 힌트

`date: str`, `amount: int`, `-> Iterator[Transaction]`은 실행 중 강제로 타입을 바꾸지 않는다. 대신 함수가 무엇을 받고 무엇을 돌려주는지 명시하여 IDE와 정적 분석기, 다음 개발자가 실수를 일찍 발견하도록 돕는다. 외부 입력은 언제나 문자열일 수 있으므로 `validate_amount()`가 실제 정수 변환과 런타임 검증을 맡는다.

## 4. 거래 추가 한 건의 실제 흐름

1. `argparse`가 `add` 명령을 선택한다.
2. `_ask()`가 값을 입력받고 날짜·타입·금액 오류 때 다시 묻는다.
3. `BudgetService.add_transaction()`이 카테고리 존재 여부까지 검증한다.
4. UUID 일부로 고유 id를 만들고 `Transaction` 객체를 생성한다.
5. `DataStore.append_transaction()`이 객체를 dict, JSON 문자열로 바꿔 한 줄 추가한다.
6. CLI가 생성된 id를 출력한다.

다른 명령도 같은 경계를 따른다. CLI는 보여 주는 방식, 서비스는 가능한 행동, 저장소는 파일 처리에 집중한다.

## 5. 직접 시연할 순서

연습용 데이터가 섞이지 않게 별도 폴더를 사용한다. `--data-dir`은 하위 명령보다 앞에 둔다.

```bash
python -m budget_app --data-dir demo-data category list
python -m budget_app --data-dir demo-data category add --name book
python -m budget_app --data-dir demo-data add
python -m budget_app --data-dir demo-data list --limit 5
python -m budget_app --data-dir demo-data search --category book --type expense
python -m budget_app --data-dir demo-data budget set --month 2024-01 --amount 100000
python -m budget_app --data-dir demo-data budget show --month 2024-01
python -m budget_app --data-dir demo-data summary --month 2024-01 --top 3
python -m budget_app --data-dir demo-data update --id 실제_ID --memo "수정됨"
python -m budget_app --data-dir demo-data export --out demo.csv --month 2024-01
python -m budget_app --data-dir imported-data import --from demo.csv
python -m budget_app --data-dir demo-data delete --id 실제_ID
python -m unittest discover -v
```

실수 시연도 한 번 한다. `--amount 0`, 잘못된 날짜, 없는 id, 사용 중인 카테고리 삭제를 실행하고 스택트레이스 대신 오류와 힌트가 나오는지 본다.

## 6. 예상 질문과 답변 핵심

**왜 DB 대신 파일을 썼나요?**  
과제 제약에 맞고 별도 서버 없이 영속성을 보여줄 수 있다. 대신 동시 쓰기와 복잡한 조회에는 한계가 있어 실제 규모가 커지면 DB를 고려한다.

**검색도 정말 스트리밍인가요?**  
그렇다. 저장소 제너레이터가 한 거래씩 주고 서비스가 조건에 맞는 항목만 다시 `yield`한다. CLI도 검색 결과를 리스트로 만들지 않고 바로 출력한다.

**목록의 `list(...)`는 문제 아닌가요?**  
서비스 제너레이터가 `--limit`에서 먼저 멈추므로 CLI에는 최대 N건만 쌓인다. 파일 전체 크기만큼 쌓이지 않는다.

**수정/삭제가 O(n)인 이유는요?**  
일반 파일은 중간 레코드 수정에 적합하지 않아 전체를 순회하며 재작성한다. 파일 과제에서 안전성을 우선한 선택이며, 빠른 임의 접근이 필요하면 DB와 인덱스가 맞다.

**카테고리 삭제를 왜 막나요?**  
기존 거래가 존재하지 않는 카테고리를 가리키는 참조 무결성 문제를 막기 위해서다. 먼저 거래를 다른 카테고리로 수정해야 한다.

**import에서 잘못된 행은 어떻게 되나요?**  
유효한 행은 저장하고 잘못된 행은 건너뛴 뒤 imported/skipped 수를 출력한다. 현재 설계는 부분 성공 정책이며 전부 성공/전부 취소 정책은 아니다.

**id에 UUID를 쓴 이유는요?**  
마지막 번호를 찾기 위해 전체 파일을 스캔하지 않고도 충돌 가능성이 매우 낮은 id를 즉시 생성하기 위해서다.

**예외를 전부 잡지 않은 이유는요?**  
예상 가능한 사용자/파일 오류만 친절하게 처리한다. 프로그래밍 버그까지 무조건 숨기면 개발 중 원인 발견이 어려워진다.

## 7. Git 제출 흐름

의미 단위로 기록하면 변경 의도를 설명하기 쉽다.

```bash
git init
git add budget_app
git commit -m "feat: implement file-based budget application"
git add tests
git commit -m "test: cover CRUD summary and CSV flows"
git add README.md STUDY_GUIDE.md .gitignore
git commit -m "docs: add usage and architecture guide"
git log --oneline
```

커밋 전에 반드시 `git diff --staged`로 포함될 파일과 비밀 정보가 없는지 확인한다.

