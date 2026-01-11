import streamlit as st
st.set_page_config(page_title="顧客・来店管理", layout="wide")
import requests
from datetime import date, datetime
import pandas as pd

GAS_BASE_URL = "https://script.google.com/macros/s/AKfycby8YGTvlubnz6ey7vHhbRd8kd5t8LwiDn5NQKyHsreIrli4YEqJC8vAdkzdbkmIZFbu/exec"

GAS_GET_URL = GAS_BASE_URL + "?action=get"
GAS_POST_URL = GAS_BASE_URL

@st.cache_data
def load_data():
    CUSTOMER_COLUMNS = ["顧客_ID","氏名","ニックネーム","住所","電話番号",
                        "生年月日","勤務先・業種","タバコ_YN","タバコ_銘柄",
                        "好き","苦手","初回来店日","紹介者_氏名","合番_氏名","メモ_顧客"]

    VISIT_COLUMNS = ["来店履歴_ID","顧客_ID","来店日","祝日前_YN",
                    "延長回数","キープ銘柄","担当_氏名","同伴_氏名",
                    "同時来店_氏名","イベント名","メモ_来店","売上金額","領収日"]

    # --- GAS から取得 ---
    res = requests.get(GAS_GET_URL, timeout=30)
    res.raise_for_status()
    data = res.json()

    customer_df = pd.DataFrame(data.get("customer", []))
    visit_df = pd.DataFrame(data.get("visit", []))
    receipt_df = pd.DataFrame(data.get("visit", []))

    # --- 空でも列を保証 ---
    if customer_df.empty:
        customer_df = pd.DataFrame(columns=CUSTOMER_COLUMNS)

    if visit_df.empty:
        visit_df = pd.DataFrame(columns=VISIT_COLUMNS)

    if receipt_df.empty:
        receipt_df = pd.DataFrame(columns=VISIT_COLUMNS)

    return customer_df, visit_df, receipt_df

# =====================
# DataFrame を読み込む
# =====================
customer_df, visit_df, receipt_df = load_data()

# ★ 日付列だけ明示的に None に統一
customer_df["初回来店日"] = customer_df["初回来店日"].where(customer_df["初回来店日"].notna(), None)
visit_df["来店日"] = visit_df["来店日"].where(visit_df["来店日"].notna(), None)
receipt_df["領収日"] = receipt_df["領収日"].where(receipt_df["領収日"].notna(), None)

# --- customer ---
text_cols = customer_df.columns.difference(["生年月日", "初回来店日"])
customer_df[text_cols] = customer_df[text_cols].fillna("")

# --- visit ---
text_cols_visit = visit_df.columns.difference(["来店日","領収日"])
visit_df[text_cols_visit] = visit_df[text_cols_visit].fillna("")

# =====================
# ユーティリティ
# =====================
def next_id(df, col, prefix):
    if df.empty:
        return f"{prefix}00001"
    nums = df[col].astype(str).str.replace(prefix, "", regex=False)
    nums = nums[nums.str.isnumeric()].astype(int)
    return f"{prefix}{nums.max()+1:05d}"

def safe_date(v):
    """
    st.date_input に渡す専用
    → 必ず datetime.date を返す
    """
    if v is None:
        return date.today()

    if isinstance(v, date):
        return v

    if isinstance(v, datetime):
        return v.date()

    if isinstance(v, str) and v.strip() != "":
        try:
            return pd.to_datetime(v).date()
        except:
            return date.today()

def safe_bool(v):
    return str(v).lower() in ("true", "1", "yes")

def safe_int(v, default=0):
    try:
        if v == "" or v is None or pd.isna(v):
            return default
        return int(v)
    except:
        return default

# =====================
# session_state 定義
# =====================
CUSTOMER_STATE_MAP = {
    "input_name": ("氏名", ""),
    "input_nick": ("ニックネーム", ""),
    "input_addr": ("住所", ""),
    "input_tel": ("電話番号", ""),
    "input_birth": ("生年月日", date(2000,1,1)),
    "input_job": ("勤務先・業種", ""),
    "input_smoke": ("タバコ_YN", False),
    "input_brand": ("タバコ_銘柄", ""),
    "input_like": ("好き", ""),
    "input_dislike": ("苦手", ""),
    "input_first_visit": ("初回来店日", date.today()),
    "input_intro_name": ("紹介者_氏名", ""),
    "input_pair_name": ("合番_氏名", ""),
    "input_memo_cus": ("メモ_顧客", ""),
}

