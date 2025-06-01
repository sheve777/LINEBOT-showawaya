# app.py (フルバージョン - .env対応、日本語コメント付き)

from flask import Flask, render_template, request, flash, redirect, url_for, session
import datetime
import os # 「オペレーティングシステム」とやり取りするための基本的な機能を提供します (環境変数を読むのに使います)
import json
import holidays

# Google Calendar API関連のインポート
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# python-dotenvライブラリから load_dotenv という機能を読み込みます
from dotenv import load_dotenv

# load_dotenv() を呼び出すことで、同じフォルダにある .env ファイルを探し、
# その中に書かれている「変数名=値」の情報を「環境変数」としてプログラムが使えるように読み込みます。
# Flaskアプリの本体 (app = Flask(...)) を作るよりも前に実行するのが一般的です。
load_dotenv()

app = Flask(__name__)

# --- 設定値を .env ファイルから読み込む ---
# os.getenv('環境変数名') で、指定した名前の環境変数の値を取得します。
CALENDAR_ID = os.getenv('CALENDAR_ID')
# Googleカレンダーのどのカレンダーを使うかを指定するIDです。

SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
# Googleサービスアカウントの秘密鍵ファイル（JSON形式）の名前（またはパス）です。

# os.getenv() で取得できる値は「文字列」なので、数値として使いたい場合は int() で変換します。
# もし .env に変数がなかった場合のデフォルト値も指定できます (例: '11')。
TOTAL_COUNTER_SEATS = int(os.getenv('TOTAL_COUNTER_SEATS', '11')) # カウンターの総席数
TOTAL_TABLE_UNITS = int(os.getenv('TOTAL_TABLE_UNITS', '2'))   # テーブルの総卓数

# Flaskのデバッグモードを .env ファイルで制御します。
FLASK_DEBUG_MODE = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# ↓↓↓ SECRET_KEY の読み込みを追加 ↓↓↓
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

# ↓↓↓ 新しいお店情報を .env から読み込み ↓↓↓
SHOP_PHONE_NUMBER = os.getenv('SHOP_PHONE_NUMBER', "お店の電話番号までお問い合わせください")
SHOP_OPENING_HOURS = os.getenv('SHOP_OPENING_HOURS', "お問い合わせください") # デフォルト値
SHOP_HOLIDAYS = os.getenv('SHOP_HOLIDAYS', "お問い合わせください")         # デフォルト値

# --------------------------------------
# ↓↓↓ FlaskアプリにSECRET_KEYを設定する処理を追加 ↓↓↓
if not FLASK_SECRET_KEY:
    print("警告: FLASK_SECRET_KEYが.envファイルに設定されていません。")
    print("開発中は自動生成された一時的なキーを使用しますが、本番環境では必ず固有のキーを設定してください。")
    app.secret_key = os.urandom(24) # .envに設定がない場合の一時的なキー (非推奨)
else:
    app.secret_key = FLASK_SECRET_KEY
    print("FLASK_SECRET_KEY を .env ファイルから読み込みました。")
# --------------------------------------

# --- Google Calendar API スコープ ---
SCOPES = ['https://www.googleapis.com/auth/calendar'] # カレンダーの読み書き両方の権限
service = None # Google Calendar APIと通信するためのオブジェクトを格納するグローバル変数

def authenticate_with_service_account():
    """サービスアカウントを使ってGoogle Calendar APIの認証を行い、サービスオブジェクトを設定する"""
    global service # この関数内でグローバル変数 service の値を変更することを宣言

    if not SERVICE_ACCOUNT_FILE:
        print("◆◆◆ エラー: .envファイルに SERVICE_ACCOUNT_FILE が設定されていません。 ◆◆◆")
        return
    if not CALENDAR_ID: # CALENDAR_IDも認証に直接は使わないが、後の処理で必須なのでチェック
        print("◆◆◆ エラー: .envファイルに CALENDAR_ID が設定されていません。 ◆◆◆")
        return

    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        print("★★★ Google Calendar API サービスアカウントでの認証成功 ★★★")
    except FileNotFoundError:
        print(f"◆◆◆ エラー: サービスアカウントキーファイル '{SERVICE_ACCOUNT_FILE}' が見つかりません。◆◆◆")
        print(f"   .envファイルの設定と、ファイルの配置場所を確認してください。")
        service = None
    except Exception as e:
        print(f"◆◆◆ サービスアカウントでの認証中に予期せぬエラーが発生しました: {e} ◆◆◆")
        service = None

