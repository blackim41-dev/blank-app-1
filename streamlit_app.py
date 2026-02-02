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
    CUSTOMER_COLUMNS = ["氏名","ニックネーム","住所","電話番号",
                        "生年月日","勤務先・業種","タバコ_銘柄",
                        "好き","苦手","初回来店日","紹介者_氏名","メモ_顧客","顧客_ID"]

    VISIT_COLUMNS = ["来店日","曜日","同伴_氏名","担当_氏名",
                    "延長回数","キープ銘柄","同時来店_氏名","プレゼント_受","プレゼント_渡",
                    "イベント名","メモ_来店","来店履歴_ID","顧客_ID"]

    # --- GAS から取得 ---
    res = requests.get(GAS_GET_URL, timeout=30)
    res.raise_for_status()
    data = res.json()

    customer_df = pd.DataFrame(data.get("customer", []))
    visit_df = pd.DataFrame(data.get("visit", []))

    # --- 空でも列を保証 ---
    if customer_df.empty:
        customer_df = pd.DataFrame(columns=CUSTOMER_COLUMNS)

    if visit_df.empty:
        visit_df = pd.DataFrame(columns=VISIT_COLUMNS)

    return customer_df, visit_df

# =====================
# DataFrame を読み込む
# =====================
customer_df, visit_df = load_data()

# ★ 日付列だけ明示的に None に統一
customer_df["初回来店日"] = customer_df["初回来店日"].where(customer_df["初回来店日"].notna(), None)
visit_df["来店日"] = visit_df["来店日"].where(visit_df["来店日"].notna(), None)

# --- customer ---
text_cols = customer_df.columns.difference(["生年月日", "初回来店日"])
customer_df[text_cols] = customer_df[text_cols].fillna("")

# --- visit ---
text_cols_visit = visit_df.columns.difference(["来店日"])
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

def get_weekday(d):
    jp = ["月", "火", "水", "木", "金", "土", "日"]
    return jp[d.weekday()]

# =====================
# session_state 定義
# =====================
CUSTOMER_STATE_MAP = {
    "input_name": ("氏名", ""),
    "input_nick": ("ニックネーム", ""),
    "input_addr": ("住所", ""),
    "input_tel": ("電話番号", ""),
    "input_birth": ("生年月日",date(2000,1,1)),
    "input_job": ("勤務先・業種", ""),
    "input_brand": ("タバコ_銘柄", ""),
    "input_like": ("好き", ""),
    "input_dislike": ("苦手", ""),
    "input_first_visit": ("初回来店日", date.today()),
    "input_intro_name": ("紹介者_氏名", ""),
    "input_memo_cus": ("メモ_顧客", ""),
}

