import sys
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QDialog, QFormLayout, QDateEdit, QComboBox, QMessageBox,
    QGroupBox, QHeaderView, QTabWidget, QTextEdit, QSpinBox
)
from PySide6.QtCore import Qt, QDate, Signal
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
        
        conn.commit()
        conn.close()
    
    def add_employee(self, data):
        """Добавление нового сотрудника"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO employees (
                last_name, first_name, patronymic, birth_date, position,
                department, phone, email, hire_date, salary, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data)
        conn.commit()
        employee_id = cursor.lastrowid
        conn.close()
        return employee_id
    
    def get_employees(self, filters=None):
        """Получение списка сотрудников с возможностью фильтрации"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM employees WHERE 1=1"
        params = []
        
        if filters:
            if filters.get('department'):
                query += " AND department = ?"
                params.append(filters['department'])
            if filters.get('status'):
                query += " AND status = ?"
                params.append(filters['status'])
            if filters.get('search'):
                query += " AND (last_name LIKE ? OR first_name LIKE ? OR position LIKE ?)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term, search_term])
        
        query += " ORDER BY last_name, first_name"
        
        cursor.execute(query, params)
        employees = cursor.fetchall()
        conn.close()
        return employees
    
    def get_employee_by_id(self, employee_id):
        """Получение данных сотрудника по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        employee = cursor.fetchone()
        conn.close()
        return employee
    
    def update_employee(self, employee_id, data):
        """Обновление данных сотрудника"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE employees 
            SET last_name=?, first_name=?, patronymic=?, birth_date=?,
                position=?, department=?, phone=?, email=?, hire_date=?,
                salary=?, status=?
            WHERE id=?
        ''', (*data, employee_id))
        conn.commit()
        conn.close()
    
    def delete_employee(self, employee_id):
        """Удаление сотрудника"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
        conn.commit()
        conn.close()
    
    def get_departments(self):
        """Получение списка отделов"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM departments ORDER BY name")
        departments = cursor.fetchall()
        conn.close()
        return departments
    
    def add_department(self, name, description=""):
        """Добавление нового отдела"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO departments (name, description) VALUES (?, ?)",
                (name, description)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def add_vacation(self, employee_id, start_date, end_date, vacation_type):
        """Добавление отпуска"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vacations (employee_id, start_date, end_date, type, status)
            VALUES (?, ?, ?, ?, 'approved')
        ''', (employee_id, start_date, end_date, vacation_type))
        conn.commit()
        conn.close()
    
    def get_employee_vacations(self, employee_id):
        """Получение отпусков сотрудника"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM vacations 
            WHERE employee_id = ? 
            ORDER BY start_date DESC
        ''', (employee_id,))
        vacations = cursor.fetchall()
        conn.close()
        return vacations


class EmployeeDialog(QDialog):
    """Диалог добавления/редактирования сотрудника"""
    
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = Database()
        self.setWindowTitle("Добавление сотрудника" if not employee_id else "Редактирование сотрудника")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.init_ui()
        
        if employee_id:
            self.load_employee_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Форма
        form_layout = QFormLayout()
        
        # Личные данные
        self.last_name_edit = QLineEdit()
        self.first_name_edit = QLineEdit()
        self.patronymic_edit = QLineEdit()
        self.birth_date = QDateEdit()
        self.birth_date.setCalendarPopup(True)
        self.birth_date.setDate(QDate.currentDate().addYears(-30))
        
        # Рабочая информация
        self.position_edit = QLineEdit()
        self.department_combo = QComboBox()
        self.load_departments()
        self.department_combo.setEditable(True)
        
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.hire_date = QDateEdit()
        self.hire_date.setCalendarPopup(True)
        self.hire_date.setDate(QDate.currentDate())
        
        self.salary_edit = QLineEdit()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "on_vacation", "sick_leave", "fired"])
        
        # Переводы
        status_labels = {
            "active": "Активен",
            "on_vacation": "В отпуске",
            "sick_leave": "На больничном",
            "fired": "Уволен"
        }
        for i in range(self.status_combo.count()):
            item_text = self.status_combo.itemText(i)
            if item_text in status_labels:
                self.status_combo.setItemText(i, status_labels[item_text])
        
        form_layout.addRow("Фамилия:*", self.last_name_edit)
        form_layout.addRow("Имя:*", self.first_name_edit)
        form_layout.addRow("Отчество:", self.patronymic_edit)
        form_layout.addRow("Дата рождения:", self.birth_date)
        form_layout.addRow("Должность:*", self.position_edit)
        form_layout.addRow("Отдел:", self.department_combo)
        form_layout.addRow("Телефон:", self.phone_edit)
        form_layout.addRow("Email:", self.email_edit)
        form_layout.addRow("Дата приема:", self.hire_date)
        form_layout.addRow("Зарплата:", self.salary_edit)
        form_layout.addRow("Статус:", self.status_combo)
        
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
    
    def load_departments(self):
        """Загрузка отделов в комбобокс"""
        self.department_combo.clear()
        departments = self.db.get_departments()
        self.department_combo.addItem("")
        for dept in departments:
            self.department_combo.addItem(dept[1])
    
    def load_employee_data(self):
        """Загрузка данных сотрудника для редактирования"""
        employee = self.db.get_employee_by_id(self.employee_id)
        if employee:
            self.last_name_edit.setText(employee[1])
            self.first_name_edit.setText(employee[2])
            self.patronymic_edit.setText(employee[3] or "")
            
            if employee[4]:
                date = QDate.fromString(employee[4], "yyyy-MM-dd")
                self.birth_date.setDate(date)
            
            self.position_edit.setText(employee[5] or "")
            
            # Выбор отдела
            index = self.department_combo.findText(employee[6] or "")
            if index >= 0:
                self.department_combo.setCurrentIndex(index)
            
            self.phone_edit.setText(employee[7] or "")
            self.email_edit.setText(employee[8] or "")
            
            if employee[9]:
                date = QDate.fromString(employee[9], "yyyy-MM-dd")
                self.hire_date.setDate(date)
            
            self.salary_edit.setText(str(employee[10]) if employee[10] else "")
            
            # Статус
            status_map = {
                "active": "Активен",
                "on_vacation": "В отпуске",
                "sick_leave": "На больничном",
                "fired": "Уволен"
            }
            status_text = status_map.get(employee[11], "Активен")
            index = self.status_combo.findText(status_text)
            if index >= 0:
                self.status_combo.setCurrentIndex(index)
    
    def save_employee(self):
        """Сохранение сотрудника"""
        if not self.last_name_edit.text() or not self.first_name_edit.text():
            QMessageBox.warning(self, "Ошибка", "Фамилия и имя обязательны для заполнения!")
            return
        
        # Сбор данных
        data = (
            self.last_name_edit.text(),
            self.first_name_edit.text(),
            self.patronymic_edit.text() or None,
            self.birth_date.date().toString("yyyy-MM-dd"),
            self.position_edit.text() or None,
            self.department_combo.currentText() or None,
            self.phone_edit.text() or None,
            self.email_edit.text() or None,
            self.hire_date.date().toString("yyyy-MM-dd"),
            float(self.salary_edit.text()) if self.salary_edit.text() else None,
            self.get_status_value()
        )
        
        if self.employee_id:
            self.db.update_employee(self.employee_id, data)
            QMessageBox.information(self, "Успех", "Данные сотрудника обновлены!")
        else:
            self.db.add_employee(data)
            QMessageBox.information(self, "Успех", "Сотрудник добавлен!")
        
        self.accept()
    
    def get_status_value(self):
        """Получение значения статуса для БД"""
        status_map = {
            "Активен": "active",
            "В отпуске": "on_vacation",
            "На больничном": "sick_leave",
            "Уволен": "fired"
        }
        return status_map.get(self.status_combo.currentText(), "active")


class VacationDialog(QDialog):
    """Диалог добавления отпуска"""
    
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = Database()
        self.setWindowTitle("Добавление отпуска")
        self.setModal(True)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(14))
        
        self.vacation_type = QComboBox()
        self.vacation_type.addItems(["Ежегодный", "Дополнительный", "Без содержания", "Учебный"])
        
        form_layout.addRow("Дата начала:", self.start_date)
        form_layout.addRow("Дата окончания:", self.end_date)
        form_layout.addRow("Тип отпуска:", self.vacation_type)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save_vacation)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def save_vacation(self):
        """Сохранение отпуска"""
        if self.start_date.date() > self.end_date.date():
            QMessageBox.warning(self, "Ошибка", "Дата окончания не может быть раньше даты начала!")
            return
        
        self.db.add_vacation(
            self.employee_id,
            self.start_date.date().toString("yyyy-MM-dd"),
            self.end_date.date().toString("yyyy-MM-dd"),
            self.vacation_type.currentText()
        )
        
        QMessageBox.information(self, "Успех", "Отпуск добавлен!")
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
        
        self.add_btn = QPushButton("➕ Добавить сотрудника")
        self.add_btn.clicked.connect(self.add_employee)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_employee)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_employee)
        
        self.vacation_btn = QPushButton("🏖️ Добавить отпуск")
        self.vacation_btn.clicked.connect(self.add_vacation)
        
        self.refresh_btn = QPushButton("🔄 Обновить")
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
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f9f9f9;
                gridline-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px;
                border: 1px solid #e0e0e0;
                font-weight: bold;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
    
    def load_employees(self):
        """Загрузка списка сотрудников в таблицу"""
        employees = self.db.get_employees()
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
            self.table.setItem(row, 4, QTableWidgetItem(emp[5] or ""))
            self.table.setItem(row, 5, QTableWidgetItem(emp[6] or ""))
            self.table.setItem(row, 6, QTableWidgetItem(emp[7] or ""))
            self.table.setItem(row, 7, QTableWidgetItem(emp[8] or ""))
            self.table.setItem(row, 8, QTableWidgetItem(emp[9] or ""))
            
            status_text = status_translation.get(emp[11], emp[11])
            status_item = QTableWidgetItem(status_text)
            
            # Цветовая индикация статуса
            if emp[11] == "fired":
                status_item.setForeground(Qt.red)
            elif emp[11] == "on_vacation":
                status_item.setForeground(Qt.blue)
            elif emp[11] == "sick_leave":
                status_item.setForeground(Qt.darkYellow)
            
            self.table.setItem(row, 9, status_item)
        
        self.table.resizeColumnsToContents()
        self.status_label.setText(f"Всего сотрудников: {len(employees)}")
    
    def search_employees(self):
        """Поиск сотрудников"""
        search_text = self.search_edit.text()
        if search_text:
            filters = {'search': search_text}
            employees = self.db.get_employees(filters)
            
            self.table.setRowCount(len(employees))
            for row, emp in enumerate(employees):
                self.table.setItem(row, 0, QTableWidgetItem(str(emp[0])))
                self.table.setItem(row, 1, QTableWidgetItem(emp[1]))
                self.table.setItem(row, 2, QTableWidgetItem(emp[2]))
                # ... остальные поля
        else:
            self.load_employees()
    
    def add_employee(self):
        """Добавление нового сотрудника"""
        dialog = EmployeeDialog(self)
        if dialog.exec():
            self.load_employees()
    
    def edit_employee(self):
        """Редактирование выбранного сотрудника"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника для редактирования!")
            return
        
        employee_id = int(self.table.item(current_row, 0).text())
        dialog = EmployeeDialog(self, employee_id)
        if dialog.exec():
            self.load_employees()
    
    def delete_employee(self):
        """Удаление сотрудника"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника для удаления!")
            return
        
        employee_id = int(self.table.item(current_row, 0).text())
        employee_name = f"{self.table.item(current_row, 1).text()} {self.table.item(current_row, 2).text()}"
        
        reply = QMessageBox.question(
            self, "Подтверждение удаления",
            f"Вы уверены, что хотите удалить сотрудника {employee_name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db.delete_employee(employee_id)
            self.load_employees()
            QMessageBox.information(self, "Успех", "Сотрудник удален!")
    
    def add_vacation(self):
        """Добавление отпуска для сотрудника"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника для добавления отпуска!")
            return
        
        employee_id = int(self.table.item(current_row, 0).text())
        dialog = VacationDialog(self, employee_id)
        if dialog.exec():
            self.load_employees()
    
    def view_employee_details(self, index):
        """Просмотр подробной информации о сотруднике"""
        row = index.row()
        employee_id = int(self.table.item(row, 0).text())
        employee = self.db.get_employee_by_id(employee_id)
        
        if not employee:
            return
        
        # Создаем диалог с подробной информацией
        details_dialog = QDialog(self)
        details_dialog.setWindowTitle(f"Информация о сотруднике - {employee[1]} {employee[2]}")
        details_dialog.setMinimumWidth(600)
        details_dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        
        # Создаем вкладки
        tabs = QTabWidget()
        
        # Вкладка "Основная информация"
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        
        info_data = [
            ("Фамилия:", employee[1]),
            ("Имя:", employee[2]),
            ("Отчество:", employee[3] or "—"),
            ("Дата рождения:", employee[4] or "—"),
            ("Должность:", employee[5] or "—"),
            ("Отдел:", employee[6] or "—"),
            ("Телефон:", employee[7] or "—"),
            ("Email:", employee[8] or "—"),
            ("Дата приема:", employee[9] or "—"),
            ("Зарплата:", f"{employee[10]:,.2f} ₽" if employee[10] else "—"),
        ]
        
        for label, value in info_data:
            basic_layout.addRow(label, QLabel(str(value)))
        
        tabs.addTab(basic_tab, "Основная информация")
        
        # Вкладка "Отпуска"
        vacation_tab = QWidget()
        vacation_layout = QVBoxLayout(vacation_tab)
        
        vacation_table = QTableWidget()
        vacation_table.setColumnCount(4)
        vacation_table.setHorizontalHeaderLabels(["Дата начала", "Дата окончания", "Тип", "Статус"])
        
        vacations = self.db.get_employee_vacations(employee_id)
        vacation_table.setRowCount(len(vacations))
        
        for row, vac in enumerate(vacations):
            vacation_table.setItem(row, 0, QTableWidgetItem(vac[2]))
            vacation_table.setItem(row, 1, QTableWidgetItem(vac[3]))
            vacation_table.setItem(row, 2, QTableWidgetItem(vac[4]))
            vacation_table.setItem(row, 3, QTableWidgetItem(vac[5]))
        
        vacation_table.horizontalHeader().setStretchLastSection(True)
        vacation_layout.addWidget(vacation_table)
        
        tabs.addTab(vacation_tab, "Отпуска")
        
        layout.addWidget(tabs)
        
        # Кнопка закрытия
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(details_dialog.accept)
        layout.addWidget(close_btn)
        
        details_dialog.setLayout(layout)
        details_dialog.exec()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = HRApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