VISIT_STATE_MAP = {
    "input_visit_date": ("来店日", date.today()),
    "input_holiday": ("祝日前_YN", False),
    "input_ext": ("延長回数", 0),
    "input_keep": ("キープ銘柄", ""),
    "input_staff": ("担当_氏名", ""),
    "input_accompany": ("同伴_氏名", ""),
    "input_same": ("同時来店_氏名", ""),
    "input_event": ("イベント名", ""),
    "input_memo_vis": ("メモ_来店", ""),
    "input_uri": ("売上金額", 0),
    "input_receipt_date": ("領収日", date(1900,1,1)),
}

def init_state_from_row(state_map, row):
    """
    row（dict）から session_state を一括初期化
    すでに存在するキーは触らない
    """
    for key, (col, default) in state_map.items():
        if key not in st.session_state:
            val = row.get(col, default)

            # 日付だけ特別扱い
            if isinstance(default, date):
                val = safe_date(val)

            st.session_state[key] = val

# =====================
# サイドバー
# =====================
menu = st.sidebar.radio(
    "メニュー",["顧客情報入力","来店情報入力", "顧客別来店履歴", "日付別来店一覧", "売上分析"])

# ★ メニュー切替を検知して初期化
if "prev_menu" not in st.session_state:
    st.session_state.prev_menu = menu

# メニュー切替検知
menu_changed = st.session_state.prev_menu != menu

if menu_changed:
    # 状態リセット
    if menu =="顧客情報入力":
        st.session_state.pop("loaded_customer_id", None)
    st.session_state.pop("selected_visit_id", None)

    for k in ["sales_daily_select", "sales_month_select", "sales_staff_select"]:
        st.session_state.pop(k, None)

    # ★ キャッシュだけクリア
    st.cache_data.clear()

    # ★ 最後に prev_menu 更新
    st.session_state.prev_menu = menu