VISIT_STATE_MAP = {
    "input_visit_date": ("来店日", date.today()),
    "input_wday": ("曜日", ""),    
    "input_accompany": ("同伴_氏名", ""),
    "input_staff": ("担当_氏名", ""),
    "input_ext": ("延長回数", 0),
    "input_keep": ("キープ銘柄", ""),
    "input_preget": ("プレゼント_受", ""),
    "input_pre": ("プレゼント_渡", ""),
    "input_same": ("同時来店_氏名", ""),    
    "input_event": ("イベント名", ""),
    "input_memo_vis": ("メモ_来店", ""),
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
menu = st.sidebar.radio("メニュー",["顧客情報入力","来店情報入力", "顧客別来店履歴", "日付別来店一覧"])
customer_df, visit_df = load_data()

# ★ メニュー切替を検知して初期化
if "prev_menu" not in st.session_state:
    st.session_state.prev_menu = menu

# メニュー切替検知
menu_changed = st.session_state.prev_menu != menu

if menu_changed:
    # 状態リセット
    st.session_state.pop("loaded_customer_id", None)
    st.session_state.pop("selected_visit_id", None)
    st.session_state.pop("search_customer_name", None)
    st.session_state.pop("search_visit_name", None)

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
    prev = st.session_state.get("prev_customer_mode")

    if prev != customer_mode:
        if customer_mode == "新規顧客":
            for key in CUSTOMER_STATE_MAP:
                st.session_state.pop(key, None)

    st.session_state.prev_customer_mode = customer_mode

    if customer_mode == "既存顧客" and customer_df.empty:
        st.info("先に新規顧客を登録してください")
        st.stop()

    row = {}

    if customer_mode == "既存顧客" and not customer_df.empty:
        search_name = st.text_input("氏名検索（部分一致）", "")
        search_col = customer_df["氏名"].fillna("") + customer_df["ニックネーム"].fillna("")

        if search_name:
            import re
            search_words = re.split(r"\s+", search_name.strip())
            mask = pd.Series(False, index=customer_df.index)
            for w in search_words:
                if w:
                    mask |= search_col.str.contains(w, case=False, na=False)
            filtered_df = customer_df[mask]
        else:
            filtered_df = customer_df

        name_labels = ["（未選択）"]
        name_map = {}

        for _, r in filtered_df.sort_values("ニックネーム").iterrows():
            label = f'{r["氏名"]}（{r["ニックネーム"]}）'
            name_labels.append(label)
            name_map[label] = r["顧客_ID"]

        selected_label = st.selectbox("氏名で選択", name_labels, key="input_selected_customer_name")

        if selected_label != "（未選択）":
            cid = name_map[selected_label]
            row = customer_df[customer_df["顧客_ID"] == cid].iloc[0].to_dict()

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
            "input_brand": row.get("タバコ_銘柄", ""),
            "input_like": row.get("好き", ""),
            "input_dislike": row.get("苦手", ""),
            "input_first_visit": safe_date(row.get("初回来店日")),
            "input_intro_name": row.get("紹介者_氏名", ""),
            "input_memo_cus": row.get("メモ_顧客", ""),
        })

        st.session_state.customer_loaded = True

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

        with col2:
            brand = st.text_input("タバコ_銘柄", key="input_brand")
            like = st.text_input("好き", key="input_like")
            dislike = st.text_input("苦手", key="input_dislike")
            first = st.date_input(
                "初回来店日",
                min_value=date(2000, 1, 1),
                max_value=date.today(),
                key="input_first_visit"
            )
            intro = st.text_input("紹介者_氏名", key="input_intro_name")
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
            "氏名": name,
            "ニックネーム": nick,
            "住所": addr,
            "電話番号": tel,
            "生年月日": date_to_str(birth),
            "勤務先・業種": work,
            "タバコ_銘柄": brand,
            "好き": like,
            "苦手": dislike,
            "初回来店日": date_to_str(first),
            "紹介者_氏名": intro,
            "メモ_顧客": memo_cus,
            "顧客_ID": cid
        }

        with st.spinner("保存中です…"):
            requests.post(GAS_POST_URL, json=payload, timeout=30)

        # --- 日付カラムを文字列に変換 ---
        for col in ["生年月日", "初回来店日"]:
            if col in customer_df.columns:
                customer_df[col] = customer_df[col].astype(str)

        # ★ ここで必ずキャッシュ破棄＋再読込
        st.cache_data.clear()         
        st.session_state.loaded_customer_id = cid
        st.success("顧客情報を保存しました")
        st.rerun()

