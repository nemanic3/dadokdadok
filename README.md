# 📚 다독다독 (DadokDadok)

![DadokDadok Logo](https://img.shields.io/badge/📖_다독다독-독서_관리_서비스-4CAF50?style=for-the-badge)

> **"당신의 독서 기록을 다독여주는 따뜻한 공간"**
> 다독다독은 독서 기록을 체계적으로 관리하고, 다른 사람들과 감상을 나누며 성장할 수 있는 **독서 관리 웹 서비스**입니다.

---

## 📖 프로젝트 소개

다독다독(DadokDadok)은 단순히 책을 읽고 끝내는 것이 아니라, 감상을 기록하고 자신만의 독서 목표를 세워 꾸준한 독서 습관을 기르도록 돕는 서비스입니다. 네이버 API와 연동하여 편리하게 책을 검색하고, 사용자 간의 리뷰 공유를 통해 새로운 책을 추천받을 수 있습니다.

---

## ✨ 주요 기능 (Features)

- 🔍 **도서 검색 & 상세 정보** : 네이버 도서 검색 API를 활용해 원하는 책을 쉽고 빠르게 찾을 수 있습니다.
- ✍️ **독서 기록 & 리뷰** : 읽은 책에 대한 평점과 감상평을 기록하고 다른 사용자와 공유할 수 있습니다.
- 🎯 **독서 목표 관리** : 연간/월간 독서 목표를 설정하고 현재 진행률을 시각적으로 확인합니다.
- 💡 **맞춤형 도서 추천** : 리뷰 기반 추천 시스템으로 취향에 맞는 도서를 제안받습니다.
- 💬 **소통과 공유** : 다른 사용자의 리뷰에 댓글을 남기고 좋아요(추천)를 누르며 소통할 수 있습니다.

---

## 🛠 기술 스택 (Tech Stack)

### **Backend**
- Python, Django, Django REST Framework (DRF)
- SQLite (기본 DB)
- JWT Authentication (SimpleJWT)

### **Frontend**
- HTML5, CSS3, Vanilla JavaScript
- Axios (API 통신)

### **External API**
- Naver Books API

---

## 🚀 시작하기 (Getting Started)

프로젝트를 로컬 환경에서 실행하는 방법입니다.

### 1. 백엔드(Django) 실행
```bash
# 1. backend 폴더로 이동
cd backend

# 2. 가상 환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 데이터베이스 마이그레이션 (필요시)
python manage.py migrate

# 5. 서버 실행
python manage.py runserver
```
*(기본 주소: `http://127.0.0.1:8000`)*

### 2. 프론트엔드 실행
```bash
# 1. frontend 폴더로 이동
cd frontend

# 2. 패키지 설치 (axios 등)
npm install

# 3. 로컬 서버 실행 (http-server 패키지 이용)
npx http-server -p 3000 -a 127.0.0.1
```
*(기본 주소: `http://127.0.0.1:3000/screen/`)*

---

## 📂 프로젝트 구조

```text
dadokdadok/
├── backend/          # Django 기반 API 서버
│   ├── book/         # 도서 검색 및 정보 관리 API
│   ├── goal/         # 독서 목표 설정 및 진행률 API
│   ├── recommendation/ # 도서 추천 로직
│   ├── review/       # 독서 리뷰 및 댓글 관리 API
│   └── user/         # 회원가입, 로그인(JWT), 마이그레이션
│
└── frontend/         # Vanilla JS 기반 프론트엔드
    ├── screen/       # HTML 페이지
    ├── scripts/      # 화면별 API 통신 및 UI 조작 스크립트
    └── styles/       # CSS 스타일시트
```

---

## 🤝 팀원 소개 및 역할

(팀원들의 이름과 역할을 자유롭게 추가해 주세요!)
- **팀원 1** : 백엔드 API 개발 / DB 설계
- **팀원 2** : 프론트엔드 UI/UX 구현 / API 연동
- **팀원 3** : 디자이너 / 기획
