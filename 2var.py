import sys
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QDialog, QFormLayout, QDateEdit, QComboBox, QMessageBox,
    QGroupBox, QHeaderView, QTabWidget, QTextEdit, QSpinBox,
    QInputDialog
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QIcon, QFont


class Database:
    """Класс для работы с MySQL базой данных"""
    
    def __init__(self, host="localhost", user="root", password="", database="hr_database"):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.connect()
        self.create_database_if_not_exists()
        self.create_tables()
    
    def connect(self):
        """Установка соединения с MySQL"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
        except Error as e:
            QMessageBox.critical(None, "Ошибка подключения", 
                               f"Не удалось подключиться к MySQL:\n{str(e)}\n\n"
                               f"Убедитесь, что MySQL сервер запущен и параметры подключения верны.")
            sys.exit(1)
    
    def create_database_if_not_exists(self):
        """Создание базы данных если она не существует"""
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            cursor.execute(f"USE {self.database}")
            self.connection.database = self.database
        except Error as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось создать базу данных:\n{str(e)}")
            sys.exit(1)
        finally:
            cursor.close()
    
    def create_tables(self):
        """Создание таблиц базы данных"""
        cursor = self.connection.cursor()
        
        try:
            # Таблица сотрудников
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    last_name VARCHAR(100) NOT NULL,
                    first_name VARCHAR(100) NOT NULL,
                    patronymic VARCHAR(100),
                    birth_date DATE,
                    position VARCHAR(100),
                    department VARCHAR(100),
                    phone VARCHAR(20),
                    email VARCHAR(100),
                    hire_date DATE,
                    salary DECIMAL(10, 2),
                    status ENUM('active', 'on_vacation', 'sick_leave', 'fired') DEFAULT 'active',
                    photo_path VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица отделов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS departments (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT,
                    head_id INT,
                    FOREIGN KEY (head_id) REFERENCES employees(id) ON DELETE SET NULL
                )
            ''')
            
            # Таблица должностей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    base_salary DECIMAL(10, 2),
                    requirements TEXT
                )
            ''')
            
            # Таблица отпусков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vacations (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    employee_id INT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    type VARCHAR(50),
                    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
                )
            ''')
            
            # Таблица для аудита изменений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    table_name VARCHAR(50),
                    record_id INT,
                    action VARCHAR(20),
                    old_data TEXT,
                    new_data TEXT,
                    changed_by VARCHAR(100),
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.connection.commit()
            
        except Error as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось создать таблицы:\n{str(e)}")
            sys.exit(1)
        finally:
            cursor.close()
    
    def add_employee(self, data):
        """Добавление нового сотрудника"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO employees (
                    last_name, first_name, patronymic, birth_date, position,
                    department, phone, email, hire_date, salary, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', data)
            self.connection.commit()
            employee_id = cursor.lastrowid
            return employee_id
        except Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def get_employees(self, filters=None):
        """Получение списка сотрудников с возможностью фильтрации"""
        cursor = self.connection.cursor(dictionary=True)
        
        query = "SELECT * FROM employees WHERE 1=1"
        params = []
        
        if filters:
            if filters.get('department'):
                query += " AND department = %s"
                params.append(filters['department'])
            if filters.get('status'):
                query += " AND status = %s"
                params.append(filters['status'])
            if filters.get('search'):
                query += " AND (last_name LIKE %s OR first_name LIKE %s OR position LIKE %s)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term, search_term])
        
        query += " ORDER BY last_name, first_name"
        
        cursor.execute(query, params)
        employees = cursor.fetchall()
        cursor.close()
        
        # Преобразуем словари в кортежи для совместимости с существующим кодом
        return [tuple(emp.values()) for emp in employees]
    
    def get_employee_by_id(self, employee_id):
        """Получение данных сотрудника по ID"""
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        cursor.close()
        return tuple(employee.values()) if employee else None
    
    def update_employee(self, employee_id, data):
        """Обновление данных сотрудника"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                UPDATE employees 
                SET last_name=%s, first_name=%s, patronymic=%s, birth_date=%s,
                    position=%s, department=%s, phone=%s, email=%s, hire_date=%s,
                    salary=%s, status=%s
                WHERE id=%s
            ''', (*data, employee_id))
            self.connection.commit()
        except Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def delete_employee(self, employee_id):
        """Удаление сотрудника"""
        cursor = self.connection.cursor()
        try:
            cursor.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
            self.connection.commit()
        except Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def get_departments(self):
        """Получение списка отделов"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM departments ORDER BY name")
        departments = cursor.fetchall()
        cursor.close()
        return departments
    
    def add_department(self, name, description=""):
        """Добавление нового отдела"""
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO departments (name, description) VALUES (%s, %s)",
                (name, description)
            )
            self.connection.commit()
            return True
        except Error:
            self.connection.rollback()
            return False
        finally:
            cursor.close()
    
    def add_vacation(self, employee_id, start_date, end_date, vacation_type):
        """Добавление отпуска"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO vacations (employee_id, start_date, end_date, type, status)
                VALUES (%s, %s, %s, %s, 'approved')
            ''', (employee_id, start_date, end_date, vacation_type))
            self.connection.commit()
        except Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def get_employee_vacations(self, employee_id):
        """Получение отпусков сотрудника"""
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM vacations 
            WHERE employee_id = %s 
            ORDER BY start_date DESC
        ''', (employee_id,))
        vacations = cursor.fetchall()
        cursor.close()
        return vacations
    
    def get_statistics(self):
        """Получение статистики по сотрудникам"""
        cursor = self.connection.cursor(dictionary=True)
        
        stats = {}
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) as total FROM employees")
        stats['total'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as active FROM employees WHERE status = 'active'")
        stats['active'] = cursor.fetchone()['active']
        
        cursor.execute("SELECT COUNT(*) as on_vacation FROM employees WHERE status = 'on_vacation'")
        stats['on_vacation'] = cursor.fetchone()['on_vacation']
        
        cursor.execute("SELECT COUNT(*) as fired FROM employees WHERE status = 'fired'")
        stats['fired'] = cursor.fetchone()['fired']
        
        # Статистика по отделам
        cursor.execute('''
            SELECT department, COUNT(*) as count 
            FROM employees 
            WHERE department IS NOT NULL 
            GROUP BY department
        ''')
        stats['by_department'] = cursor.fetchall()
        
        cursor.close()
        return stats
    
    def backup_database(self, backup_path):
        """Создание резервной копии базы данных"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"BACKUP DATABASE {self.database} TO DISK = '{backup_path}'")
            self.connection.commit()
            cursor.close()
            return True
        except Error:
            return False
    
    def close_connection(self):
        """Закрытие соединения с БД"""
        if self.connection and self.connection.is_connected():
            self.connection.close()