# =====================
# 来店情報入力
# =====================
elif menu == "来店情報入力":
    st.header("来店情報入力")

    # ★ 顧客IDは必ず session_state から取得（未選択時は ""）
    cid = st.session_state.get("current_customer_id", "")    
    
    search_name = st.text_input("氏名検索（部分一致）", "")
    search_col = customer_df["氏名"].fillna("") + customer_df["ニックネーム"].fillna("")

    if search_name:
        import re
        search_words = re.split(r"\s+", search_name.strip())
        mask = pd.Series(False, index=customer_df.index)
        for w in search_words:
            if w:
                mask |= search_col.str.contains(w, case=False, na=False)
        filtered_df = customer_df[mask]
    else:
        filtered_df = customer_df

    name_labels = ["（未選択）"]
    name_map = {}

    for _, r in filtered_df.sort_values("ニックネーム").iterrows():
        label = f'{r["氏名"]}（{r["ニックネーム"]}）'
        name_labels.append(label)
        name_map[label] = r["顧客_ID"]

    selected_label = st.selectbox("氏名で選択", name_labels, key="input_selected_customer_name")

    if selected_label != "（未選択）":
        cid = name_map[selected_label]
        row = customer_df[customer_df["顧客_ID"] == cid].iloc[0].to_dict()
        st.session_state.current_customer_id = cid

        cid = row["顧客_ID"]
        st.session_state.current_customer_id = cid     

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

    # =====================
    # 来店情報（事前定義）
    # =====================  
    # ★ 顧客IDは必ず session_state から取得（未選択時は ""）
    vid = st.session_state.get("current_visit_id", "")

    if visit_mode == "既存来店履歴を編集":
        target_visits = visit_df[visit_df["顧客_ID"] == cid]

        if target_visits.empty:
            st.info("編集できる来店履歴がありません")
        else:
            visit_labels = (target_visits["来店履歴_ID"]+ "｜"+ target_visits["来店日"].astype(str))

            selected_label = st.selectbox("編集する来店履歴を選択",["（未選択）"] + visit_labels.tolist(),
                key="visit_edit_select")

            if selected_label != "（未選択）":
                selected_visit_id = selected_label.split("｜")[0]

                if st.session_state.get("selected_visit_id") != selected_visit_id:
                    st.session_state.selected_visit_id = selected_visit_id

                    visit_row = target_visits[
                        target_visits["来店履歴_ID"] == selected_visit_id
                    ].iloc[0].to_dict()

                    for key, (col, default) in VISIT_STATE_MAP.items():
                        val = visit_row.get(col, default)
                        if isinstance(default, date):
                            val = safe_date(val)
                        st.session_state[key] = val

                # ★ 初期化フラグを明示的に消す
                st.session_state.pop("visit_initialized", None)

    # --- 新規来店 初期化 ---
    init_key = f"visit_initialized_for_{cid}"

    editing = visit_mode == "既存来店履歴を編集" and st.session_state.get("selected_visit_id")

    if visit_mode == "新規来店":
        st.session_state.pop("selected_visit_id", None)  # ← ★これ追加

        if st.session_state.get(init_key) != True:
            for key in VISIT_STATE_MAP:
                st.session_state.pop(key, None)

            init_state_from_row(VISIT_STATE_MAP, {})
            st.session_state[init_key] = True
    else:
        st.session_state.pop(init_key, None)
        
    with st.form("visit_form"):
        col1, col2 = st.columns(2)

        with col1:
            visit_date = st.date_input("来店日", key="input_visit_date")
            accompany = st.text_input("同伴_氏名", key="input_accompany")
            staff = st.text_input("担当_氏名", key="input_staff")
            ext = st.number_input("延長回数", min_value=0, max_value=10, key="input_ext")
            keep = st.text_input("キープ銘柄", key="input_keep")


        with col2:
            same = st.text_input("同時来店_氏名", key="input_same")
            preget = st.text_input("プレゼント_受", key="input_preget")
            pre = st.text_input("プレゼント_渡", key="input_pre")
            event = st.text_input("イベント名", key="input_event")
            memovis = st.text_input("メモ_来店", key="input_memo_vis")

        save_visit = st.form_submit_button("来店情報を保存")
                    
    def date_to_str(d):
        if isinstance(d, date):
            return d.strftime("%Y-%m-%d")
        return ""
    
    # =====================
    # 来店情報の保存
    # =====================
    if save_visit:
        cid = st.session_state.get("current_customer_id")

        if not cid:
            st.error("顧客が選択されていません")
            st.stop()

        if visit_mode == "新規来店":
            vid = next_id(visit_df, "来店履歴_ID", "V")
        else:
            vid = st.session_state.get("selected_visit_id")
            if not vid:
                st.error("編集する来店履歴が特定できません")
                st.stop()

        payload = {
            "mode": "visit_only",
            "来店日": date_to_str(visit_date),
            "曜日": get_weekday(visit_date),
            "同伴_氏名": accompany,
            "担当_氏名": staff,
            "延長回数": ext,
            "キープ銘柄": keep,
            "同時来店_氏名": same,
            "プレゼント_受": preget,
            "プレゼント_渡": pre,
            "イベント名": event,
            "メモ_来店": memovis,
            "来店履歴_ID": vid,
            "顧客_ID": cid
        }

        with st.spinner("保存中です…"):
            requests.post(GAS_POST_URL, json=payload, timeout=30)

        # --- 日付カラムを文字列に変換 ---
        for col in ["来店日"]:
            if col in visit_df.columns:
                visit_df[col] = visit_df[col].astype(str)

        # 来店保存後
        st.session_state.after_visit_save = True
        st.cache_data.clear()

        if visit_mode == "新規来店":
            st.success("来店情報を保存しました")
        else:
            st.success("来店情報を更新しました")

        st.rerun()
     
