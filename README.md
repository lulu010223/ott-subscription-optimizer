# OTT Subscription Optimizer

사용자의 콘텐츠 취향과 구독 예산을 기반으로 **최적의 OTT 구독 조합을 추천하는 의사결정 지원 시스템**입니다.

Netflix, Disney+, TVING, Wavve, Watcha의 콘텐츠 및 요금제 데이터를 분석하여 단순히 하나의 OTT를 추천하는 것이 아니라, 사용자의 취향을 가장 효과적으로 충족할 수 있는 **OTT 구독 포트폴리오**를 제안하는 것을 목표로 합니다.

## 프로젝트 개요

OTT 서비스마다 제공하는 콘텐츠와 구독 요금이 다르기 때문에 여러 서비스를 동시에 이용할 경우 구독 비용이 증가합니다. 반면 가격만 비교해서는 각 사용자의 콘텐츠 취향을 충분히 반영하기 어렵습니다.

본 프로젝트에서는 사용자가 재미있게 시청한 콘텐츠와 선호 장르를 기반으로 취향을 분석하고, 각 OTT가 해당 취향을 얼마나 충족하는지 계산합니다. 이후 구독 비용과 취향 커버리지를 함께 고려하여 사용자에게 적합한 OTT 조합과 대안을 제공합니다.

### 주요 입력

- 최근 재미있게 시청한 영화·드라마
- 선호 장르 (선택)
- 월 구독 예산
- 월별 평균 시청량 (선택)
- 현재 이용 중인 OTT (선택)

### 주요 출력

- 사용자 콘텐츠 취향 분석
- 최적 OTT 구독 조합 및 월 구독료
- 취향 커버리지 (Preference Coverage)
- OTT 간 콘텐츠 중복도
- OTT별 취향 맞춤 콘텐츠
- 대안 구독 조합
- AI 기반 추천 근거 설명

## 추천 시스템

추천 시스템은 사용자의 취향과 OTT별 콘텐츠 구성을 다음과 같은 과정으로 분석합니다.

```text
사용자 콘텐츠 선택
        ↓
장르·키워드 기반 취향 프로필 생성
        ↓
Content Embedding
        ↓
User Preference Vector 생성
        ↓
Cosine Similarity 기반 콘텐츠 취향 유사도 계산
        ↓
OTT별 Weighted Preference Coverage 계산
        ↓
예산 내 OTT 조합 생성
        ↓
Pareto Front 및 한계 효율 분석
        ↓
Knee Point 기반 최적 조합 선정
        ↓
Gemini 기반 추천 근거 생성
```

추천 결과는 생성형 AI가 직접 결정하지 않고, **데이터 기반 추천 알고리즘이 조합을 선정한 뒤 Gemini가 해당 결과를 설명하는 구조**로 설계합니다.

## 데이터

콘텐츠 메타데이터 및 OTT 제공 정보는 TMDB API를 활용하여 수집합니다.

- 대상 OTT: Netflix, Disney+, TVING, Wavve, Watcha
- 콘텐츠: 영화 및 TV 프로그램
- 주요 데이터
  - 장르
  - 키워드
  - OTT 제공 정보
  - OTT 요금제 및 번들 정보

수집된 데이터는 전처리 후 Cloud Storage와 BigQuery에 적재하여 분석 및 추천에 활용합니다.

## System Architecture

```text
TMDB API
   ↓
Python ETL
   ↓
Cloud Storage
   ↓
BigQuery
   ↓
Embedding / Preference Analysis
   ↓
Python Recommendation Engine
   ↓
Gemini
   ↓
Streamlit
   ↓
Cloud Run
```

## Tech Stack

### Data & Backend
- Python
- TMDB API
- BigQuery
- Cloud Storage

### AI & Recommendation
- Vertex AI Text Embeddings
- Cosine Similarity
- Pareto-based Optimization
- Gemini API

### Application & Deployment
- Streamlit
- Cloud Run

### Cloud
- Google Cloud Platform (GCP)

