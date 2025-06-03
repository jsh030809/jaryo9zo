import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox,
    QCheckBox, QComboBox, QDialog, QSpacerItem, QSizePolicy
)
from datetime import datetime, timedelta

# 시뮬레이션 시간
simulated_now = datetime.now()

def get_now():
    return simulated_now

class FridgeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("냉장고 유통기한 관리")
        self.food_list = []
        self.settings = {
            "night_notify": True,
            "notify_hours_before": 24
        }

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

        self.toggle_button = QPushButton(">")
        self.toggle_button.setFixedWidth(25)
        self.toggle_button.clicked.connect(self.toggle_time_controls)

        self.time_control_widget = QWidget()
        self.time_control_layout = QHBoxLayout()
        self.time_control_widget.setLayout(self.time_control_layout)
        self.time_control_widget.setVisible(False)

        self.add_time_button("+1분", 1)
        self.add_time_button("-1분", -1)
        self.add_time_button("+5분", 5)
        self.add_time_button("-5분", -5)
        self.add_time_button("+30분", 30)
        self.add_time_button("-30분", -30)

        # [✅ 5] 현재 시간으로 초기화 버튼 추가
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

        self.valid_label = QLabel("✅ 유효한 식품 목록")
        self.valid_list_widget = QListWidget()

        self.expired_label = QLabel("⚠️ 유통기한 지난 식품")
        self.expired_list_widget = QListWidget()

        self.layout.addWidget(self.valid_label)
        self.layout.addWidget(self.valid_list_widget)
        self.layout.addWidget(self.expired_label)
        self.layout.addWidget(self.expired_list_widget)

        self.setLayout(self.layout)

        # [✅ 4] 앱 실행 시 모든 알림 확인
        self.check_all_alerts()

    def add_time_button(self, label, minutes):
        btn = QPushButton(label)
        btn.clicked.connect(lambda: self.change_time(minutes))
        self.time_control_layout.addWidget(btn)

    def update_time_label(self):
        self.time_label.setText(get_now().strftime("%Y-%m-%d %H:%M"))

    def change_time(self, minutes):
        global simulated_now
        simulated_now += timedelta(minutes=minutes)
        self.update_time_label()
        self.update_lists()
        self.check_all_alerts()  # [✅ 4] 시간 변경 시 전체 알림 재확인

    def reset_time(self):
        global simulated_now
        simulated_now = datetime.now()
        self.update_time_label()
        self.update_lists()
        self.check_all_alerts()  # [✅ 5] 리셋 후 알림 확인

    def toggle_time_controls(self):
        self.time_control_widget.setVisible(not self.time_control_widget.isVisible())

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.settings = dialog.get_settings()
            self.update_lists()
            self.check_all_alerts()  # [✅ 4] 설정 변경 시 알림 재확인
            QMessageBox.information(self, "설정 완료", "설정이 저장되었습니다.")

    def add_food(self):
        name = self.name_input.text().strip()
        date_str = self.date_input.text().strip()

        # [✅ 2] 이름 입력 검증
        if not name:
            QMessageBox.warning(self, "오류", "식품 이름을 입력해주세요.")
            return

        # [✅ 3] 중복 식품 검사
        if any(item.name == name for item in self.food_list):
            QMessageBox.warning(self, "중복 항목", f"{name}은(는) 이미 목록에 있습니다.")
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

        self.check_alert(item)

    def check_alert(self, item):
        hours_left = item.time_left().total_seconds() / 3600
        if item.is_expired():
            QMessageBox.warning(self, "경고", f"{item.name}은 유통기한이 지났습니다!")
        elif hours_left <= self.settings["notify_hours_before"]:
            QMessageBox.information(self, "알림", f"{item.name}의 유통기한이 곧 도래합니다!")

    # [✅ 4] 모든 식품에 대해 알림 재검사
    def check_all_alerts(self):
        for item in self.food_list:
            self.check_alert(item)

    def update_lists(self):
        self.valid_list_widget.clear()
        self.expired_list_widget.clear()
        self.update_time_label()

        for item in self.food_list:
            if item.is_expired():
                self.expired_list_widget.addItem(str(item))
            else:
                self.valid_list_widget.addItem(str(item))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FridgeApp()
    window.show()
    sys.exit(app.exec_())