# =====================
# 顧客情報入力
# =====================
if menu == "顧客情報入力":
    st.header("顧客情報入力")

    # ★ 顧客IDは必ず session_state から取得（未選択時は ""）
    cid = st.session_state.get("current_customer_id", "")
    
    # --- session_state 初期化 ---
    if "selected_customer_name" not in st.session_state:
        st.session_state.selected_customer_name = "（未選択）"

    # --- 顧客区分（customer_mode） ---
    customer_mode = st.radio("顧客区分", ["既存顧客", "新規顧客"],index=1)  #← 0=既存顧客 / 1=新規顧客

    # 顧客区分が変わったら強制リセット
    if "prev_customer_mode" not in st.session_state:
        st.session_state.prev_customer_mode = customer_mode

    if customer_mode == "既存顧客" and customer_df.empty:
        st.info("先に新規顧客を登録してください")
        st.stop()

    row = {}

    if customer_mode == "既存顧客" and not customer_df.empty:
        search_name = st.text_input("氏名検索（部分一致）", "")

        if search_name:
            filtered_df = customer_df[customer_df["氏名"].str.contains(search_name, na=False)]
        else:
            filtered_df = customer_df

        name_list = ["（未選択）"] + sorted(filtered_df["氏名"].unique())

        selected_name = st.selectbox("氏名で選択",name_list,key="input_selected_customer_name")

        if selected_name != "（未選択）":
            row = customer_df[customer_df["氏名"] == selected_name].iloc[0].to_dict()
            cid = row["顧客_ID"]
            st.session_state.current_customer_id = cid     

    # ★ 顧客切替フラグ
    if (cid and st.session_state.get("loaded_customer_id") != cid
            and customer_mode == "既存顧客"):
        st.session_state.loaded_customer_id = cid

        # ---- 顧客情報を一括セット ----
        st.session_state.update({
            "input_name": row.get("氏名", ""),
            "input_nick": row.get("ニックネーム", ""),
            "input_addr": row.get("住所", ""),
            "input_tel": row.get("電話番号", ""),
            "input_birth": safe_date(row.get("生年月日")),
            "input_job": row.get("勤務先・業種", ""),
            "input_smoke": safe_bool(row.get("タバコ_YN")),
            "input_brand": row.get("タバコ_銘柄", ""),
            "input_like": row.get("好き", ""),
            "input_dislike": row.get("苦手", ""),
            "input_first_visit": safe_date(row.get("初回来店日")),
            "input_intro_name": row.get("紹介者_氏名", ""),
            "input_pair_name": row.get("合番_氏名", ""),
            "input_memo_cus": row.get("メモ_顧客", ""),
        })

        st.session_state.customer_loaded = True

        # ---- 顧客情報を完全クリア ----
        for k in list(st.session_state.keys()):
            if k.startswith("input_") and k not in (
                "input_name","input_nick","input_addr","input_tel","input_birth",
                "input_job","input_like","input_dislike","input_smoke","input_brand",
                "input_first_visit","input_intro_name","input_pair_name","input_memo_cus"                
            ):
                del st.session_state[k]

        if st.session_state.get("customer_loaded"):
            del st.session_state["customer_loaded"]
            st.rerun()

        # ★ 顧客IDは session_state から取得
        cid = st.session_state.get("current_customer_id", "")

    # =====================
    # 顧客情報（事前定義）
    # =====================
    if customer_mode == "新規顧客":
        init_state_from_row(CUSTOMER_STATE_MAP, {})
        cid = next_id(customer_df, "顧客_ID", "C")
        st.session_state.current_customer_id = cid
    else:
        # ★ 必ず session_state から
        cid = st.session_state.get("current_customer_id")

        if not cid:
            st.error("編集する顧客が特定できません")
            st.stop()

    with st.form("customer_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("氏名", key="input_name")
            nick = st.text_input("ニックネーム", key="input_nick")
            addr = st.text_input("住所", key="input_addr")
            tel = st.text_input("電話番号", key="input_tel")
            birth = st.date_input(
                "生年月日",
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                key="input_birth"
            )
            work = st.text_input("勤務先・業種", key="input_job")
            smoke = st.checkbox("タバコ", key="input_smoke")
            brand = st.text_input("タバコ_銘柄", key="input_brand")

        with col2:
            like = st.text_input("好き", key="input_like")
            dislike = st.text_input("苦手", key="input_dislike")
            first = st.date_input(
                "初回来店日",
                min_value=date(2000, 1, 1),
                max_value=date.today(),
                key="input_first_visit"
            )
            intro = st.text_input("紹介者_氏名", key="input_intro_name")
            pair = st.text_input("合番_氏名", key="input_pair_name")
            memo_cus = st.text_input("メモ_顧客", key="input_memo_cus")

        save_customer = st.form_submit_button("顧客情報を保存")

    def date_to_str(d):
        if isinstance(d, date):
            return d.strftime("%Y-%m-%d")
        return ""
       
    # =====================
    # 顧客情報の保存
    # =====================
    if save_customer:
        if customer_mode == "新規顧客":
            cid = next_id(customer_df, "顧客_ID", "C")
            st.session_state.current_customer_id = cid
        else:
            cid = st.session_state.get("current_customer_id", "")

        payload = {
            "mode": "customer_only",
            "顧客_ID": cid,
            "氏名": name,
            "ニックネーム": nick,
            "住所": addr,
            "電話番号": tel,
            "生年月日": date_to_str(birth),
            "勤務先・業種": work,
            "タバコ_YN": smoke,
            "タバコ_銘柄": brand,
            "好き": like,
            "苦手": dislike,
            "初回来店日": date_to_str(first),
            "紹介者_氏名": intro,
            "合番_氏名": pair,
            "メモ_顧客": memo_cus
        }

        with st.spinner("保存中です…"):
            requests.post(GAS_POST_URL, json=payload, timeout=30)

        # --- 日付カラムを文字列に変換 ---
        for col in ["生年月日", "初回来店日"]:
            if col in customer_df.columns:
                customer_df[col] = customer_df[col].astype(str)

        # ★ ここで必ずキャッシュ破棄＋再読込
        st.cache_data.clear()
        customer_df = load_data()
            
        st.session_state.loaded_customer_id = cid
        st.success("顧客情報を保存しました")

# =====================
# 来店情報入力
# =====================
if menu == "来店情報入力":
    st.header("来店情報入力")

    # ★ 顧客IDは必ず session_state から取得（未選択時は ""）
    cid = st.session_state.get("current_customer_id", "")    
    
    # --- visit_mode の初期化（radioより前！）---
    if "visit_mode" not in st.session_state:
        st.session_state.visit_mode = "新規来店"        

    # ★★★ radio を描画する前で制御 ★★★
    if st.session_state.get("after_visit_save"):
        st.session_state.visit_mode = "新規来店"
        st.session_state.pop("after_visit_save", None)

    # --- 来店入力モード（visit_mode） ---
    visit_mode = st.radio("来店入力モード",["新規来店", "既存来店履歴を編集"],
            index=0,key="visit_mode")  #← 0=新規来店 / 1=既存来店履歴を編集

    search_name = st.text_input("氏名検索（部分一致）", "")

    if search_name:
        filtered_df = customer_df[customer_df["氏名"].str.contains(search_name, na=False)]
    else:
        filtered_df = customer_df

    name_list = ["（未選択）"] + sorted(filtered_df["氏名"].unique())

    selected_name = st.selectbox("氏名で選択",name_list,key="input_selected_customer_name")

    if selected_name != "（未選択）":
        row = customer_df[customer_df["氏名"] == selected_name].iloc[0].to_dict()
        cid = row["顧客_ID"]
        st.session_state.current_customer_id = cid     

    # ★ 顧客IDは session_state から取得
    cid = st.session_state.get("current_customer_id", "")
 
    # =====================
    # 来店情報（事前定義）
    # =====================
    # --- visit_row 初期化 ---
    selected_visit_id = None
    visit_row = {}

    # --- 新規来店 初期化 ---
    if (visit_mode == "新規来店"
        and st.session_state.get("visit_initialized_for") != cid
    ):
        init_state_from_row(CUSTOMER_STATE_MAP, {})
        init_state_from_row(VISIT_STATE_MAP, {})
        st.session_state.visit_initialized_for = cid

    # --- 既存来店 編集 ---
    if visit_mode == "既存来店履歴を編集":
        cid = st.session_state.get("current_customer_id", "")

        target_visits = visit_df[visit_df["顧客_ID"] == cid]

        if target_visits.empty:
            st.info("編集できる来店履歴がありません")
        else:
            visit_labels = (
                target_visits["来店履歴_ID"]
                + "｜"
                + target_visits["来店日"].astype(str)
            )

            selected_label = st.selectbox(
                "編集する来店履歴を選択",
                ["（未選択）"] + visit_labels.tolist(),
                key="visit_edit_select"
            )

            if selected_label != "（未選択）":
                selected_visit_id = selected_label.split("｜")[0]
                visit_row = target_visits[
                    target_visits["来店履歴_ID"] == selected_visit_id
                ].iloc[0].to_dict()

                st.session_state.selected_visit_id = selected_visit_id

                for key, (col, default) in VISIT_STATE_MAP.items():
                    val = visit_row.get(col, default)
                    if isinstance(default, date):
                        val = safe_date(val)
                    st.session_state[key] = val

                # ★ 初期化フラグを明示的に消す
                st.session_state.pop("visit_initialized", None)

    with st.form("visit_form"):
        col1, col2 = st.columns(2)

        with col1:
            visit_date = st.date_input("来店日", key="input_visit_date")
            holiday = st.checkbox("祝日前", key="input_holiday")
            ext = st.number_input("延長回数", min_value=0, max_value=10, key="input_ext")
            keep = st.text_input("キープ銘柄", key="input_keep")
            staff = st.text_input("担当_氏名", key="input_staff")
            accompany = st.text_input("同伴_氏名", key="input_accompany")

        with col2:
            same = st.text_input("同時来店_氏名", key="input_same")
            event = st.text_input("イベント名", key="input_event")
            memovis = st.text_input("メモ_来店", key="input_memo_vis")
            sales = st.number_input("売上金額", min_value=0, step=1000, key="input_uri")
            receipt = st.date_input("領収日", key="input_receipt_date")

        save_visit = st.form_submit_button("来店情報を保存")
                    
    def date_to_str(d):
        if isinstance(d, date):
            return d.strftime("%Y-%m-%d")
        return ""
    
    # =====================
    # 来店情報の保存
    # =====================
    if save_visit:
        cid = st.session_state.get("current_customer_id", "")

        if visit_mode == "新規来店":
            vid = next_id(visit_df, "来店履歴_ID", "V")
        else:
            vid = st.session_state.get("selected_visit_id")

        if not vid:
            st.error("編集する来店履歴が選択されていません")
            st.stop()
    
        payload = {
            "mode": "visit_only",
            "来店履歴_ID": vid,
            "顧客_ID": cid,
            "来店日": date_to_str(visit_date),
            "祝日前_YN": holiday,
            "延長回数": ext,
            "キープ銘柄": keep,
            "担当_氏名": staff,
            "同伴_氏名": accompany,
            "同時来店_氏名": same,
            "イベント名": event,
            "メモ_来店": memovis,
            "売上金額": sales,
            "領収日": date_to_str(receipt_date),
        }

        with st.spinner("保存中です…"):
            requests.post(GAS_POST_URL, json=payload, timeout=30)

        # 来店保存後
        st.session_state.after_visit_save = True
        st.success("来店情報を保存しました")

        # キャッシュのクリア
        st.cache_data.clear()
        visit_df = load_data()

        # 保存後は編集モードを解除するだけ
        st.session_state.pop("selected_visit_id", None)
        st.session_state.pop("visit_edit_select", None)
        
        # --- 日付カラムを文字列に変換 ---
        for col in ["来店日", "領収日"]:
            if col in visit_df.columns:
                visit_df[col] = visit_df[col].astype(str)
       
# ==========================
# 顧客別来店履歴（氏名で選択）
# ==========================
elif menu == "顧客別来店履歴":
    st.header("顧客別来店履歴")

    # ① 検索ボックス（常に定義するのが重要）
    search_name = st.text_input("氏名検索（部分一致）", "")

    # ② 検索結果で顧客を絞り込む
    if search_name:
        filtered_df = customer_df[customer_df["氏名"].
                                str.contains(search_name, case=False, na=False)]
    else:
        filtered_df = customer_df

    # ③ selectbox（必ず表示・未選択あり）
    name_list = ["（未選択）"] + sorted(filtered_df["氏名"].unique())

    selected_name = st.selectbox(
        "氏名で選択",
        name_list,
        key="history_selected_customer_name"
    )

    # ④ 来店履歴表示
    if selected_name == "（未選択）":
        st.info("顧客を選択してください")
    else:
        cid = customer_df.loc[
            customer_df["氏名"] == selected_name, "顧客_ID"
        ].iloc[0]

        target = visit_df[visit_df["顧客_ID"] == cid].copy()
        target["来店日"] = pd.to_datetime(target["来店日"]).dt.date

        if target.empty:
            st.warning("来店履歴がありません")
        else:
            st.dataframe(target.sort_values("来店日", ascending=False))

# =====================
# 日付別来店一覧
# =====================
elif menu == "日付別来店一覧":
    st.header("日付別来店一覧")

    # ★① データ準備
    df = visit_df.copy()
    df["来店日"] = pd.to_datetime(df["来店日"]).dt.date

    # ★② 来店日一覧（存在する日付のみ）
    date_list = sorted(df["来店日"].dropna().unique())

    if not date_list:
        st.warning("来店データがありません")
        st.stop()

    # ★③ 表示用ラベル
    date_count = df.groupby("来店日").size().to_dict()
    date_labels = ["（日付を選択）"] + [f"{d}（{date_count[d]}件）" for d in date_list]

    # ★④ selectbox
    selected_label = st.selectbox("来店日を選択",date_labels,index=0,key="visit_date_select")

    if selected_label == "（日付を選択）":
        st.info("来店日を選択してください")
        st.stop()

    # ★⑤ 表示ラベル → 実日付
    selected_date = date_list[date_labels.index(selected_label) - 1]

    # ★⑥ 来店一覧表示
    st.dataframe(df[df["来店日"] == selected_date].sort_values("来店履歴_ID"))

# =====================
# 売上分析
# =====================
elif menu == "売上分析":
    st.header("売上分析")

    df = visit_df.copy()
    df["来店日"] = pd.to_datetime(df["来店日"])

    # 日別売上-----
    st.subheader("日別売上")

    df["日付"] = df["来店日"].dt.date
    daily = df.groupby("日付")["売上金額"].sum().reset_index()

    date_list = sorted(daily["日付"].unique())
    date_labels = ["（日付を選択）"] + [str(d) for d in date_list]

    selected_date_label = st.selectbox("日付を選択",date_labels,index=0,key="sales_daily_select")

    if selected_date_label != "（日付を選択）":
        selected_date = date_list[date_labels.index(selected_date_label) - 1]
        st.dataframe(daily[daily["日付"] == selected_date])
    else:
        st.info("日付を選択してください")

    # 月別売上-----
    st.subheader("月別売上")

    df["年月"] = df["来店日"].dt.to_period("M").astype(str)
    monthly = df.groupby("年月")["売上金額"].sum().reset_index()

    month_list = sorted(monthly["年月"].unique())
    month_labels = ["（年月を選択）"] + month_list

    selected_month = st.selectbox("年月を選択",month_labels,index=0,key="sales_month_select")

    if selected_month != "（年月を選択）":
        st.dataframe(monthly[monthly["年月"] == selected_month])
    else:
        st.info("年月を選択してください")

    # 担当別売上-----
    st.subheader("担当者別売上")

    staff_sales = (df.groupby("担当_氏名")["売上金額"].sum().reset_index())

    staff_list = sorted(staff_sales["担当_氏名"].dropna().unique())
    staff_labels = ["（担当者を選択）"] + staff_list

    selected_staff = st.selectbox("担当者を選択",staff_labels,index=0,key="sales_staff_select")

    if selected_staff != "（担当者を選択）":
        st.dataframe(staff_sales[staff_sales["担当_氏名"] == selected_staff])
    else:
        st.info("担当者を選択してください")
