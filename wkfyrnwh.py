import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox,
    QCheckBox, QComboBox, QDialog, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import QTimer # QTimer를 사용하기 위해 임포트
from datetime import datetime, timedelta

# 시뮬레이션 시간
simulated_now = datetime.now()

def get_now():
    """현재 시뮬레이션 시간을 반환합니다."""
    return simulated_now

class FoodItem:
    """식품 항목을 나타내는 클래스입니다."""
    def __init__(self, name, expiry_date_str):
        self.name = name
        try:
            # 유통기한은 해당 날짜의 23:59:59로 설정
            self.expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            raise ValueError("날짜 형식이 잘못되었습니다.")
        self.added_at = get_now()

    def time_left(self):
        """유통기한까지 남은 시간을 계산합니다."""
        return self.expiry_date - get_now()

    def is_expired(self):
        """식품이 유통기한을 지났는지 확인합니다."""
        return get_now() > self.expiry_date

    def __str__(self):
        """식품 항목을 문자열로 표현합니다."""
        if self.is_expired():
            # 만료된 시간을 표시 (예: 1일 지남)
            delta = get_now() - self.expiry_date
            return f"{self.name} (유통기한: {self.expiry_date.strftime('%Y-%m-%d')}) - {delta.days}일 지남"
        else:
            delta = self.time_left()
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            return f"{self.name} (유통기한: {self.expiry_date.strftime('%Y-%m-%d')}) - {days}일 {hours}시간 남음"

class SettingsDialog(QDialog):
    """설정 변경을 위한 대화 상자 클래스입니다."""
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

class FridgeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("냉장고 유통기한 관리")
        self.food_list = []
        self.settings = {
            "night_notify": True,
            "notify_hours_before": 24
        }
        # 이미 알림을 보낸 항목을 추적하기 위한 집합 (중복 알림 방지용)
        self.notified_items = set()

        self.init_ui()
        
        # 앱 시작 시 기존 데이터가 있다면 알림 확인
        self.check_and_show_alerts()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.input_layout = QHBoxLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("식품 이름")
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("유통기한 (YYYY-MM-DD)")
        self.add_button = QPushButton("추가")
        self.add_button.clicked.connect(self.add_food)

        self.setting_button = QPushButton("⚙️ 설정")
        self.setting_button.clicked.connect(self.open_settings)

        self.time_label = QLabel()
        self.update_time_label()

        self.toggle_button = QPushButton("▼")
        self.toggle_button.setFixedWidth(30)
        self.toggle_button.clicked.connect(self.toggle_time_controls)

        self.time_control_widget = QWidget()
        self.time_control_layout = QHBoxLayout()
        self.time_control_widget.setLayout(self.time_control_layout)
        self.time_control_widget.setVisible(False)

        self.add_time_button("+1분", 1)
        self.add_time_button("-1분", -1)
        self.add_time_button("+30분", 30)
        self.add_time_button("+1일", 24 * 60)

        reset_button = QPushButton("현재 시간으로 초기화")
        reset_button.clicked.connect(self.reset_time)
        self.time_control_layout.addWidget(reset_button)

        self.input_layout.addWidget(self.name_input)
        self.input_layout.addWidget(self.date_input)
        self.input_layout.addWidget(self.add_button)
        self.input_layout.addWidget(self.setting_button)
        self.layout.addLayout(self.input_layout)

        time_control_row = QHBoxLayout()
        time_control_row.addWidget(QLabel("현재 시간:"))
        time_control_row.addWidget(self.time_label)
        time_control_row.addWidget(self.toggle_button)
        time_control_row.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.layout.addLayout(time_control_row)
        self.layout.addWidget(self.time_control_widget)

        self.valid_list_widget = QListWidget()
        self.expired_list_widget = QListWidget()
        self.layout.addWidget(QLabel("✅ 유효한 식품 목록"))
        self.layout.addWidget(self.valid_list_widget)
        self.layout.addWidget(QLabel("⚠️ 유통기한 지난 식품"))
        self.layout.addWidget(self.expired_list_widget)
        self.setLayout(self.layout)

    def add_time_button(self, label, minutes):
        btn = QPushButton(label)
        btn.clicked.connect(lambda: self.change_time(minutes))
        self.time_control_layout.addWidget(btn)

    def update_time_label(self):
        self.time_label.setText(get_now().strftime("%Y-%m-%d %H:%M"))

    def change_time(self, minutes):
        global simulated_now
        simulated_now += timedelta(minutes=minutes)
        self.update_lists()
        self.check_and_show_alerts()

    def reset_time(self):
        global simulated_now
        simulated_now = datetime.now()
        self.update_lists()
        self.check_and_show_alerts()

    def toggle_time_controls(self):
        is_visible = self.time_control_widget.isVisible()
        self.time_control_widget.setVisible(not is_visible)
        self.toggle_button.setText("▲" if not is_visible else "▼")

    def open_settings(self):
        dialog = SettingsDialog(self, current_settings=self.settings)
        if dialog.exec_():
            self.settings = dialog.get_settings()
            QMessageBox.information(self, "설정 완료", "설정이 저장되었습니다.")
            self.update_lists()
            self.check_and_show_alerts()

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

        # 새로 추가된 항목에 대해서만 알림 확인
        self.check_and_show_alerts(check_item=item)

    def update_lists(self):
        self.valid_list_widget.clear()
        self.expired_list_widget.clear()
        self.update_time_label()

        # 유통기한이 임박한 순서대로 정렬
        self.food_list.sort(key=lambda x: x.expiry_date)
        
        # 알림을 받은 후 상태가 변경된 항목을 notified_items에서 제거
        items_to_unnotify = set()
        for item_name in self.notified_items:
            found_item = next((item for item in self.food_list if item.name == item_name), None)
            if found_item and not found_item.is_expired() and found_item.time_left().total_seconds() / 3600 > self.settings["notify_hours_before"]:
                 items_to_unnotify.add(item_name)
        self.notified_items -= items_to_unnotify

        for item in self.food_list:
            if item.is_expired():
                self.expired_list_widget.addItem(str(item))
            else:
                self.valid_list_widget.addItem(str(item))

    # === [핵심 수정] 알림 함수 통합 및 개선 ===
    def check_and_show_alerts(self, check_item=None):
        """
        알림 조건을 확인하고 하나의 메시지 박스로 통합하여 보여줍니다.
        `check_item`이 주어지면 해당 항목만 확인하고, 그렇지 않으면 전체 목록을 확인합니다.
        """
        now = get_now()
        if not self.settings["night_notify"] and (now.hour >= 22 or now.hour < 8):
            return  # 야간 알림 비활성화 시 함수 종료

        expired_alerts = []
        imminent_alerts = []
        
        items_to_check = [check_item] if check_item else self.food_list

        for item in items_to_check:
            if item.name in self.notified_items:
                continue # 이미 알림을 보낸 항목은 건너뜀

            hours_left = item.time_left().total_seconds() / 3600
            
            if item.is_expired():
                expired_alerts.append(item.name)
                self.notified_items.add(item.name) # 알림 목록에 추가
            elif 0 <= hours_left <= self.settings["notify_hours_before"]:
                imminent_alerts.append(f"{item.name} ({int(hours_left)}시간 남음)")
                self.notified_items.add(item.name) # 알림 목록에 추가
        
        messages = []
        if expired_alerts:
            messages.append("--- 유통기한 만료 ---\n" + "\n".join(expired_alerts))
        if imminent_alerts:
            messages.append("--- 유통기한 임박 ---\n" + "\n".join(imminent_alerts))

        if messages:
            full_message = "\n\n".join(messages)
            # QTimer.singleShot: 현재 이벤트 처리가 끝난 후 메시지 박스를 띄워 충돌 방지
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "식품 알림", full_message))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = FridgeApp()
    window.show()
    sys.exit(app.exec_())