# Flaskアプリが起動する際に、一度だけGoogleカレンダーの認証処理を実行します。
authenticate_with_service_account()


def calculate_vacancy(target_datetime_start_jp, target_datetime_end_jp, calendar_service):
    """
    指定された日時の既存予約から、カウンターとテーブルの空き状況を計算する関数。
    """
    global CALENDAR_ID, TOTAL_COUNTER_SEATS, TOTAL_TABLE_UNITS # .envから読み込んだグローバル変数を使用

    print(f"\n--- 空き状況計算開始 ({target_datetime_start_jp.strftime('%Y-%m-%d %H:%M')} JST) ---")

    time_offset = datetime.timedelta(hours=9)
    start_time_utc = target_datetime_start_jp - time_offset
    end_time_utc = target_datetime_end_jp - time_offset
    time_min_utc_iso = start_time_utc.isoformat() + 'Z'
    time_max_utc_iso = end_time_utc.isoformat() + 'Z'

    print(f"検索期間 (UTC): {time_min_utc_iso} から {time_max_utc_iso}")

    if calendar_service is None: # 認証失敗などで service が None の場合の対策
        print("◆◆◆ calculate_vacancyエラー: Calendar APIサービスが利用できません。 ◆◆◆")
        return -1, -1

    try:
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID, # .env から読み込んだカレンダーIDを使用
            timeMin=time_min_utc_iso,
            timeMax=time_max_utc_iso,
            singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])
    except HttpError as error:
        print(f'カレンダーからの予定取得中にエラー: {error}')
        return -1, -1 # エラー時は空きなしとして扱う (例)

    current_used_counter_seats = 0
    current_used_table_units = 0

    if not events:
        print("指定期間に既存の予約はありませんでした。")
    else:
        print(f"{len(events)}件の既存予約が見つかりました。詳細を確認します...")
        for event in events:
            description_str = event.get('description', '{}')
            # print(f"  デバッグ用出力: 取得した説明欄 -> [{description_str}]") # 必要に応じてコメント解除
            try:
                reservation_details = json.loads(description_str)
                if reservation_details: # JSONが空でないことを確認
                    seat_type = reservation_details.get('seat_type')
                    if seat_type == 'カウンター':
                        seats_this_booking = reservation_details.get('seats_used', 0)
                        current_used_counter_seats += seats_this_booking
                        print(f"  カウンター予約発見: {seats_this_booking}席使用")
                    elif seat_type == 'テーブル':
                        tables_this_booking = reservation_details.get('tables_used', 0)
                        current_used_table_units += tables_this_booking
                        print(f"  テーブル予約発見: {tables_this_booking}卓使用")
            except json.JSONDecodeError:
                print(f"  注意: 予定「{event.get('summary', '(タイトルなし)')}」の説明欄はJSON形式ではありませんでした。")
            except TypeError:
                print(f"  注意: 予定「{event.get('summary', '(タイトルなし)')}」の説明欄の形式に問題がありました。")

    print(f"集計結果: 現在使用中のカウンター {current_used_counter_seats}席, テーブル {current_used_table_units}卓")

    available_counter_seats = TOTAL_COUNTER_SEATS - current_used_counter_seats
    available_table_units = TOTAL_TABLE_UNITS - current_used_table_units

    print(f"計算結果: 空きカウンター {available_counter_seats}席, 空きテーブル {available_table_units}卓")
    print("--- 空き状況計算終了 ---")

    return available_counter_seats, available_table_units


