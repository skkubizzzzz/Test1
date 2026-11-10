"""쇼핑 리스트 Streamlit 앱."""

import html

import streamlit as st

import storage

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒")

st.session_state.setdefault("editing_id", None)
st.session_state.setdefault("add_warning", None)
st.session_state.setdefault("edit_warning", None)
st.session_state.setdefault("notice", None)
st.session_state.setdefault("error", None)


# ===== 콜백 (위젯 이벤트 → 파일의 최신 목록에 변경 적용 → 저장) =====
# 목록은 세션에 들고 있지 않고 항상 파일에서 다시 읽는다. 그래야 다른 탭에서 한 변경을 덮어쓰지 않는다.

def _apply(change):
    """storage.update()를 실행하고, 안내/오류 문구는 다음 화면에 보이도록 세션에 남긴다."""
    try:
        result, notice = storage.update(change)
    except storage.StorageError as e:
        st.session_state["error"] = str(e)
        return None
    if notice:
        st.session_state["notice"] = notice
    return result


def on_add() -> None:
    name = st.session_state["add_name"]
    quantity = st.session_state["add_quantity"]
    st.session_state["add_warning"] = _apply(lambda items: storage.add_item(items, name, quantity))


def on_toggle(item_id: str) -> None:
    checked = st.session_state[f"check_{item_id}"]
    _apply(lambda items: storage.set_checked(items, item_id, checked))


def on_start_edit(item_id: str) -> None:
    st.session_state["editing_id"] = item_id
    st.session_state["edit_warning"] = None


def on_save_edit(item_id: str) -> None:
    name = st.session_state[f"edit_name_{item_id}"]
    quantity = st.session_state[f"edit_quantity_{item_id}"]
    error = _apply(lambda items: storage.update_item(items, item_id, name, quantity))
    if error:
        st.session_state["edit_warning"] = error
    else:
        on_cancel_edit()


def on_cancel_edit() -> None:
    st.session_state["editing_id"] = None
    st.session_state["edit_warning"] = None


def on_delete(item_id: str) -> None:
    _apply(lambda items: storage.delete_item(items, item_id))


def on_clear_checked() -> None:
    _apply(storage.clear_checked)


MARKDOWN_CHARS = set("*_~`$:[]{}()#+-!|\\^=.")


def safe_html(text: str) -> str:
    """사용자 입력을 HTML에 넣기 위해 이스케이프한다.

    html.escape()로 태그를 막고, 남은 문장부호도 문자 참조(&#NN;)로 바꿔서
    마크다운(**, ~~), 수식($), 색상 지시어(:red[...])로 해석되지 않게 한다.
    """
    return "".join(f"&#{ord(ch)};" if ch in MARKDOWN_CHARS else html.escape(ch) for ch in text)


# ===== 데이터 로드 =====

try:
    items, load_notice = storage.load_items()
except storage.StorageError as e:
    items, load_notice = [], None
    st.session_state["error"] = str(e)
if load_notice:
    st.session_state["notice"] = load_notice

# 수정 중이던 아이템이 (다른 탭 등에서) 삭제됐으면 수정 모드를 끝낸다.
if st.session_state["editing_id"] and storage.find_item(items, st.session_state["editing_id"]) is None:
    on_cancel_edit()
    st.session_state["notice"] = "수정하던 아이템이 다른 곳에서 삭제되어 수정을 취소했습니다."
editing_id = st.session_state["editing_id"]


# ===== 스타일 =====