# ==========================
# 顧客別来店履歴（氏名で選択）
# ==========================
elif menu == "顧客別来店履歴":
    st.header("顧客別来店履歴")

    # ① 検索ボックス（常に定義するのが重要）
    search_name = st.text_input("氏名検索（部分一致）",key="search_customer_name")
    search_col = customer_df["氏名"].fillna("") + customer_df["ニックネーム"].fillna("")

    # ② 検索結果で顧客を絞り込む
    if search_name:
        import re
        search_words = re.split(r"\s+", search_name.strip())
        mask = pd.Series(False, index=customer_df.index)
        for w in search_words:
            if w:
                mask |= search_col.str.contains(w, case=False, na=False)
        filtered_df = customer_df[mask]
    else:
        filtered_df = customer_df

    # ③ selectbox（必ず表示・未選択あり）
    # 来店回数を集計
    visit_count = visit_df.groupby("顧客_ID").size().to_dict()

    # 表示ラベル作成
    name_labels = ["（未選択）"]
    name_map = {}

    # 五十音順で並べる
    filtered_df = filtered_df.sort_values("ニックネーム", ascending=True)

    for _, row in filtered_df.iterrows():
        cid = row["顧客_ID"]
        name = row["氏名"]
        nickname = row["ニックネーム"]
        count = visit_count.get(cid, 0)

        label = f"{name}（{nickname}）（{count}回）"
        name_labels.append(label)
        name_map[label] = cid

    selected_label = st.selectbox("氏名で選択", name_labels,
                                key="history_selected_customer_name")

    if selected_label == "（未選択）":
        st.info("顧客を選択してください")
    else:
        cid = name_map[selected_label]

        target = visit_df[visit_df["顧客_ID"] == cid].copy()

        if target.empty:
            st.warning("来店履歴がありません")
        else:
            # 日付を datetime に
            target["来店日"] = pd.to_datetime(target["来店日"])

            # 古い順で番号
            target = target.sort_values("来店日", ascending=True)
            target["No"] = range(1, len(target) + 1)

            # 表示は新しい順
            target = target.sort_values("来店日", ascending=False)

            # 時刻を消す
            target["来店日"] = target["来店日"].dt.date

            # 顧客ID・来店履歴IDは消す
            target = target.drop(columns=["顧客_ID", "来店履歴_ID"], errors="ignore")

            # No を左に
            cols = ["No"] + [c for c in target.columns if c != "No"]
            target = target[cols]

            st.dataframe(target, hide_index=True)

# =====================
# 日付別来店一覧
# =====================
elif menu == "日付別来店一覧":
    st.header("日付別来店一覧")

    # ★① データ準備
    df = visit_df.copy()
    df["来店日"] = pd.to_datetime(df["来店日"]).dt.date

    # ★② 来店日一覧（存在する日付のみ）
    date_list = sorted(df["来店日"].dropna().unique(), reverse=True)

    if not date_list:
        st.warning("来店データがありません")
        st.stop()

    # ★③ 表示用ラベル
    date_count = df.groupby("来店日").size().to_dict()
    date_labels = ["（日付を選択）"] + [f"{d}({get_weekday(pd.to_datetime(d))})（{date_count[d]}件）"for d in date_list]

    # ★④ selectbox
    selected_label = st.selectbox("来店日を選択",date_labels,index=0,key="visit_date_select")

    if selected_label == "（日付を選択）":
        st.info("来店日を選択してください")
        st.stop()

    # ★⑤ 表示ラベル → 実日付
    selected_date = date_list[date_labels.index(selected_label) - 1]

    # ★⑥ 来店一覧抽出
    target = df[df["来店日"] == selected_date].copy()

    target["来店日"] = pd.to_datetime(target["来店日"])

    # 顧客ID → 氏名・ニックネームに変換
    target = target.merge(customer_df[["顧客_ID", "氏名","ニックネーム"]], on="顧客_ID", how="left")

    # ★氏名昇順で並べる
    target = target.sort_values("氏名", ascending=True)

    # ★その順でNoを振る
    target["No"] = range(1, len(target) + 1)

    # 来店日・曜日・顧客ID・来店履歴IDは消す
    target = target.drop(columns=["来店日", "曜日","顧客_ID", "来店履歴_ID"], errors="ignore")

    # ★No → 氏名 → その他の順に並び替え
    cols = ["No", "氏名","ニックネーム"] + [c for c in target.columns if c not in ["No", "氏名","ニックネーム"]]
    target = target[cols]

    st.dataframe(target, hide_index=True)