@app.route('/')
def index():
    # --- ▼▼▼ 定休日と祝日の情報をJavaScriptに渡すための準備 ▼▼▼ ---
    disabled_js_weekdays = []  # 毎週無効にする曜日 (JSのgetDay()用: 日曜=0, 月曜=1...)
    specific_dates_to_disable = [] # 特定の日付を無効にするリスト ("YYYY-MM-DD"形式)
    date_ranges_to_disable = []    # 特定の期間を無効にするリスト ({from:"YYYY-MM-DD", to:"..."})

    today = datetime.date.today()
    min_date_for_flatpickr = (today + datetime.timedelta(days=1)).isoformat()
    
    # 日本の祝日を取得 (当年と翌年分)
    jp_holidays = holidays.JP(years=[today.year, today.year + 1]) # holidays.Japanでも可

    if SHOP_HOLIDAYS:
        # 1. 毎週の定休日 (「祝日の月曜日」と区別するため、少しロジック調整)
        disable_all_mondays = "毎週月曜日" in SHOP_HOLIDAYS # 「毎週月曜日」が指定されているか
        
        if "毎週日曜日" in SHOP_HOLIDAYS: disabled_js_weekdays.append(0)
        if disable_all_mondays: disabled_js_weekdays.append(1) # 「毎週月曜日」なら全ての月曜を無効化
        if "毎週火曜日" in SHOP_HOLIDAYS: disabled_js_weekdays.append(2)
        if "毎週水曜日" in SHOP_HOLIDAYS: disabled_js_weekdays.append(3)
        if "毎週木曜日" in SHOP_HOLIDAYS: disabled_js_weekdays.append(4)
        if "毎週金曜日" in SHOP_HOLIDAYS: disabled_js_weekdays.append(5)
        if "毎週土曜日" in SHOP_HOLIDAYS: disabled_js_weekdays.append(6)

        # 2. 年末年始の期間 (前回と同じロジック)
        if "年末年始" in SHOP_HOLIDAYS:
            nenmatsu_start_mmdd_str = os.getenv('NENMATSU_HOLIDAY_START_MONTH_DAY', "12-29")
            nenshi_end_mmdd_str = os.getenv('NENSHI_HOLIDAY_END_MONTH_DAY', "01-03")
            nenmatsu_m, nenmatsu_d = map(int, nenmatsu_start_mmdd_str.split('-'))
            nenshi_m, nenshi_d = map(int, nenshi_end_mmdd_str.split('-'))
            
            date_ranges_to_disable.append({"from": f"{today.year}-{nenmatsu_m:02d}-{nenmatsu_d:02d}", "to": f"{today.year}-12-31"})
            date_ranges_to_disable.append({"from": f"{today.year+1}-01-01", "to": f"{today.year+1}-{nenshi_m:02d}-{nenshi_d:02d}"})

        # 3. 日本の祝日全体を無効にするかチェック
        if "祝日" in SHOP_HOLIDAYS and "祝日の月曜日" not in SHOP_HOLIDAYS: # 「祝日」指定があり、「祝日の月曜日」指定ではない場合
            for date_obj, name in sorted(jp_holidays.items()):
                if date_obj > today: # 未来の祝日のみ対象
                    specific_dates_to_disable.append(date_obj.isoformat())
                    print(f"DEBUG: 祝日として無効化 -> {date_obj.isoformat()} ({name})")

        # 4. 「祝日の月曜日」だけを無効にするかチェック
        #    （「毎週月曜日」が指定されていなければ、こちらを優先）
        if "祝日の月曜日" in SHOP_HOLIDAYS and not disable_all_mondays:
            for date_obj, name in sorted(jp_holidays.items()):
                if date_obj > today and date_obj.weekday() == 0: # Pythonのweekday()で月曜日は0
                    specific_dates_to_disable.append(date_obj.isoformat())
                    print(f"DEBUG: 祝日の月曜日として無効化 -> {date_obj.isoformat()} ({name})")
    
    # 重複する日付を削除（祝日が定休日曜日と重なる場合など）
    specific_dates_to_disable = sorted(list(set(specific_dates_to_disable)))

    # --- ▲▲▲ ここまで準備 ▲▲▲ ---

    # 'reservation_form.html' を表示する
    return render_template(
        'reservation_form.html',
        shop_hours=SHOP_OPENING_HOURS,  # SHOP_OPENING_HOURS 変数を 'shop_hours' として渡す
        shop_holidays=SHOP_HOLIDAYS,   # SHOP_HOLIDAYS 変数を 'shop_holidays' として渡す
        shop_phone=SHOP_PHONE_NUMBER, # SHOP_PHONE_NUMBER を 'shop_phone' として渡す
        min_date_for_calendar=min_date_for_flatpickr, # ★変更★ Flatpickr用のminDate
        disabled_weekdays_json=json.dumps(disabled_js_weekdays), # ★追加★ 無効にする曜日のリストをJSON文字列で渡す
        nenmatsu_nenshi_json=json.dumps(date_ranges_to_disable), # 年末年始期間を渡す (名前は前回と同じ)
        specific_holidays_json=json.dumps(specific_dates_to_disable) # ★追加★ 特定の祝日リストをJSONで渡す
    )

@app.route('/reservation_result')
def reservation_result():
    # このページはフラッシュメッセージを表示するだけ
    return render_template('result_page.html')

