

# 📚 다독다독 프로젝트

<div align="center">
<img width="400" alt="프로젝트 로고" src="https://github.com/HICC-2024-2-project-contest/team1/blob/master/KakaoTalk_20250119_221115619.png">

<div align="left">



---

## 📝 프로젝트 소개

다독다독은 독서 기록 및 관리, 추천과 공유를 지원하는 웹 플랫폼입니다.  
사용자가 읽은 책을 쉽게 기록하고 다른 사용자와 상호작용할 수 있는 환경을 제공합니다.

---



## 🌟 주요 기능

### **1) 사용자 인증 (User Authentication)**

사용자 인증 및 프로필 관리를 위한 API입니다.

- 회원가입 및 로그인 (JWT 토큰 발급)
- 프로필 조회 및 수정
- 프로필 이미지 관리
- 로그아웃 기능

### **2) 도서 검색 & 추천 (Book Search & Recommendation)**

네이버 API를 활용하여 도서 정보를 검색하고 추천하는 기능을 제공합니다.

- 키워드 또는 ISBN을 이용한 도서 검색
- 리뷰 기반 추천 시스템을 활용한 맞춤 도서 추천

### **3) 독서 기록 (Review & Library)**

사용자가 읽은 책을 기록하고 리뷰를 작성하는 기능을 제공합니다.

- 도서 리뷰 작성, 수정, 삭제
- 특정 도서에 대한 리뷰 목록 조회
- 좋아요 및 댓글 기능

### **4) 독서 목표 (Goal Management)**

사용자가 연간 및 월간 독서 목표를 설정하고 진행 상황을 확인할 수 있도록 합니다.

- 연간 및 월간 목표 설정
- 독서 진행률 조회 및 수정

### **5) 추천 시스템 (Recommendation)**

네이버 API를 활용하여 추천하는 기능.

- 관련 도서 추천

---
## ⭐️ 프로젝트 플랜

| 작업명                     | 주차   | 날짜                       | 상태     | 역할         | 비고                                |
|----------------------------|--------|----------------------------|----------|--------------|-------------------------------------|
| 사용자 관리                | 1주차  | 2025년 1월 20일 ~ 2025년 1월 23일 | 시작 전 | 회원가입, 로그인/로그아웃 API 개발 | -                                   |
| 도서 CRUD 기능             | 1주차  | 2025년 1월 24일 ~ 2025년 1월 26일 | 시작 전 | 등록, 수정, 삭제 API 및 프론트 개발 | -                                   |
| API와 프론트엔드 연동 및 기본 화면 구성 | 1주차  | 2025년 1월 27일 ~ 2025년 1월 29일 | 시작 전 | 기본화면 - 메인 페이지, 마이페이지 UI 제작 | -                                   |
| 1차 테스트 및 코드 리팩토링 | 2주차  | 2025년 1월 30일           | 시작 전 | -            | -                                   |
| 감상문, 목표 설정/통계       | 2주차  | 2025년 1월 31일 ~ 2025년 2월 4일 | 시작 전 | 감상문 작성/조회 기능 개발, 독서 목표 설정 및 통계 시각화 | -                                   |
| 추천 기능, 감상문            | 3주차  | 2025년 2월 5일 ~ 2025년 2월 8일 | 시작 전 | 평점 기반 추천 API, 감상문 공유 및 댓글 기능 구현 | -                                   |
| 전체 기능 통합 및 시스템 테스트 | 3주차  | 2025년 2월 9일           | 시작 전 | -            | -                                   |
| 최종 배포 준비 및 발표 자료 작성 | 4주차  | 2025년 2월 10일 ~ 2025년 2월 14일  | 시작 전 | -            | -                                   |

---

## 📂 시작 가이드

### Requirements
- [Node.js 14.19.3](https://nodejs.org/ca/blog/release/v14.19.3/)
- [Npm 9.2.0](https://www.npmjs.com/package/npm/v/9.2.0)
- [Django 4.0](https://www.djangoproject.com/)

### Installation
```bash
$ git clone https://github.com/nemanic3/Function_Specification.git
$ cd Function_Specification
```

#### Backend
```bash
$ cd backend
$ pip install -r requirements.txt
$ python manage.py runserver
```

#### Frontend
```bash
$ cd frontend
$ npm install
$ npm start
```

---

## 🧑‍🤝‍🧑 팀 구성

|      팀장 신성현       |          강 산        |       이나나          |       곽유나          |                                                                                                                
| :------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | 
|   <img width="160px" src="https://avatars.githubusercontent.com/u/188848771?v=4" />    |   <img width="160px" src="https://avatars.githubusercontent.com/u/139611910?s=400&u=c3c4a6eb05429b73e109293cac9ad11680365b1a&v=4" />    |    <img width="160px" src="https://github.com/user-attachments/assets/3471d8d4-b25d-49b1-8980-a23f877fbbc8" />   |    <img width="160px" src="https://avatars.githubusercontent.com/u/195542716?s=400&u=42372de0252734a071646c6136a851f9c088cf62&v=4" />    |
| **21학번 백엔드** | **23학번 프론드엔드**  | **23학번 백엔드**  | **24학번 디자이너**  |

---

## 🔧 기술 스택

### Environment
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=Git&logoColor=white)
![Github](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=GitHub&logoColor=white)

### Frontend
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=Bootstrap&logoColor=white)

### Backend
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/python-3776AB?style=for-the-badge&logo=python&logoColor=white)

### Design
![Figma](https://img.shields.io/badge/figma-F24E1E?style=for-the-badge&logo=figma&logoColor=white)

### Communication
![Slack](https://img.shields.io/badge/Slack-4A154B?style=for-the-badge&logo=Slack&logoColor=white)
![Notion](https://img.shields.io/badge/Notion-000000?style=for-the-badge&logo=Notion&logoColor=white)
![Discord](https://img.shields.io/badge/discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)

---

## 💡 아키텍쳐

### 디렉토리 구조
```bash
├── backend : Django 기반 백엔드
│   ├── api : 데이터베이스 모델 및 API 정보
│   ├── config : 서버 및 환경 설정
│   ├── public : 업로드된 데이터 관리
├── frontend : React 기반 프론트엔드
│   ├── components : UI 컴포넌트
│   ├── pages : 라우팅 및 페이지별 구성
│   ├── styles : 스타일 관리
└── README.md : 프로젝트 설명 파일

```
