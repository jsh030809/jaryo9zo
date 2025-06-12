# https://github.com/UB-Mannheim/tesseract/wiki  다음 림크에서 tesseract 를 깔아야 합니다
# pip install pandas geopy PyQt5 PyQtWebEngine
# pip install pytesseract pillow
import os
import re
from PIL import Image
import pytesseract
import sys
import math
import pandas as pd
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox,
    QCheckBox, QComboBox, QDialog, QSpacerItem, QSizePolicy, QTabWidget, QTextEdit, QFileDialog, QListWidgetItem
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QTimer

pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

# ========== 유통기한 관리 ==========
simulated_now = datetime.now()
def get_now():
    return simulated_now

class FoodItem:
    def __init__(self, name, expiry_date_str):
        self.name = name
        try:
            self.expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            raise ValueError("날짜 형식이 잘못되었습니다.")
        self.added_at = get_now()
    def time_left(self):
        return self.expiry_date - get_now()
    def is_expired(self):
        return get_now() > self.expiry_date
    def __str__(self):
        if self.is_expired():
            delta = get_now() - self.expiry_date
            return f"{self.name} (유통기한: {self.expiry_date.strftime('%Y-%m-%d')}) - {delta.days}일 지남"
        else:
            delta = self.time_left()
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            return f"{self.name} (유통기한: {self.expiry_date.strftime('%Y-%m-%d')}) - {days}일 {hours}시간 남음"

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("알림 설정")
        self.settings = current_settings.copy() if current_settings else {}
        self.layout = QVBoxLayout(self)
        self.night_notify_checkbox = QCheckBox("밤에도 알림 받기 (22:00 ~ 08:00)")
        self.night_notify_checkbox.setChecked(self.settings.get("night_notify", True))
        self.layout.addWidget(self.night_notify_checkbox)
        notify_time_layout = QHBoxLayout()
        notify_time_label = QLabel("유통기한 임박 알림 시간:")
        self.notify_time_combo = QComboBox()
        self.notify_time_combo.addItems(["12시간 전", "24시간 전", "48시간 전", "72시간 전"])
        hours_map = {"12": 0, "24": 1, "48": 2, "72": 3}
        current_hours = str(self.settings.get("notify_hours_before", 24))
        self.notify_time_combo.setCurrentIndex(hours_map.get(current_hours, 1))
        notify_time_layout.addWidget(notify_time_label)
        notify_time_layout.addWidget(self.notify_time_combo)
        self.layout.addLayout(notify_time_layout)
        button_box = QHBoxLayout()
        ok_button = QPushButton("저장")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        button_box.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        button_box.addWidget(ok_button)
        button_box.addWidget(cancel_button)
        self.layout.addLayout(button_box)
    def get_settings(self):
        self.settings["night_notify"] = self.night_notify_checkbox.isChecked()
        hours = int(self.notify_time_combo.currentText().split('시간')[0])
        self.settings["notify_hours_before"] = hours
        return self.settings

# ========== 클린하우스 추천 ==========
def load_cleanhouse_list(filepath):
    df = pd.read_excel(filepath, sheet_name='클린하우스 목록')
    df = df[(df['사용여부'] == 'Y') & df['위도'].notnull() & df['경도'].notnull()]
    return df

def extract_date(data):
    tempB = []
    pat = r'\d{2,4}\W\d{2}\W\d{2}'
    temp_A = re.findall(pat, data)
    for tempf in temp_A:
        date = re.sub(r'\W', '-', tempf)
        parts = date.split('-')
        if len(parts[0]) == 2:
            parts[0] = '20' + parts[0]
        date = '-'.join(parts)
        tempB.append(date)
    result = sorted(tempB, reverse=True)
    return (result)

def use_by_date(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang='eng')
    return extract_date(text)

from geopy.geocoders import Nominatim
def geocode_address(address):
    geolocator = Nominatim(user_agent="CleanHouseFinder")
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        print(f"지오코딩 오류: {str(e)}")
    return None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_nearest_cleanhouses(user_lat, user_lng, cleanhouse_df, top_n=5):
    cleanhouse_df = cleanhouse_df.copy()
    cleanhouse_df['거리'] = cleanhouse_df.apply(
        lambda row: haversine(user_lat, user_lng, row['위도'], row['경도']), axis=1)
    return cleanhouse_df.sort_values('거리').head(top_n)