@app.route('/submit_reservation', methods=['POST'])
def submit_reservation():
    global service, CALENDAR_ID
    message_type = "error" # ★追加★ まずはデフォルトをエラータイプに設定

    if service is None:
        final_message_to_customer = "申し訳ありません。現在、予約システムをご利用いただけません。\nお手数ですが、お電話にてお問い合わせください。"
        # ★修正★ message_type を渡す
        flash(final_message_to_customer, message_type) # ★変更1: メッセージをflashに設定
        return redirect(url_for('reservation_result'))  # ★変更2: 結果ページへリダイレクト

    date_str = request.form.get('reservation_date')
    time_str = request.form.get('reservation_time')
    num_guests_str = request.form.get('num_guests')
    requested_seat_type = request.form.get('seat_type')
    reservist_name = request.form.get('reservist_name', '').strip()
    phone_number = request.form.get('phone_number', '').strip()

    try:
        requested_guests = int(num_guests_str)
        if not (1 <= requested_guests <= 8) :
             raise ValueError("人数は1～8名で選択してください。")

        year, month, day = map(int, date_str.split('-'))
        hour, minute = map(int, time_str.split(':'))

        selected_date_obj = datetime.date(year, month, day) # お客様が選択した日付オブジェクト
        today_date_obj = datetime.date.today()              # 今日の日付オブジェクト

        if selected_date_obj <= today_date_obj: # 選択された日付が今日以前かチェック
            final_message_to_customer = "ご予約は明日以降の日付で承っております。\n恐れ入りますが、日付をご確認の上、再度ご入力ください。"
            # message_type は "error" のまま
            flash(final_message_to_customer, message_type) # ★変更★
            return redirect(url_for('reservation_result')) # ★変更★
        
               # --- ▼▼▼ 定休日チェック（拡張版）▼▼▼ ---
        is_holiday = False # このフラグが True なら定休日
        holiday_reason_message = "" # 定休日の理由メッセージ

        selected_month = selected_date_obj.month # 選択された月
        selected_day = selected_date_obj.day     # 選択された日
        selected_weekday_int = selected_date_obj.weekday() # 曜日番号を selected_weekday_int に入れる
        japanese_weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        selected_weekday_jp = japanese_weekdays[selected_weekday_int] # 正しく selected_weekday_int を使う


        # 1. 毎週の定休日チェック (例: 日曜日)
        if SHOP_HOLIDAYS and "日曜日" in SHOP_HOLIDAYS:
            if selected_weekday_int == 6: # 6 は日曜日
                is_holiday = True
                holiday_reason_message = f"毎週{selected_weekday_jp}のため" # %A は曜日名 (例: Sunday)
                                                                              # 日本語で「日曜日」と表示したい場合は調整が必要
        
        # (もし「毎週水曜日」も定休日なら、以下のように追加できます)
        # if not is_holiday and SHOP_HOLIDAYS and "水曜日" in SHOP_HOLIDAYS: # まだ休日と判定されていなければ
        #     if selected_weekday_int == 2: # 2 は水曜日
        #         is_holiday = True
        #         holiday_reason_message = f"毎週{selected_weekday_jp}のため"

        # 2. 年末年始のチェック (例: 12月29日～1月3日)
        #    SHOP_HOLIDAYS に "年末年始" というキーワードが含まれていれば、このチェックを行う
        if not is_holiday and SHOP_HOLIDAYS and "年末年始" in SHOP_HOLIDAYS: # まだ休日と判定されていなければ
            # 年末の期間 (12月29日, 30日, 31日)
            if selected_month == 12 and selected_day >= 29:
                is_holiday = True
            # 年始の期間 (1月1日, 2日, 3日)
            elif selected_month == 1 and selected_day <= 3:
                is_holiday = True
            
            if is_holiday: # もし上の年末年始の条件に合致したら
                holiday_reason_message = "年末年始の休業期間のため"

        # (ここに、将来的に「祝日」や「特定の休みの日」のチェックも追加できます)

        # 最終的に is_holiday が True なら、予約不可とする
        if is_holiday:
            final_message_to_customer = (
                f"申し訳ございません。{selected_date_obj.strftime('%Y年%m月%d日')}（{selected_weekday_jp}）は、{holiday_reason_message}定休日でございます。\n"
                f"恐れ入りますが、別の日付をご選択ください。"
            )
            flash(final_message_to_customer, message_type) # message_type は既に "error"
            return redirect(url_for('reservation_result'))
        # --- ▲▲▲ ここまで定休日チェック（拡張版） ▲▲▲ ---
        
        reservation_start_time_jp = datetime.datetime(year, month, day, hour, minute)
        reservation_end_time_jp = reservation_start_time_jp + datetime.timedelta(hours=2)

        if not reservist_name:
            final_message_to_customer = "お名前が入力されていません。恐れ入りますが、お名前をご入力ください。"
            # ★修正★ message_type を渡す
            flash(final_message_to_customer, message_type) # ★変更★
            return redirect(url_for('reservation_result')) # ★変更★

        if requested_guests >= 4 and not phone_number:
            final_message_to_customer = "4名様以上でご予約の場合は、お電話番号のご入力をお願いいたします。"
            # ★修正★ message_type を渡す
            flash(final_message_to_customer, message_type) # ★変更★
            return redirect(url_for('reservation_result')) # ★変更★

    except (ValueError, TypeError) as e:
        print(f"入力データのエラー: {e}")
        final_message_to_customer = f"入力された人数、日付、または時刻の形式に誤りがあります。もう一度ご確認ください。" # ({e}) を削除
        # ★修正★ message_type を渡す
        flash(final_message_to_customer, message_type) # ★変更★
        return redirect(url_for('reservation_result')) # ★変更★
    except Exception as e: # ★追加★ その他の予期せぬエラーもキャッチ
        print(f"予期せぬ入力処理エラー: {e}")
        final_message_to_customer = "入力処理中に予期せぬエラーが発生しました。お手数ですが、入力内容を再度ご確認ください。"
        flash(final_message_to_customer, message_type) # ★変更★
        return redirect(url_for('reservation_result')) # ★変更★


    print(f"処理中のリクエスト: {reservist_name}様, {requested_guests}名様、{requested_seat_type}希望")
    print(f"希望日時: {reservation_start_time_jp.strftime('%Y-%m-%d %H:%M')} - {reservation_end_time_jp.strftime('%Y-%m-%d %H:%M')} JST")
    if phone_number:
        print(f"電話番号: {phone_number}")

    available_counters, available_tables = calculate_vacancy(
        reservation_start_time_jp,
        reservation_end_time_jp,
        service
    )

    if available_counters == -1: # calculate_vacancy でエラーが発生した場合
        final_message_to_customer = "申し訳ありません。ただいま空席状況を確認できませんでした。\nお手数ですが、しばらくしてから再度お試しいただくか、お電話にてお問い合わせください。"
        # ★修正★ message_type を渡す (デフォルトの "error" のまま)
        flash(final_message_to_customer, message_type) # ★変更★
        return redirect(url_for('reservation_result')) # ★変更★

    print(f"\n--- 予約可否判断開始 ---")
    print(f"現在の空き: カウンター {available_counters}席, テーブル {available_tables}卓")
    reservation_possible = False
    final_message_to_customer = "" # メッセージは各条件分岐で設定
    # message_type は、予約不可の場合はデフォルトの "error" が使われる

    # --- 予約可否判断ロジック (メッセージ内容を調整) ---
    if requested_seat_type == "カウンター":
        if 1 <= requested_guests <= 4:
            if available_counters >= requested_guests:
                if (available_counters - requested_guests) >= 5:
                    reservation_possible = True
                    final_message_to_customer = f"{reservist_name}様、カウンター席 {requested_guests}名様でのご予約を承りました。"
                    message_type = "success" # ★追加★ 予約成功なので type を success に
                else:
                    final_message_to_customer = f"{reservist_name}様、申し訳ございません。ご希望のお時間帯は、カウンター席が満席でございます。恐れ入りますがお電話にてお問い合わせをお願いいたします。"
            else:
                final_message_to_customer = f"{reservist_name}様、申し訳ございません。ご希望のお時間帯は、カウンター席がご希望の人数様分ご用意できません。"
        else:
            final_message_to_customer = f"{reservist_name}様、申し訳ありません。カウンター席は1～4名様でのご案内でございます。"
    elif requested_seat_type == "テーブル":
        if 1 <= requested_guests <= 2:
            final_message_to_customer = f"{reservist_name}様、申し訳ありません。テーブル席は3名様からのご案内でございます。"
        elif 3 <= requested_guests <= 4:
            if available_tables >= 1:
                reservation_possible = True
                final_message_to_customer = f"{reservist_name}様、テーブル席 {requested_guests}名様でのご予約を承りました。"
                message_type = "success" # ★追加★ 予約成功なので type を success に
            else:
                final_message_to_customer = f"{reservist_name}様、申し訳ございません。ご希望のお時間帯は、テーブル席が満席でございます。"
        elif 5 <= requested_guests <= 8:
            if available_tables >= 2:
                reservation_possible = True
                final_message_to_customer = f"{reservist_name}様、テーブル席 {requested_guests}名様でのご予約を承りました。"
                message_type = "success" # ★追加★ 予約成功なので type を success に
            else:
                final_message_to_customer = f"{reservist_name}様、申し訳ございません。ご希望のお時間帯は、テーブル席が満席でございます。"
        else:
            final_message_to_customer = f"{reservist_name}様、申し訳ありません。テーブル席では8名様を超えるご予約はお受けできません。9名様以上はお電話にてご相談ください。"
    else:
        final_message_to_customer = f"{reservist_name}様、ご希望の席タイプを正しくお選びください。"
    # --- ここまで予約可否判断ロジック ---

    if reservation_possible: # この時点で final_message_to_customer と message_type は設定済みのはず
        # ... (カレンダー書き込み処理は変更なし、ただしエラー時の message_type 変更は重要) ...
        event_summary = f"予約: {reservist_name}様 {requested_guests}名 ({requested_seat_type})"
        if phone_number:
            event_summary += f" ({phone_number})"
        # (以下、event_description_details, event_body の作成は変更なし)
        event_description_details = {
            "reservist_name": reservist_name, "number_of_guests": requested_guests,
            "seat_type": requested_seat_type,
        }
        if phone_number: event_description_details["phone_number"] = phone_number
        if requested_seat_type == "カウンター": event_description_details["seats_used"] = requested_guests
        elif requested_seat_type == "テーブル": event_description_details["tables_used"] = 1 if requested_guests <= 4 else 2
        event_description_json = json.dumps(event_description_details, ensure_ascii=False, indent=2)
        event_start = {'dateTime': reservation_start_time_jp.isoformat(), 'timeZone': 'Asia/Tokyo'}
        event_end = {'dateTime': reservation_end_time_jp.isoformat(), 'timeZone': 'Asia/Tokyo'}
        event_body = {'summary': event_summary, 'description': event_description_json, 'start': event_start, 'end': event_end}

        try:
            created_event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
            print(f"カレンダー登録成功: {created_event.get('id')}, Link: {created_event.get('htmlLink')}")
            # final_message_to_customer には既に予約承りメッセージが入っているので、追記する
            final_message_to_customer += (
                f"\n\n上記の内容でご予約を受付させていただきました。\n"
                f"{reservist_name}様のご来店を心よりお待ちしております。"
            )
            # message_type は "success" のまま
        except HttpError as error:
            print(f"カレンダー書き込みエラー: {error}")
            final_message_to_customer = (
                f"{reservist_name}様、申し訳ございません。\n"
                f"ただいまご予約のお手続き中にシステムで一時的な問題が発生いたしました。\n"
                f"お席の確保状況を確認いたしますので、大変お手数をおかけしますが、"
                f"お店からの確認のご連絡をお待ちいただくか、お急ぎの場合はお電話（お店の電話番号をここに記載）にてお問い合わせいただけますでしょうか。"
            )
            message_type = "error" # ★重要★ カレンダー登録失敗時はエラー扱いに
    
    print(f"DEBUG: 最終メッセージタイプ -> [{message_type}]") # ★追加★ デバッグ用
    print("--- 予約可否判断終了 ---")
    # ★修正★ message_type を渡す
    flash(final_message_to_customer, message_type)
    return redirect(url_for('reservation_result'))

    # 4. 予約可否判断ロジック
    print(f"\n--- 予約可否判断開始 ---")
    print(f"現在の空き: カウンター {available_counters}席, テーブル {available_tables}卓")
    reservation_possible = False
    final_message_to_customer = ""
    
    if requested_seat_type == "カウンター":
        if 1 <= requested_guests <= 4:
            if available_counters >= requested_guests:
                if (available_counters - requested_guests) >= 5:
                    reservation_possible = True
                    final_message_to_customer = f"{reservist_name}様、カウンター席 {requested_guests}名様でのご予約を承りました。"
                else:
                    final_message_to_customer = f"{reservist_name}様、申し訳ございません。ご希望のお時間帯は、カウンター席の空きが残り少なくなっております。別のお時間をご検討いただくか、お電話にてご相談ください。"
            else:
                final_message_to_customer = f"{reservist_name}様、申し訳ございません。ご希望のお時間帯は、カウンター席がご希望の人数様分ご用意できません。)"
        else:
            final_message_to_customer = f"{reservist_name}様、申し訳ありません。カウンター席は1～4名様でのご案内となります。"
    elif requested_seat_type == "テーブル":
        if 1 <= requested_guests <= 2:
            final_message_to_customer = f"{reservist_name}様、申し訳ありません。テーブル席は3名様からのご案内となります。"
        elif 3 <= requested_guests <= 4:
            if available_tables >= 1:
                reservation_possible = True
                final_message_to_customer = f"{reservist_name}様、テーブル席 {requested_guests}名様でのご予約を承りました。"
            else:
                final_message_to_customer = f"{reservist_name}様、申し訳ございません。ご希望のお時間帯は、カウンター席の空きが残り少なくなっております。別のお時間をご検討いただくか、お電話にてご相談ください。"
        elif 5 <= requested_guests <= 8:
            if available_tables >= 2:
                reservation_possible = True
                final_message_to_customer = f"{reservist_name}様、テーブル席 {requested_guests}名様でのご予約を承りました。"
            else:
                final_message_to_customer = f"{reservist_name}様、申し訳ございません。テーブル席は満席でございます。"
        else:
            final_message_to_customer = f"{reservist_name}様、申し訳ありません。テーブル席では8名様を超えるご予約はお受けできません。9名様以上はお電話にてご相談ください。"
    else:
        final_message_to_customer = f"{reservist_name}様、ご希望の席タイプを正しくお選びください。"

    # 5. 予約可能ならカレンダーに書き込み
    if reservation_possible:
        event_summary = f"予約: {reservist_name}様 {requested_guests}名 ({requested_seat_type})"
        if phone_number:
            event_summary += f" ({phone_number})"
            
        event_description_details = {
            "reservist_name": reservist_name,
            "number_of_guests": requested_guests,
            "seat_type": requested_seat_type,
        }
        if phone_number:
            event_description_details["phone_number"] = phone_number
        
        if requested_seat_type == "カウンター":
            event_description_details["seats_used"] = requested_guests
        elif requested_seat_type == "テーブル":
            event_description_details["tables_used"] = 1 if requested_guests <= 4 else 2
        
        event_description_json = json.dumps(event_description_details, ensure_ascii=False, indent=2)

        event_start = {'dateTime': reservation_start_time_jp.isoformat(), 'timeZone': 'Asia/Tokyo'}
        event_end = {'dateTime': reservation_end_time_jp.isoformat(), 'timeZone': 'Asia/Tokyo'}
        event_body = {
            'summary': event_summary,
            'description': event_description_json,
            'start': event_start,
            'end': event_end,
        }
        try:
            created_event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
            print(f"カレンダー登録成功: {created_event.get('id')}, Link: {created_event.get('htmlLink')}") # 開発者ログ
            final_message_to_customer = f"{reservist_name}様、ご予約ありがとうございます。\n"
            final_message_to_customer += f"{reservation_start_time_jp.strftime('%Y年%m月%d日 %H:%M')}より、{requested_guests}名様、{requested_seat_type}席にてご予約を承りました。"
        except HttpError as error:
            print(f"カレンダー書き込みエラー: {error}") # 開発者ログ
            final_message_to_customer = f"{reservist_name}様、ご予約のお席は確保できましたが、システムエラーによりカレンダーへの登録に失敗しました。お手数ですがお電話にてご確認ください。"
            # reservation_possible はTrueのままなので、メッセージタイプはsuccessのままでも良いが、注意を促す
            message_type = "error" # または "warning" のような別のタイプを定義しても良い
    
    
    print("--- 予約可否判断終了 ---")
    return render_template('reservation_form.html', message=final_message_to_customer)


if __name__ == '__main__':
    # Flaskの開発用サーバーを起動します。
    # host='0.0.0.0' は、同じネットワーク内の他の端末からもアクセスできるようにする設定です。
    # debug=FLASK_DEBUG_MODE で、.env ファイルから読み込んだ設定値を使ってデバッグモードを制御します。
    app.run(host='0.0.0.0', debug=FLASK_DEBUG_MODE)