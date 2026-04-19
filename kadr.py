import sys
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QDialog, QFormLayout, QDateEdit, QComboBox, QMessageBox,
    QGroupBox, QHeaderView, QTabWidget, QTextEdit, QSpinBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QIcon, QFont


class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_name="hr_database.db"):
        self.db_name = db_name
        self.create_tables()
    
    def get_connection(self):
        """Получение соединения с БД"""
        return sqlite3.connect(self.db_name)
    
    def create_tables(self):
        """Создание таблиц базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица сотрудников
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_name TEXT NOT NULL,
                first_name TEXT NOT NULL,
                patronymic TEXT,
                birth_date TEXT,
                position TEXT,
                department TEXT,
                phone TEXT,
                email TEXT,
                hire_date TEXT,
                salary REAL,
                status TEXT DEFAULT 'active',
                photo_path TEXT
            )
        ''')
        
        # Таблица отделов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                head_id INTEGER,
                FOREIGN KEY (head_id) REFERENCES employees (id)
            )
        ''')
        
        # Таблица должностей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                base_salary REAL,
                requirements TEXT
            )
        ''')
        
        # Таблица отпусков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vacations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                type TEXT,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
        ''')
        
        # Добавим тестового сотрудника, если таблица пуста
        cursor.execute("SELECT COUNT(*) FROM employees")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO employees (last_name, first_name, patronymic, position, department, phone, email, hire_date, salary, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ("Иванов", "Иван", "Иванович", "Разработчик", "IT-отдел", 
                  "+7 (999) 123-45-67", "ivan@example.com", 
                  datetime.now().strftime("%Y-%m-%d"), 50000, "active"))
        
        conn.commit()
        conn.close()


class EmployeeDialog(QDialog):
    """Диалог добавления/редактирования сотрудника (ЗАГЛУШКА)"""
    
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.setWindowTitle("Добавление сотрудника" if not employee_id else "Редактирование сотрудника")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Простая форма-заглушка
        form_layout = QFormLayout()
        
        self.last_name_edit = QLineEdit()
        self.first_name_edit = QLineEdit()
        self.position_edit = QLineEdit()
        
        form_layout.addRow("Фамилия:", self.last_name_edit)
        form_layout.addRow("Имя:", self.first_name_edit)
        form_layout.addRow("Должность:", self.position_edit)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save_employee)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
        if self.employee_id:
            self.last_name_edit.setText("Иванов")
            self.first_name_edit.setText("Иван")
            self.position_edit.setText("Разработчик")
    
    def save_employee(self):
        """ЗАГЛУШКА: Сохранение сотрудника"""
        if not self.last_name_edit.text() or not self.first_name_edit.text():
            QMessageBox.warning(self, "Ошибка", "Заполните фамилию и имя")
            return
        
        QMessageBox.information(self, "Успех", f"Сотрудник {self.last_name_edit.text()} {self.first_name_edit.text()} сохранен (ЗАГЛУШКА)")
        self.accept()


class HRApp(QMainWindow):
    """Главное окно приложения кадрового учета"""
    
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.current_employee_id = None
        self.init_ui()
        self.load_employees()
    
    def init_ui(self):
        self.setWindowTitle("Система кадрового учета")
        self.setGeometry(100, 100, 1200, 700)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Верхняя панель с кнопками
        top_panel = QHBoxLayout()
        
        self.add_btn = QPushButton(" Добавить сотрудника")
        self.add_btn.clicked.connect(self.add_employee)
        
        self.edit_btn = QPushButton(" Редактировать")
        self.edit_btn.clicked.connect(self.edit_employee)
        
        self.delete_btn = QPushButton(" Удалить")
        self.delete_btn.clicked.connect(self.delete_employee)
        
        self.vacation_btn = QPushButton(" Добавить отпуск")
        self.vacation_btn.clicked.connect(self.add_vacation)
        
        self.refresh_btn = QPushButton(" Обновить")
        self.refresh_btn.clicked.connect(self.load_employees)
        
        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск сотрудников...")
        self.search_edit.textChanged.connect(self.search_employees)
        
        top_panel.addWidget(self.add_btn)
        top_panel.addWidget(self.edit_btn)
        top_panel.addWidget(self.delete_btn)
        top_panel.addWidget(self.vacation_btn)
        top_panel.addWidget(self.refresh_btn)
        top_panel.addStretch()
        top_panel.addWidget(QLabel("Поиск:"))
        top_panel.addWidget(self.search_edit)
        
        main_layout.addLayout(top_panel)
        
        # Таблица сотрудников
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Фамилия", "Имя", "Отчество", "Должность",
            "Отдел", "Телефон", "Email", "Дата приема", "Статус"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.view_employee_details)
        
        main_layout.addWidget(self.table)
        
        # Нижняя панель с информацией
        info_panel = QHBoxLayout()
        self.status_label = QLabel("Готов к работе")
        info_panel.addWidget(self.status_label)
        info_panel.addStretch()
        
        main_layout.addLayout(info_panel)
        
        # Стилизация
        self.setStyleSheet("""
    QMainWindow {
        background-color: #1e1e2e;
    }
    QPushButton {
        background-color: #89b4fa;
        color: #1e1e2e;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #b4befe;
    }
    QPushButton:pressed {
        background-color: #6c96e0;
    }
    QTableWidget {
        background-color: #181825;
        alternate-background-color: #1e1e2e;
        gridline-color: #313244;
        color: #cdd6f4;
        selection-background-color: #45475a;
    }
    QHeaderView::section {
        background-color: #11111b;
        padding: 8px;
        border: 1px solid #313244;
        font-weight: bold;
        color: #89b4fa;
    }
    QLineEdit {
        padding: 6px;
        border: 1px solid #45475a;
        border-radius: 4px;
        background-color: #181825;
        color: #cdd6f4;
    }
    QLineEdit:focus {
        border-color: #89b4fa;
    }
    QLineEdit[placeholderText="Поиск сотрудников..."] {
        color: #6c7086;
    }
    QLabel {
        color: #cdd6f4;
    }
    QComboBox {
        padding: 6px;
        border: 1px solid #45475a;
        border-radius: 4px;
        background-color: #181825;
        color: #cdd6f4;
    }
    QComboBox:hover {
        border-color: #89b4fa;
    }
    QComboBox::drop-down {
        border: none;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid #cdd6f4;
        margin-right: 5px;
    }
    QDateEdit {
        padding: 6px;
        border: 1px solid #45475a;
        border-radius: 4px;
        background-color: #181825;
        color: #cdd6f4;
    }
    QDateEdit::drop-down {
        border: none;
    }
    QDateEdit::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid #cdd6f4;
    }
    QDialog {
        background-color: #1e1e2e;
    }
    QMessageBox {
        background-color: #1e1e2e;
        color: #cdd6f4;
    }
    QMessageBox QPushButton {
        min-width: 80px;
    }
    QScrollBar:vertical {
        background-color: #11111b;
        width: 12px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background-color: #45475a;
        border-radius: 6px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #89b4fa;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar:horizontal {
        background-color: #11111b;
        height: 12px;
        border-radius: 6px;
    }
    QScrollBar::handle:horizontal {
        background-color: #45475a;
        border-radius: 6px;
        min-width: 20px;
    }
    QScrollBar::handle:horizontal:hover {
        background-color: #89b4fa;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    QTabWidget::pane {
        border: 1px solid #313244;
        background-color: #181825;
        border-radius: 4px;
    }
    QTabBar::tab {
        background-color: #11111b;
        color: #6c7086;
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background-color: #181825;
        color: #89b4fa;
    }
    QTabBar::tab:hover:!selected {
        background-color: #1e1e2e;
        color: #cdd6f4;
    }
    QGroupBox {
        color: #89b4fa;
        border: 1px solid #313244;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }
    QTextEdit {
        background-color: #181825;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
    }
""")
    
    def load_employees(self):
        """Загрузка списка сотрудников в таблицу"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, last_name, first_name, patronymic, position, 
                   department, phone, email, hire_date, status
            FROM employees
            ORDER BY last_name, first_name
        ''')
        
        employees = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(len(employees))
        
        status_translation = {
            "active": "Активен",
            "on_vacation": "В отпуске",
            "sick_leave": "На больничном",
            "fired": "Уволен"
        }
        
        for row, emp in enumerate(employees):
            self.table.setItem(row, 0, QTableWidgetItem(str(emp[0])))
            self.table.setItem(row, 1, QTableWidgetItem(emp[1]))
            self.table.setItem(row, 2, QTableWidgetItem(emp[2]))
            self.table.setItem(row, 3, QTableWidgetItem(emp[3] or ""))
            self.table.setItem(row, 4, QTableWidgetItem(emp[4] or ""))
            self.table.setItem(row, 5, QTableWidgetItem(emp[5] or ""))
            self.table.setItem(row, 6, QTableWidgetItem(emp[6] or ""))
            self.table.setItem(row, 7, QTableWidgetItem(emp[7] or ""))
            self.table.setItem(row, 8, QTableWidgetItem(emp[8] or ""))
            
            status_text = status_translation.get(emp[9], emp[9])
            status_item = QTableWidgetItem(status_text)
            
            # Цветовая индикация статуса
            if emp[9] == "fired":
                status_item.setForeground(Qt.red)
            elif emp[9] == "on_vacation":
                status_item.setForeground(Qt.blue)
            elif emp[9] == "sick_leave":
                status_item.setForeground(Qt.darkYellow)
            
            self.table.setItem(row, 9, status_item)
        
        self.table.resizeColumnsToContents()
        self.status_label.setText(f"Всего сотрудников: {len(employees)}")
    
    def search_employees(self):
        """ЗАГЛУШКА: Поиск сотрудников"""
        search_text = self.search_edit.text().lower()
        if not search_text:
            # Показываем всех
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            self.status_label.setText(f"Всего сотрудников: {self.table.rowCount()}")
            return
        
        # Простой поиск по таблице
        visible_count = 0
        for row in range(self.table.rowCount()):
            hide_row = True
            for col in range(1, 4):  # Поиск по ФИО
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    hide_row = False
                    break
            self.table.setRowHidden(row, hide_row)
            if not hide_row:
                visible_count += 1
        
        self.status_label.setText(f"Найдено: {visible_count} из {self.table.rowCount()} сотрудников")
    
    def add_employee(self):
        """Добавление сотрудника"""
        dialog = EmployeeDialog(self)
        if dialog.exec():
            self.load_employees()
            QMessageBox.information(self, "Успех", "Сотрудник добавлен (тестовые данные)")
    
    def edit_employee(self):
        """Редактирование сотрудника"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            employee_id = int(self.table.item(current_row, 0).text())
            employee_name = self.table.item(current_row, 1).text()
            dialog = EmployeeDialog(self, employee_id)
            if dialog.exec():
                self.load_employees()
                QMessageBox.information(self, "Успех", f"Сотрудник {employee_name} отредактирован (ЗАГЛУШКА)")
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите сотрудника для редактирования")
    
    def delete_employee(self):
        """Удаление сотрудника"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            employee_id = int(self.table.item(current_row, 0).text())
            employee_name = self.table.item(current_row, 1).text()
            
            reply = QMessageBox.question(self, "Подтверждение",
                                       f"Вы уверены, что хотите удалить сотрудника {employee_name}?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
                conn.commit()
                conn.close()
                self.load_employees()
                QMessageBox.information(self, "Успех", f"Сотрудник {employee_name} удален")
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите сотрудника для удаления")
    
    def add_vacation(self):
        """ЗАГЛУШКА: Добавление отпуска"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            employee_name = self.table.item(current_row, 1).text()
            QMessageBox.information(self, "Информация", 
                                   f"Функция добавления отпуска для сотрудника {employee_name}\n(ЗАГЛУШКА - будет реализовано позже)")
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите сотрудника")
    
    def view_employee_details(self):
        """ЗАГЛУШКА: Просмотр деталей сотрудника"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            employee_id = self.table.item(current_row, 0).text()
            last_name = self.table.item(current_row, 1).text()
            first_name = self.table.item(current_row, 2).text()
            position = self.table.item(current_row, 4).text()
            
            details = f"""
            <h3>Карточка сотрудника</h3>
            <b>ID:</b> {employee_id}<br>
            <b>ФИО:</b> {last_name} {first_name}<br>
            <b>Должность:</b> {position}<br>
            <br>
            <i>ЗАГЛУШКА - подробная информация будет доступна в следующей версии</i>
            """
            
            QMessageBox.information(self, "Информация о сотруднике", details)
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите сотрудника")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = HRApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