class ConnectionDialog(QDialog):
    """Диалог настроек подключения к MySQL"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки подключения к MySQL")
        self.setModal(True)
        self.setFixedSize(400, 300)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.host_edit = QLineEdit("localhost")
        self.user_edit = QLineEdit("root")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.database_edit = QLineEdit("hr_database")
        
        form_layout.addRow("Хост:", self.host_edit)
        form_layout.addRow("Пользователь:", self.user_edit)
        form_layout.addRow("Пароль:", self.password_edit)
        form_layout.addRow("База данных:", self.database_edit)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        test_btn = QPushButton("Тест подключения")
        test_btn.clicked.connect(self.test_connection)
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(test_btn)
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def test_connection(self):
        """Тестирование подключения к MySQL"""
        try:
            conn = mysql.connector.connect(
                host=self.host_edit.text(),
                user=self.user_edit.text(),
                password=self.password_edit.text()
            )
            conn.close()
            self.status_label.setText("✓ Подключение успешно!")
            self.status_label.setStyleSheet("color: green;")
        except Error as e:
            self.status_label.setText(f"✗ Ошибка: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
    
    def get_connection_params(self):
        """Получение параметров подключения"""
        return {
            'host': self.host_edit.text(),
            'user': self.user_edit.text(),
            'password': self.password_edit.text(),
            'database': self.database_edit.text()
        }


class EmployeeDialog(QDialog):
    """Диалог добавления/редактирования сотрудника"""
    
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = parent.db if parent else None
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
        if self.db:
            self.department_combo.clear()
            departments = self.db.get_departments()
            self.department_combo.addItem("")
            for dept in departments:
                self.department_combo.addItem(dept[1])
    
    def load_employee_data(self):
        """Загрузка данных сотрудника для редактирования"""
        if not self.db:
            return
            
        employee = self.db.get_employee_by_id(self.employee_id)
        if employee:
            self.last_name_edit.setText(employee[1])
            self.first_name_edit.setText(employee[2])
            self.patronymic_edit.setText(employee[3] or "")
            
            if employee[4]:
                date = QDate.fromString(str(employee[4]), "yyyy-MM-dd")
                self.birth_date.setDate(date)
            
            self.position_edit.setText(employee[5] or "")
            
            # Выбор отдела
            index = self.department_combo.findText(employee[6] or "")
            if index >= 0:
                self.department_combo.setCurrentIndex(index)
            
            self.phone_edit.setText(employee[7] or "")
            self.email_edit.setText(employee[8] or "")
            
            if employee[9]:
                date = QDate.fromString(str(employee[9]), "yyyy-MM-dd")
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
        
        try:
            if self.employee_id:
                self.db.update_employee(self.employee_id, data)
                QMessageBox.information(self, "Успех", "Данные сотрудника обновлены!")
            else:
                self.db.add_employee(data)
                QMessageBox.information(self, "Успех", "Сотрудник добавлен!")
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить данные:\n{str(e)}")
    
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
        self.db = parent.db if parent else None
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
        
        try:
            self.db.add_vacation(
                self.employee_id,
                self.start_date.date().toString("yyyy-MM-dd"),
                self.end_date.date().toString("yyyy-MM-dd"),
                self.vacation_type.currentText()
            )
            
            QMessageBox.information(self, "Успех", "Отпуск добавлен!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить отпуск:\n{str(e)}")


class HRApp(QMainWindow):
    """Главное окно приложения кадрового учета"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_employee_id = None
        self.init_ui()
        self.load_employees()
    
    def init_ui(self):
        self.setWindowTitle("Система кадрового учета (MySQL)")
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
        
        self.stats_btn = QPushButton("📊 Статистика")
        self.stats_btn.clicked.connect(self.show_statistics)
        
        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск сотрудников...")
        self.search_edit.textChanged.connect(self.search_employees)
        
        top_panel.addWidget(self.add_btn)
        top_panel.addWidget(self.edit_btn)
        top_panel.addWidget(self.delete_btn)
        top_panel.addWidget(self.vacation_btn)
        top_panel.addWidget(self.refresh_btn)
        top_panel.addWidget(self.stats_btn)
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
        try:
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
                self.table.setItem(row, 8, QTableWidgetItem(str(emp[9]) if emp[9] else ""))
                
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
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные:\n{str(e)}")
    
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
                self.table.setItem(row, 3, QTableWidgetItem(emp[3] or ""))
                self.table.setItem(row, 4, QTableWidgetItem(emp[5] or ""))
                self.table.setItem(row, 5, QTableWidgetItem(emp[6] or ""))
                self.table.setItem(row, 6, QTableWidgetItem(emp[7] or ""))
                self.table.setItem(row, 7, QTableWidgetItem(emp[8] or ""))
                self.table.setItem(row, 8, QTableWidgetItem(str(emp[9]) if emp[9] else ""))
                
                status_translation = {
                    "active": "Активен",
                    "on_vacation": "В отпуске",
                    "sick_leave": "На больничном",
                    "fired": "Уволен"
                }
                status_text = status_translation.get(emp[11], emp[11])
                self.table.setItem(row, 9, QTableWidgetItem(status_text))
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
            try:
                self.db.delete_employee(employee_id)
                self.load_employees()
                QMessageBox.information(self, "Успех", "Сотрудник удален!")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить сотрудника:\n{str(e)}")
    
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
            ("Дата рождения:", str(employee[4]) if employee[4] else "—"),
            ("Должность:", employee[5] or "—"),
            ("Отдел:", employee[6] or "—"),
            ("Телефон:", employee[7] or "—"),
            ("Email:", employee[8] or "—"),
            ("Дата приема:", str(employee[9]) if employee[9] else "—"),
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
            vacation_table.setItem(row, 0, QTableWidgetItem(str(vac[2])))
            vacation_table.setItem(row, 1, QTableWidgetItem(str(vac[3])))
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
    
    def show_statistics(self):
        """Показ статистики"""
        try:
            stats = self.db.get_statistics()
            
            stats_dialog = QDialog(self)
            stats_dialog.setWindowTitle("Статистика")
            stats_dialog.setMinimumSize(500, 400)
            
            layout = QVBoxLayout()
            
            # Общая статистика
            general_group = QGroupBox("Общая статистика")
            general_layout = QFormLayout()
            
            general_layout.addRow("Всего сотрудников:", QLabel(str(stats['total'])))
            general_layout.addRow("Активных:", QLabel(str(stats['active'])))
            general_layout.addRow("В отпуске:", QLabel(str(stats['on_vacation'])))
            general_layout.addRow("Уволенных:", QLabel(str(stats['fired'])))
            
            general_group.setLayout(general_layout)
            layout.addWidget(general_group)
            
            # Статистика по отделам
            if stats['by_department']:
                dept_group = QGroupBox("Статистика по отделам")
                dept_layout = QVBoxLayout()
                
                dept_table = QTableWidget()
                dept_table.setColumnCount(2)
                dept_table.setHorizontalHeaderLabels(["Отдел", "Количество сотрудников"])
                
                dept_table.setRowCount(len(stats['by_department']))
                for i, dept in enumerate(stats['by_department']):
                    dept_table.setItem(i, 0, QTableWidgetItem(dept['department']))
                    dept_table.setItem(i, 1, QTableWidgetItem(str(dept['count'])))
                
                dept_table.horizontalHeader().setStretchLastSection(True)
                dept_layout.addWidget(dept_table)
                dept_group.setLayout(dept_layout)
                layout.addWidget(dept_group)
            
            # Кнопка закрытия
            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(stats_dialog.accept)
            layout.addWidget(close_btn)
            
            stats_dialog.setLayout(layout)
            stats_dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить статистику:\n{str(e)}")
    
    def closeEvent(self, event):
        """Закрытие соединения с БД при закрытии приложения"""
        self.db.close_connection()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Показываем диалог настроек подключения
    conn_dialog = ConnectionDialog()
    
    if conn_dialog.exec() == QDialog.Accepted:
        params = conn_dialog.get_connection_params()
        
        try:
            db = Database(**params)
            window = HRApp(db)
            window.show()
            sys.exit(app.exec())
        except Exception as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось подключиться к базе данных:\n{str(e)}")
            sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
