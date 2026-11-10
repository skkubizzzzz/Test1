# 🛒 쇼핑 리스트

아이템을 추가, 수정, 삭제, 체크할 수 있는 간단한 Streamlit 웹 앱입니다. 자세한 요구사항은 [PRD.md](PRD.md)를 참고하세요.

## 설치

```
pip install -r requirements.txt
```

## 실행

```
streamlit run app.py
```

브라우저에서 http://localhost:8501 이 열립니다.

## 데이터 저장

목록은 `data/shopping_list.json`에 저장됩니다. Streamlit Community Cloud에 배포하면 앱이 다시 시작될 때 이 파일이 초기화됩니다.
