import streamlit as st
import pandas as pd
import re
from itertools import permutations
import plotly.express as px

st.set_page_config(page_title="급식 규칙 찾기", layout="wide")

st.title("🍱 송탄고 급식 메뉴 연관 규칙 탐색기")

DATA_URL = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"

@st.cache_data
def load_and_process_data(url):
    df = pd.read_csv(url, encoding='utf-8')
    
    baskets = []
    for menu_str in df['메뉴'].dropna():
        # 괄호 및 괄호 안의 내용 제거
        cleaned = re.sub(r'\([^)]*\)', '', str(menu_str))
        # 세로줄(|) 단위 분리 및 공백 제거
        items = [item.strip() for item in cleaned.split('|') if item.strip()]
        # 하루 식단 단위 중복 메뉴 제거
        unique_items = sorted(list(set(items)))
        if unique_items:
            baskets.append(unique_items)
            
    total_baskets = len(baskets)
    
    # 단일 메뉴 출현 빈도 집계
    item_counts = {}
    for basket in baskets:
        for item in basket:
            item_counts[item] = item_counts.get(item, 0) + 1
            
    # 메뉴 쌍 출현 빈도 집계 (조건-결과 양방향)
    pair_counts = {}
    for basket in baskets:
        for a, b in permutations(basket, 2):
            pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1
            
    # 연관 규칙 지표 산출
    rules = []
    for (a, b), co_cnt in pair_counts.items():
        support = co_cnt / total_baskets
        confidence = co_cnt / item_counts[a]
        prob_b = item_counts[b] / total_baskets
        lift = confidence / prob_b if prob_b > 0 else 0
        
        rules.append({
            '조건': a,
            '결과': b,
            '동시': co_cnt,
            '지지도': round(support, 4),
            '신뢰도': round(confidence, 4),
            '향상도': round(lift, 4)
        })
        
    rules_df = pd.DataFrame(rules)
    unique_menus = sorted(list(item_counts.keys()))
    unique_pairs_count = len(set(tuple(sorted([a, b])) for (a, b) in pair_counts.keys()))
    
    return rules_df, total_baskets, len(unique_menus), unique_pairs_count, unique_menus, item_counts, pair_counts

try:
    rules_df, total_days, total_menus, total_pairs, menu_list, item_counts, pair_counts = load_and_process_data(DATA_URL)

    # 1. 상단 요약 지표 (한 줄 표시)
    col1, col2, col3 = st.columns(3)
    col1.metric("급식 일수", f"{total_days}일")
    col2.metric("메뉴 종류 수", f"{total_menus}개")
    col3.metric("함께 나온 적이 있는 메뉴 쌍의 수", f"{total_pairs}개")

    st.markdown("---")

    # 2. 필터 및 정렬 컨트롤러
    filter_col, sort_col = st.columns(2)

    with filter_col:
        selected_menu = st.selectbox("📌 메뉴 선택 (해당 메뉴가 포함된 규칙 필터링)", ["전체"] + menu_list)

    with sort_col:
        sort_by = st.radio("📊 정렬 기준", ["향상도 순", "신뢰도 순", "동시 순"], horizontal=True)

    # 최소 동시 일수 슬라이더 (1~10, 기본값 1)
    min_co_days = st.slider("🗓️ 최소 동시 일수 선택", min_value=1, max_value=10, value=1)

    # 필터링 동작
    filtered_df = rules_df.copy()
    
    if selected_menu != "전체":
        filtered_df = filtered_df[(filtered_df['조건'] == selected_menu) | (filtered_df['결과'] == selected_menu)]

    # 최소 동시 일수 이상인 규칙만 선택
    filtered_df = filtered_df[filtered_df['동시'] >= min_co_days]

    # 정렬 동작
    sort_map = {
        "향상도 순": "향상도",
        "신뢰도 순": "신뢰도",
        "동시 순": "동시"
    }
    filtered_df = filtered_df.sort_values(by=sort_map[sort_by], ascending=False).reset_index(drop=True)

    # 남은 규칙 수 한 줄 안내
    st.markdown(f"🔍 **현재 조건(최소 동시 일수 {min_co_days}일 이상)에 해당하는 규칙 수:** **{len(filtered_df)}**개")

    # 3. Plotly 가로 막대그래프 (향상도 상위 10개)
    st.subheader("📈 향상도(Lift) 상위 10개 규칙")
    top10_df = filtered_df.sort_values(by="향상도", ascending=False).head(10).copy()

    if not top10_df.empty:
        top10_df['규칙'] = top10_df['조건'] + " ➔ " + top10_df['결과']
        top10_plot = top10_df.sort_values(by="향상도", ascending=True)

        fig = px.bar(
            top10_plot,
            x="향상도",
            y="규칙",
            orientation="h",
            text="향상도",
            labels={"향상도": "향상도 (Lift)", "규칙": "연관 규칙"},
            color="향상도",
            color_continuous_scale="Blues"
        )
        fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig.update_layout(height=420, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("선택된 조건에 해당하는 규칙 데이터가 없습니다.")

    # 4. 연관 규칙 데이터표 출력
    st.subheader("📋 연관 규칙 목록")
    st.dataframe(filtered_df, use_container_width=True)

    st.markdown("---")

    # 5. 함께 나온 적 없는 짝 탐색기
    st.subheader("🚫 함께 나온 적 없는 짝 탐색기")

    target_menu = st.selectbox(
        "📌 미조합 메뉴 탐색을 위한 기준 메뉴 선택",
        menu_list,
        key="never_paired_select"
    )

    target_days = item_counts.get(target_menu, 0)
    st.write(f"👉 **{target_menu}**이(가) 급식에 나온 총 일수: **{target_days}일**")

    # 한 번도 같이 나오지 않았고(co_occurrence == 0) 혼자서는 10일 이상 나온 메뉴 추출
    never_paired_list = []
    for menu, count in item_counts.items():
        if menu == target_menu:
            continue
        if (target_menu, menu) not in pair_counts and count >= 10:
            never_paired_list.append({
                "메뉴": menu,
                "나온 날 수": count
            })

    never_df = pd.DataFrame(never_paired_list)

    if not never_df.empty:
        never_df = never_df.sort_values(by="나온 날 수", ascending=False).reset_index(drop=True)
        st.write(f"**'{target_menu}'**와(과) 한 번도 함께 나오지 않았으면서 10일 이상 나온 메뉴 (총 {len(never_df)}개):")
        st.dataframe(never_df, use_container_width=True)
    else:
        st.info(f"**'{target_menu}'**와(과) 한 번도 함께 나오지 않았으면서 10일 이상 나온 메뉴가 없습니다.")

except Exception as e:
    st.error(f"데이터를 불러오거나 처리하는 중 오류가 발생했습니다: {e}")
