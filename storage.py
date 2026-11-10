"""쇼핑 리스트 데이터 로드/저장과 아이템 조작 로직 (Streamlit에 의존하지 않음).

저장 파일이 유일한 원본이다. 여러 탭/접속자가 동시에 써도 서로의 변경을 덮어쓰지 않도록
모든 변경은 update()로 "잠금 → 파일에서 최신 목록 읽기 → 변경 → 원자적 저장" 순서로 처리한다.
"""

import json
import os
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypeVar

DATA_FILE = Path(__file__).resolve().parent / "data" / "shopping_list.json"
MAX_QUANTITY = 99

# Streamlit은 세션마다 스레드가 다르지만 모듈은 한 번만 로드되므로 이 잠금을 모든 세션이 공유한다.
_lock = threading.RLock()

T = TypeVar("T")


class StorageError(Exception):
    """저장 파일을 읽거나 쓸 수 없는 경우. 이때는 데이터를 덮어쓰지 않는다."""


# ===== 저장소 =====

def _parse_checked(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return value is True


def _normalize(item: dict) -> dict | None:
    """저장 파일의 아이템을 데이터 모델에 맞게 정리한다. 이름이 없으면 버린다."""
    name = str(item.get("name", "")).strip()
    if not name:
        return None
    try:
        quantity = min(MAX_QUANTITY, max(1, int(item.get("quantity", 1))))
    except (TypeError, ValueError):
        quantity = 1
    return {
        "id": str(item.get("id") or uuid.uuid4()),
        "name": name,
        "quantity": quantity,
        "checked": _parse_checked(item.get("checked", False)),
        "created_at": str(item.get("created_at") or datetime.now().isoformat(timespec="seconds")),
    }


def _quarantine_corrupt_file() -> str:
    """손상된 파일을 덮어쓰지 않도록 다른 이름으로 옮겨 보관하고 안내 문구를 반환한다."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")  # 마이크로초까지 넣어 기존 보관본을 덮어쓰지 않음
    backup = DATA_FILE.with_name(f"{DATA_FILE.stem}.corrupt-{stamp}.json")
    try:
        os.replace(DATA_FILE, backup)
    except OSError as e:
        raise StorageError(f"손상된 저장 파일을 보관하지 못했습니다: {e}") from e
    return f"저장 파일이 손상되어 빈 목록으로 시작합니다. 원본은 data/{backup.name}에 보관했습니다."


def _load() -> tuple[list[dict], str | None]:
    try:
        text = DATA_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], None
    except UnicodeDecodeError:
        return [], _quarantine_corrupt_file()
    except OSError as e:
        raise StorageError(f"저장 파일을 읽지 못했습니다: {e}") from e

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], _quarantine_corrupt_file()
    if not isinstance(data, list):
        return [], _quarantine_corrupt_file()

    items, seen_ids = [], set()
    for raw in data:
        if not isinstance(raw, dict):
            continue
        item = _normalize(raw)
        if item is None:
            continue
        if item["id"] in seen_ids:  # 중복 id는 위젯 key 충돌을 일으키므로 새로 발급
            item["id"] = str(uuid.uuid4())
        seen_ids.add(item["id"])
        items.append(item)
    return items, None


def _save(items: list[dict]) -> None:
    """임시 파일에 다 쓴 뒤 한 번에 교체한다. 쓰는 도중 멈춰도 기존 파일은 깨지지 않는다."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=DATA_FILE.parent, prefix=".shopping_list-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(5):  # Windows에서 백신 등이 파일을 잠깐 잡고 있으면 교체가 실패할 수 있음
            try:
                os.replace(tmp_path, DATA_FILE)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except OSError as e:
        Path(tmp_path).unlink(missing_ok=True)
        raise StorageError(f"저장하지 못했습니다: {e}") from e


def load_items() -> tuple[list[dict], str | None]:
    """최신 목록과 (손상 파일을 보관했다면) 안내 문구를 반환한다."""
    with _lock:
        return _load()


def update(change: Callable[[list[dict]], T]) -> tuple[T, str | None]:
    """잠근 상태에서 최신 목록을 읽어 change(items)로 바꾸고 저장한다.

    change의 반환값과 (손상 파일을 보관했다면) 안내 문구를 반환한다.
    """
    with _lock:
        items, notice = _load()
        result = change(items)
        _save(items)
        return result, notice


# ===== 아이템 조작 (목록을 직접 바꾸는 순수 함수) =====

def validate(name: str, quantity: int) -> str | None:
    """입력이 올바르면 None, 아니면 사용자에게 보여 줄 오류 문구를 반환한다."""
    if not name.strip():
        return "아이템 이름을 입력해 주세요."
    if not 1 <= quantity <= MAX_QUANTITY:
        return f"수량은 1~{MAX_QUANTITY} 사이로 입력해 주세요."
    return None


def find_item(items: list[dict], item_id: str) -> dict | None:
    return next((item for item in items if item["id"] == item_id), None)


def add_item(items: list[dict], name: str, quantity: int = 1) -> str | None:
    """아이템을 목록 끝에 추가한다. 입력이 잘못되면 추가하지 않고 오류 문구를 반환한다."""
    error = validate(name, quantity)
    if error:
        return error
    items.append({
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "quantity": int(quantity),
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    return None


def update_item(items: list[dict], item_id: str, name: str, quantity: int) -> str | None:
    """아이템의 이름과 수량을 바꾼다. 실패하면 오류 문구를 반환한다."""
    error = validate(name, quantity)
    if error:
        return error
    item = find_item(items, item_id)
    if item is None:
        return "이미 삭제된 아이템입니다."
    item["name"] = name.strip()
    item["quantity"] = int(quantity)
    return None


def delete_item(items: list[dict], item_id: str) -> None:
    items[:] = [item for item in items if item["id"] != item_id]


def set_checked(items: list[dict], item_id: str, checked: bool) -> None:
    item = find_item(items, item_id)
    if item is not None:
        item["checked"] = checked


def clear_checked(items: list[dict]) -> None:
    items[:] = [item for item in items if not item["checked"]]
