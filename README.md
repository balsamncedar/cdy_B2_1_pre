# 나만의 용돈 기입장

Python 표준 라이브러리만 사용한 파일 기반 콘솔 가계부입니다. Python 3.10 이상에서 실행합니다.

## 실행

프로젝트 루트에서 아래처럼 실행합니다. 모든 단계의 도움말은 `--help`로 확인할 수 있습니다.

```bash
python -m budget_app --help
python -m budget_app add
python -m budget_app list --limit 5
python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal
python -m budget_app summary --month 2024-01 --top 3
python -m budget_app budget set --month 2024-01 --amount 500000
python -m budget_app budget show --month 2024-01
python -m budget_app category add --name hobby
python -m budget_app category list
python -m budget_app category remove --name hobby
python -m budget_app update --id TX-1234ABCD --amount 20000 --memo "수정 메모"
python -m budget_app delete --id TX-1234ABCD
python -m budget_app export --out export.csv --month 2024-01
python -m budget_app import --from export.csv
```

기본 저장 위치는 `./data`입니다. 다른 위치는 **하위 명령 앞에** 전역 옵션을 둡니다.

```bash
python -m budget_app --data-dir ./my-data list --limit 10
```

## 저장 형식

최초 실행 때 폴더와 아래 UTF-8 JSONL 파일을 자동 생성합니다. JSONL은 한 줄에 JSON 객체 하나를 저장하는 형식이므로 거래를 한 건씩 스트리밍할 수 있습니다.

- `data/transactions.jsonl`: id, type, date, amount, category, memo, tags
- `data/categories.jsonl`: category name (기본값 food, transport, rent, salary, etc)
- `data/budgets.jsonl`: month, amount

`update`와 `delete`는 옵션 방식으로 고정했습니다. 두 기능과 카테고리/예산 저장은 임시 파일을 완성한 뒤 `os.replace`로 원본을 교체합니다.

## CSV 가져오기/내보내기

UTF-8, 헤더 포함이며 열 순서는 다음과 같습니다.

| column | 필수 | 형식 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | income 또는 expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양의 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표로 구분한 문자열 |

가져오기에서 유효하지 않은 행은 `skipped`로 집계합니다. 내보내기는 `--month` 또는 `--from`/`--to` 조건이 반드시 필요합니다.

## 구조와 핵심 설계

- `models.py`: `Transaction` 데이터 모양과 변환
- `repositories.py`: 세 JSONL 파일 생성, 제너레이터 읽기, 원자적 쓰기
- `services.py`: 검증을 조합한 CRUD/검색/요약/예산/CSV 업무 규칙
- `cli.py`: 명령과 화면 입출력
- `decorators.py`: 예상 오류를 친절한 메시지와 종료 코드 1로 변환
- `validators.py`: 날짜, 월, 타입, 금액 검증

`stream_transactions()`는 `yield`로 거래를 한 건씩 전달합니다. 최신순 조회도 파일을 통째로 리스트로 만들지 않고 뒤에서부터 블록 단위로 읽습니다. 따라서 거래 수가 커져도 메모리 사용량이 파일 전체 크기에 비례해 증가하지 않습니다.

## 테스트

```bash
python -m unittest discover -v
```
# cdy_B2_1_pre
# cdy_B2_1_pre