class CleanhouseFinder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("집 주소를 입력하세요")
        self.search_button = QPushButton("주변 클린하우스 찾기")
        self.search_button.clicked.connect(self.search_nearby)
        self.result_list = QListWidget()
        self.map_view = QWebEngineView()
        self.map_view.setMinimumHeight(300)
        self.map_view.hide()
        self.layout.addWidget(QLabel("🏠 집 주소로 주변 클린하우스 추천"))
        self.layout.addWidget(self.address_input)
        self.layout.addWidget(self.search_button)
        self.layout.addWidget(self.result_list)
        self.layout.addWidget(self.map_view)
        self.cleanhouse_df = load_cleanhouse_list("C:/Users/jsh03/Downloads/gonggongdeiteogwanri-keulrinhauseu-mogrog_202506111445.xlsx")
        self.result_list.itemClicked.connect(self.show_selected_map)
        self.nearest_df = None

    def search_nearby(self):
        try:
            address = self.address_input.text().strip()
            if not address:
                QMessageBox.warning(self, "오류", "주소를 입력하세요.")
                return
            user_loc = geocode_address(address)
            if not user_loc:
                QMessageBox.warning(self, "오류", "주소를 찾을 수 없습니다.")
                return
            lat, lng = user_loc
            nearest = find_nearest_cleanhouses(lat, lng, self.cleanhouse_df, top_n=5)
            self.result_list.clear()
            self.nearest_df = nearest
            for idx, row in nearest.iterrows():
                item_text = f"{row['도로명주소']} ({row['거리']:.2f}km)"
                self.result_list.addItem(item_text)
            if not nearest.empty:
                self.show_map(nearest.iloc[0]['위도'], nearest.iloc[0]['경도'], nearest.iloc[0]['도로명주소'])
        except Exception as e:
            QMessageBox.critical(self, "오류", f"검색 실패: {str(e)}")

    def show_selected_map(self, item):
        idx = self.result_list.currentRow()
        if self.nearest_df is not None and idx >= 0 and idx < len(self.nearest_df):
            row = self.nearest_df.iloc[idx]
            self.show_map(row['위도'], row['경도'], row['도로명주소'])

    def show_map(self, lat, lng, label):
        map_html = f"""
        <html>
        <body>
        <h4>{label}</h4>
        <iframe width="100%" height="300"
        src="https://maps.google.com/maps?q={lat},{lng}&z=16&output=embed"></iframe>
        </body>
        </html>
        """
        self.map_view.setHtml(map_html)
        self.map_view.show()

# ========== 식품 보관방법 탭 ==========
class FoodStorageTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setHtml("""
            <h2>  📖 식품 보관 가이드 </h2>
            <h3>냉장고 보관법</h3>
            <ul>
                <li><b>냉동실 상단</b>: 조리된 식품 보관</li>
                <li><b>냉동실 하단</b>: 생육류·어패류 보관</li>
                <li><b>냉장실 문쪽</b>: 달걀(금방 먹을 것), 잘 상하지 않는 식품</li>
                <li><b>신선실</b>: 밀폐용기에 담은 채소·과일</li>
            </ul>
            <h3>냉동 보관 주의사항</h3>
            <table border="1" cellpadding="4" cellspacing="0">
                <tr><th>식품종류</th><th>보관기간</th><th>주의사항</th></tr>
                <tr><td>생닭고기 🐔</td><td>12개월</td><td rowspan="2">분할 포장 후 보관</td></tr>
                <tr><td>생소고기 🐮</td><td>2-3개월</td></tr>
                <tr><td>해산물   🐟</td><td>1개월</td><td>손질 후 위생팩 사용</td></tr>
                <tr><td>조리육류 🍖</td><td>6-12개월</td><td>공기차단 포장</td></tr>
            </table>
            <h3>❗ 절대 냉동금지 식품</h3>
            <ul>
                <li>유제품 🥛(마요네즈, 요거트)</li>
                <li>달걀 🥚(껍질 파손 위험)</li>
                <li>수분많은 채소 🥒(상추, 오이)</li>
                <li>통조림 🥫(용기 파열 위험)</li>
            </ul>
            <p style="color:gray; font-size:0.8em;">출처: 식약처 블로그</p>
        """)
        layout.addWidget(content)

# ========== 식품 항목 위젯 ==========
class FoodListItem(QWidget):
    def __init__(self, food_item, delete_callback):
        super().__init__()
        layout = QHBoxLayout(self)
        self.label = QLabel(str(food_item))
        layout.addWidget(self.label)
        layout.addStretch()
        self.delete_btn = QPushButton("삭제")
        layout.addWidget(self.delete_btn)
        self.delete_btn.clicked.connect(lambda: delete_callback(food_item.name))
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