st.markdown(
    """
<style>
/* 입력창의 영어 안내 문구("Press Enter to submit form") 숨김 */
[data-testid="InputInstructions"] { display: none; }

/* 아이템 행: 모바일에서도 세로로 쌓이지 않고 한 줄 유지 */
[class*="st-key-row_"] {
    border-bottom: 1px solid rgba(128, 128, 128, 0.25);
    padding: 0.35rem 0;
}
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem;
}
[class*="st-key-row_"] [data-testid="stColumn"],
[class*="st-key-row_"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {
    display: flex;
    flex-direction: column;
    justify-content: center;
}
[class*="st-key-row_"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"] { height: 100%; gap: 0; }
[class*="st-key-row_"] [data-testid="stColumn"] {
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 0 !important;
}
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(2) {
    flex: 1 1 0 !important;
}
[class*="st-key-row_"] [data-testid="stCheckbox"] label { min-height: 2.5rem; align-items: center; }

/* 아이콘 버튼: 손가락으로 누르기 쉬운 크기 */
[class*="st-key-row_"] button {
    min-width: 2.75rem;
    min-height: 2.75rem;
    padding: 0.25rem 0.5rem;
}
/* 아이콘 버튼의 글자("수정"/"삭제")는 화면에서만 숨기고 화면 낭독기에는 읽히게 함 */
[class*="st-key-row_"] button [data-testid="stMarkdownContainer"] {
    position: absolute !important;
    width: 1px; height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
}

/* Streamlit 기본 문단 여백(마지막 문단 margin-bottom: -1rem)을 덮어써서 세로 가운데 정렬 */
.item-name, .item-qty { margin: 0 !important; }
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
.item-name { font-size: 1.05rem; line-height: 1.4; overflow-wrap: anywhere; }
.item-name.done { text-decoration: line-through; opacity: 0.5; }
.item-qty { font-size: 0.95rem; opacity: 0.75; white-space: nowrap; }
.item-qty.done { opacity: 0.4; }

.empty-state {
    text-align: center;
    padding: 2.5rem 1rem;
    border: 1px dashed rgba(128, 128, 128, 0.4);
    border-radius: 0.75rem;
    opacity: 0.8;
}
.empty-state .icon { font-size: 2.5rem; }

@media (max-width: 640px) {
    /* 좁은 화면에서 제목이 두 줄로 깨지지 않게, 위쪽 여백도 줄여 목록이 더 보이게 */
    h1 { font-size: 1.9rem !important; }
    [data-testid="stMainBlockContainer"] { padding-top: 2.5rem !important; }

    /* 입력 폼: 이름은 한 줄 전체, 수량과 추가 버튼은 다음 줄에 나란히 */
    [data-testid="stForm"]:has(input[aria-label="아이템 이름"]) [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    [data-testid="stForm"]:has(input[aria-label="아이템 이름"]) [data-testid="stColumn"]:nth-child(1) {
        flex: 1 1 100% !important; min-width: 100% !important; width: 100% !important;
    }
    [data-testid="stForm"]:has(input[aria-label="아이템 이름"]) [data-testid="stColumn"]:nth-child(2) {
        flex: 1 1 0 !important; min-width: 0 !important; width: auto !important;
    }
    [data-testid="stForm"]:has(input[aria-label="아이템 이름"]) [data-testid="stColumn"]:nth-child(3) {
        flex: 0 0 6rem !important; min-width: 6rem !important; width: 6rem !important;
    }

    /* 수량 +/- 버튼을 손가락으로 누르기 쉽게 */
    [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {
        min-width: 2.75rem !important;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


# ===== 화면 =====

st.title("🛒 쇼핑 리스트")

if st.session_state["error"]:
    st.error(st.session_state["error"])
    st.session_state["error"] = None
if st.session_state["notice"]:
    st.warning(st.session_state["notice"])
    st.session_state["notice"] = None

# ===== 진행 현황 (F-08) =====
total = len(items)
done = sum(item["checked"] for item in items)
if total:
    label = "🎉 모두 샀어요!" if done == total else f"{total}개 중 {done}개 완료"
    st.progress(done / total, text=label)

# ===== 입력 폼 (F-01) =====
# 수량에 최소/최대값을 두면 범위 밖 입력 시 Streamlit이 아무 안내 없이 제출을 막는다.
# 그래서 범위는 콜백에서 검사하고 한국어 경고를 띄운다.
with st.form("add_form", clear_on_submit=True, border=False):
    name_col, qty_col, add_col = st.columns([5, 2, 1.3], vertical_alignment="bottom")
    name_col.text_input("아이템 이름", key="add_name", placeholder="예: 우유")
    qty_col.number_input("수량", key="add_quantity", value=1, step=1)
    add_col.form_submit_button("추가", on_click=on_add, type="primary", width="stretch")
if st.session_state["add_warning"]:
    st.warning(st.session_state["add_warning"])
    st.session_state["add_warning"] = None  # 다음 동작 때는 경고를 다시 보이지 않음

# ===== 필터 (F-09) =====
view = st.radio("보기", ["전체", "미완료", "완료"], horizontal=True, key="filter",
                label_visibility="collapsed")
if view == "미완료":
    matches = lambda item: not item["checked"]  # noqa: E731
elif view == "완료":
    matches = lambda item: item["checked"]  # noqa: E731
else:
    matches = lambda item: True  # noqa: E731
# 수정 중인 아이템은 필터와 상관없이 계속 보여서 입력하던 내용을 잃지 않게 한다.
visible = [item for item in items if matches(item) or item["id"] == editing_id]

# ===== 목록 (F-02~F-05) =====
if not items:
    st.markdown(
        '<div class="empty-state"><div class="icon">🧺</div>'
        "<p>쇼핑 리스트가 비어 있습니다.<br>아이템을 추가해 보세요.</p></div>",
        unsafe_allow_html=True,
    )
elif not visible:
    st.markdown(
        f'<div class="empty-state"><p>\'{view}\' 항목이 없습니다.</p></div>',
        unsafe_allow_html=True,
    )

for item in visible:
    item_id = item["id"]
    if editing_id == item_id:
        with st.form(f"edit_form_{item_id}"):
            e_name, e_qty = st.columns([3, 1.4])
            e_name.text_input("이름", value=item["name"], key=f"edit_name_{item_id}")
            e_qty.number_input("수량", value=item["quantity"], step=1,
                               key=f"edit_quantity_{item_id}")
            save_col, cancel_col = st.columns(2)
            save_col.form_submit_button("저장", on_click=on_save_edit, args=(item_id,),
                                        type="primary", width="stretch")
            cancel_col.form_submit_button("취소", on_click=on_cancel_edit,
                                          width="stretch")
        if st.session_state["edit_warning"]:
            st.warning(st.session_state["edit_warning"])
        continue

    # 파일의 최신 체크 상태를 위젯에 반영 (다른 탭에서 바뀐 경우 대비)
    st.session_state[f"check_{item_id}"] = item["checked"]
    with st.container(key=f"row_{item_id}"):
        check_col, name_col, qty_col, edit_col, delete_col = st.columns(
            [0.6, 5, 1, 1, 1], vertical_alignment="center", gap="small"
        )
        check_col.checkbox(
            f"구매 완료: {item['name']}", key=f"check_{item_id}",
            on_change=on_toggle, args=(item_id,), label_visibility="collapsed",
        )
        state = " done" if item["checked"] else ""
        name_col.markdown(
            f'<p class="item-name{state}">{safe_html(item["name"])}</p>',
            unsafe_allow_html=True,
        )
        qty_col.markdown(
            f'<p class="item-qty{state}">×{item["quantity"]}</p>', unsafe_allow_html=True
        )
        # 다른 아이템을 수정하는 중에는 수정 버튼을 막아 입력하던 내용이 사라지지 않게 한다.
        edit_col.button(
            "수정", icon="✏️", key=f"edit_{item_id}",
            help="수정 중인 항목을 먼저 저장하거나 취소하세요" if editing_id else "수정",
            disabled=editing_id is not None,
            on_click=on_start_edit, args=(item_id,),
        )
        delete_col.button("삭제", icon="🗑️", key=f"delete_{item_id}", help="삭제",
                          on_click=on_delete, args=(item_id,))

# ===== 하단 버튼 (F-07) =====
if items:
    st.write("")
    st.button("완료 항목 모두 삭제", on_click=on_clear_checked, disabled=done == 0,
              width="stretch")