# ========== 전체 앱 ==========
class FridgeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("냉장고 유통기한 관리 & 클린하우스 추천 & 식품보관방법")
        self.food_list = []
        self.settings = {"night_notify": True, "notify_hours_before": 24}
        self.notified_items = set()
        self.init_ui()
        self.check_and_show_alerts()

    def init_ui(self):
        self.tabs = QTabWidget()
        # 유통기한 관리 탭
        self.fridge_tab = QWidget()
        self.fridge_layout = QVBoxLayout(self.fridge_tab)
        self.input_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("식품 이름")
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("유통기한 (YYYY-MM-DD)")
        self.add_button = QPushButton("추가")
        self.add_button.clicked.connect(self.add_food)
        self.ocr_button = QPushButton("📷 이미지로 날짜 인식")
        self.ocr_button.clicked.connect(self.load_date_from_image)
        self.input_layout.addWidget(self.ocr_button)
        self.setting_button = QPushButton("⚙️ 설정")
        self.setting_button.clicked.connect(self.open_settings)
        self.input_layout.addWidget(self.name_input)
        self.input_layout.addWidget(self.date_input)
        self.input_layout.addWidget(self.add_button)
        self.input_layout.addWidget(self.setting_button)
        self.fridge_layout.addLayout(self.input_layout)
        self.time_label = QLabel()
        self.update_time_label()
        self.fridge_layout.addWidget(self.time_label)
        self.valid_list_widget = QListWidget()
        self.expired_list_widget = QListWidget()
        self.fridge_layout.addWidget(QLabel("✅ 유효한 식품 목록"))
        self.fridge_layout.addWidget(self.valid_list_widget)
        self.fridge_layout.addWidget(QLabel("⚠️ 유통기한 지난 식품"))
        self.fridge_layout.addWidget(self.expired_list_widget)
        self.tabs.addTab(self.fridge_tab, "유통기한 관리")
        # 식품 보관방법 탭
        self.storage_tab = FoodStorageTab()
        self.tabs.addTab(self.storage_tab, "식품 보관방법")
        # 클린하우스 추천 탭
        self.cleanhouse_tab = CleanhouseFinder()
        self.tabs.addTab(self.cleanhouse_tab, "주변 클린하우스")
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def update_time_label(self):
        self.time_label.setText(get_now().strftime("%Y-%m-%d %H:%M"))

    def add_food(self):
        name = self.name_input.text().strip()
        date_str = self.date_input.text().strip()
        if not name:
            QMessageBox.warning(self, "오류", "식품 이름을 입력해주세요.")
            return
        if any(item.name == name for item in self.food_list):
            QMessageBox.warning(self, "중복 항목", f"'{name}'은(는) 이미 목록에 있습니다.")
            return
        try:
            item = FoodItem(name, date_str)
        except ValueError:
            QMessageBox.warning(self, "오류", "날짜 형식이 잘못되었습니다. YYYY-MM-DD로 입력해주세요.")
            return
        self.food_list.append(item)
        self.update_lists()
        self.name_input.clear()
        self.date_input.clear()
        self.check_and_show_alerts(check_item=item)

    def update_lists(self):
        self.valid_list_widget.clear()
        self.expired_list_widget.clear()
        self.update_time_label()
        self.food_list.sort(key=lambda x: x.expiry_date)
        items_to_unnotify = set()
        for item_name in self.notified_items:
            found_item = next((item for item in self.food_list if item.name == item_name), None)
            if found_item and not found_item.is_expired() and found_item.time_left().total_seconds() / 3600 > self.settings["notify_hours_before"]:
                items_to_unnotify.add(item_name)
        self.notified_items -= items_to_unnotify

        # 각 식품 항목에 삭제 버튼이 있는 위젯을 추가
        for item in self.food_list:
            widget = FoodListItem(item, self.delete_food_by_name)
            list_item = QListWidgetItem()
            list_item.setSizeHint(widget.sizeHint())
            if item.is_expired():
                self.expired_list_widget.addItem(list_item)
                self.expired_list_widget.setItemWidget(list_item, widget)
            else:
                self.valid_list_widget.addItem(list_item)
                self.valid_list_widget.setItemWidget(list_item, widget)

    def delete_food_by_name(self, name):
        self.food_list = [item for item in self.food_list if item.name != name]
        self.update_lists()

    def open_settings(self):
        dialog = SettingsDialog(self, current_settings=self.settings)
        if dialog.exec_():
            self.settings = dialog.get_settings()
            QMessageBox.information(self, "설정 완료", "설정이 저장되었습니다.")
            self.update_lists()
            self.check_and_show_alerts()

    def check_and_show_alerts(self, check_item=None):
        now = get_now()
        if not self.settings["night_notify"] and (now.hour >= 22 or now.hour < 8):
            return
        expired_alerts = []
        imminent_alerts = []
        items_to_check = [check_item] if check_item else self.food_list
        for item in items_to_check:
            if item.name in self.notified_items:
                continue
            hours_left = item.time_left().total_seconds() / 3600
            if item.is_expired():
                expired_alerts.append(item.name)
                self.notified_items.add(item.name)
            elif 0 <= hours_left <= self.settings["notify_hours_before"]:
                imminent_alerts.append(f"{item.name} ({int(hours_left)}시간 남음)")
                self.notified_items.add(item.name)
        messages = []
        if expired_alerts:
            messages.append("--- 유통기한 만료 ---\n" + "\n".join(expired_alerts))
        if imminent_alerts:
            messages.append("--- 유통기한 임박 ---\n" + "\n".join(imminent_alerts))
        if messages:
            full_message = "\n\n".join(messages)
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "식품 알림", full_message))

    def load_date_from_image(self):
        fname, _ = QFileDialog.getOpenFileName(self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg)")
        if fname:
            try:
                dates = use_by_date(fname)
                if not dates:
                    QMessageBox.information(self, "인식 실패", "유통기한 형식의 날짜를 찾을 수 없습니다.")
                    return
                self.date_input.setText(dates[0])
                QMessageBox.information(self, "날짜 인식 성공", f"인식된 유통기한: {dates[0]}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"OCR 실패: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = FridgeApp()
    window.show()
    sys.exit(app.exec_())
