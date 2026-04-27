import sys
import os
import re
import csv
from datetime import datetime, date
from io import StringIO

import mysql.connector
from mysql.connector import Error
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QDialog, QFormLayout, QDateEdit, QComboBox, QMessageBox,
    QGroupBox, QHeaderView, QTabWidget, QToolTip, QMenu,
    QFileDialog, QCheckBox, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QDate, QRegularExpression, QSortFilterProxyModel, QStringListModel
from PySide6.QtGui import QColor, QRegularExpressionValidator, QPalette, QAction, QBrush


class Database:
    """Класс для работы с MySQL базой данных"""
    
    def __init__(self):
        # Параметры подключения из переменных окружения или значения по умолчанию
        self.host = os.getenv('MYSQL_HOST', '127.0.0.1')
        self.user = os.getenv('MYSQL_USER', 'root')
        self.password = os.getenv('MYSQL_PASSWORD', '12345')
        self.database = os.getenv('MYSQL_DATABASE', 'hr')
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
            print(f"Ошибка подключения: {e}")
            sys.exit(1)
    
    def create_database_if_not_exists(self):
        """Создание базы данных если она не существует"""
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            cursor.execute(f"USE {self.database}")
            self.connection.database = self.database
        except Error as e:
            print(f"Ошибка создания БД: {e}")
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            ''')
            
            # Таблица отделов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS departments (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT,
                    head_id INT
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            ''')
            
            # Таблица отпусков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vacations (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    employee_id INT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    type VARCHAR(50),
                    status ENUM('pending', 'approved', 'rejected') DEFAULT 'approved',
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            ''')
            
            self.connection.commit()
            
        except Error as e:
            print(f"Ошибка создания таблиц: {e}")
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
            return cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def get_employees(self, filters=None):
        """Получение списка сотрудников с фильтрацией"""
        cursor = self.connection.cursor()
        
        query = "SELECT * FROM employees WHERE 1=1"
        params = []
        
        if filters:
            # Фильтр по поисковому запросу
            if filters.get('search'):
                query += " AND (last_name LIKE %s OR first_name LIKE %s OR position LIKE %s)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term, search_term])
            
            # Фильтр по статусу
            if filters.get('status'):
                query += " AND status = %s"
                params.append(filters['status'])
            
            # Фильтр по отделу
            if filters.get('department'):
                query += " AND department = %s"
                params.append(filters['department'])
            
            # Фильтр по должности
            if filters.get('position'):
                query += " AND position LIKE %s"
                params.append(f"%{filters['position']}%")
            
            # Фильтр по дате приема (от)
            if filters.get('hire_date_from'):
                query += " AND hire_date >= %s"
                params.append(filters['hire_date_from'])
            
            # Фильтр по дате приема (до)
            if filters.get('hire_date_to'):
                query += " AND hire_date <= %s"
                params.append(filters['hire_date_to'])
            
            # Фильтр по зарплате (от)
            if filters.get('salary_from') is not None:
                query += " AND salary >= %s"
                params.append(filters['salary_from'])
            
            # Фильтр по зарплате (до)
            if filters.get('salary_to') is not None:
                query += " AND salary <= %s"
                params.append(filters['salary_to'])
            
            # Фильтр по возрасту (от)
            if filters.get('age_from') is not None:
                query += " AND TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) >= %s"
                params.append(filters['age_from'])
            
            # Фильтр по возрасту (до)
            if filters.get('age_to') is not None:
                query += " AND TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) <= %s"
                params.append(filters['age_to'])
        
        query += " ORDER BY last_name, first_name"
        
        cursor.execute(query, params)
        employees = cursor.fetchall()
        cursor.close()
        return employees
    
    def get_employee_by_id(self, employee_id):
        """Получение данных сотрудника по ID"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        cursor.close()
        return employee
    
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
        cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL ORDER BY department")
        departments = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return departments
    
    def get_positions(self):
        """Получение списка должностей"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT DISTINCT position FROM employees WHERE position IS NOT NULL ORDER BY position")
        positions = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return positions
    
    def add_vacation(self, employee_id, start_date, end_date, vacation_type):
        """Добавление отпуска"""
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO vacations (employee_id, start_date, end_date, type, status)
                VALUES (%s, %s, %s, %s, 'approved')
            ''', (employee_id, start_date, end_date, vacation_type))
            self.connection.commit()
            
            # Обновляем статус сотрудника
            cursor.execute('''
                UPDATE employees SET status = 'on_vacation' WHERE id = %s
            ''', (employee_id,))
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
        """Получение статистики"""
        cursor = self.connection.cursor()
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM employees")
        stats['total'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'active'")
        stats['active'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'on_vacation'")
        stats['on_vacation'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'sick_leave'")
        stats['sick_leave'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'fired'")
        stats['fired'] = cursor.fetchone()[0]
        
        cursor.close()
        return stats
    
    def export_to_csv(self, filters=None):
        """Экспорт данных в CSV"""
        employees = self.get_employees(filters)
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Заголовки
        writer.writerow(['ID', 'Фамилия', 'Имя', 'Отчество', 'Дата рождения', 
                         'Должность', 'Отдел', 'Телефон', 'Email', 'Дата приема', 
                         'Зарплата', 'Статус'])
        
        # Данные
        status_map = {
            'active': 'Активен',
            'on_vacation': 'В отпуске',
            'sick_leave': 'На больничном',
            'fired': 'Уволен'
        }
        
        for emp in employees:
            writer.writerow([
                emp[0], emp[1], emp[2], emp[3] or '', emp[4] or '',
                emp[5] or '', emp[6] or '', emp[7] or '', emp[8] or '',
                emp[9] or '', emp[10] or '', status_map.get(emp[11], emp[11])
            ])
        
        return output.getvalue()
    
    def close(self):
        """Закрытие соединения"""
        if self.connection and self.connection.is_connected():
            self.connection.close()


class Validators:
    """Класс с методами валидации"""
    
    @staticmethod
    def validate_name(name, field_name):
        """Проверка имени/фамилии/отчества"""
        if not name or len(name.strip()) < 2:
            return False, f"{field_name} должно содержать минимум 2 символа"
        
        # Проверка на буквы, дефис, пробел и апостроф
        if not re.match(r'^[а-яёА-ЯЁa-zA-Z\-\'\s]+$', name):
            return False, f"{field_name} может содержать только буквы, дефис, апостроф и пробел"
        
        return True, ""
    
    @staticmethod
    def validate_birth_date(birth_date):
        """Проверка даты рождения"""
        today = date.today()
        birth = birth_date.toPython()
        
        if birth > today:
            return False, "Дата рождения не может быть в будущем"
        
        # Проверка возраста (не старше 100 лет)
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if age > 100:
            return False, "Возраст не может быть больше 100 лет"
        
        # Минимальный возраст 16 лет
        if age < 16:
            return False, "Сотрудник должен быть не младше 16 лет"
        
        return True, ""
    
    @staticmethod
    def validate_hire_date(hire_date, birth_date):
        """Проверка даты приема на работу"""
        today = date.today()
        hire = hire_date.toPython()
        birth = birth_date.toPython()
        
        if hire > today:
            return False, "Дата приема не может быть в будущем"
        
        # Проверка, что сотруднику было минимум 16 лет на момент приема
        age_at_hire = hire.year - birth.year - ((hire.month, hire.day) < (birth.month, birth.day))
        if age_at_hire < 16:
            return False, "На момент приема сотруднику должно быть минимум 16 лет"
        
        # Проверка на разумную дату (не раньше 1990 года)
        if hire.year < 1990:
            return False, "Дата приема не может быть раньше 1990 года"
        
        return True, ""
    
    @staticmethod
    def validate_salary(salary_text):
        """Проверка зарплаты"""
        if not salary_text.strip():
            return False, "Зарплата не может быть пустой"
        
        try:
            salary = float(salary_text.replace(',', '.'))
        except ValueError:
            return False, "Зарплата должна быть числом"
        
        if salary <= 0:
            return False, "Зарплата должна быть положительным числом"
        
        if salary < 16000:
            return False, "Зарплата не может быть меньше 16 000 ₽"
        
        if salary > 10000000:
            return False, "Зарплата не может быть больше 10 000 000 ₽"
        
        return True, ""
    
    @staticmethod
    def validate_email(email):
        """Проверка email"""
        if not email.strip():
            return True, ""  # Email не обязателен
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False, "Некорректный формат email"
        
        return True, ""
    
    @staticmethod
    def validate_phone(phone):
        """Проверка телефона"""
        if not phone.strip():
            return True, ""  # Телефон не обязателен
        
        # Убираем все нецифровые символы
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) < 6:
            return False, "Номер телефона слишком короткий (минимум 6 цифр)"
        
        if len(digits) > 15:
            return False, "Номер телефона слишком длинный (максимум 15 цифр)"
        
        return True, ""
    
    @staticmethod
    def validate_vacation_dates(start_date, end_date):
        """Проверка дат отпуска"""
        start = start_date.toPython()
        end = end_date.toPython()
        
        if start > end:
            return False, "Дата окончания не может быть раньше даты начала"
        
        # Проверка минимальной продолжительности (1 день)
        if start == end:
            return False, "Отпуск должен быть минимум 1 день"
        
        return True, ""
    
    @staticmethod
    def format_name(name):
        """Форматирование имени (первая буква заглавная)"""
        if name:
            return name.strip().title()
        return name


class ValidationResult:
    """Класс для хранения результатов валидации"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def add_error(self, message):
        self.errors.append(message)
    
    def add_warning(self, message):
        self.warnings.append(message)
    
    def is_valid(self):
        return len(self.errors) == 0
    
    def get_all_messages(self):
        return self.errors + [f"Предупреждение: {w}" for w in self.warnings]


class FilterWidget(QWidget):
    """Виджет для фильтрации сотрудников"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.is_visible = False
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Основная группа фильтров
        self.filter_group = QGroupBox("Фильтры")
        self.filter_group.setVisible(False)
        filter_layout = QVBoxLayout()
        
        # Первая строка фильтров
        row1_layout = QHBoxLayout()
        
        # Статус
        row1_layout.addWidget(QLabel("Статус:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все статусы", None)
        self.status_filter.addItem("Активен", "active")
        self.status_filter.addItem("В отпуске", "on_vacation")
        self.status_filter.addItem("На больничном", "sick_leave")
        self.status_filter.addItem("Уволен", "fired")
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        row1_layout.addWidget(self.status_filter)
        
        # Отдел
        row1_layout.addWidget(QLabel("Отдел:"))
        self.department_filter = QComboBox()
        self.department_filter.addItem("Все отделы", None)
        self.department_filter.currentIndexChanged.connect(self.apply_filters)
        row1_layout.addWidget(self.department_filter)
        
        filter_layout.addLayout(row1_layout)
        
        # Вторая строка фильтров
        row2_layout = QHBoxLayout()
        
        # Должность
        row2_layout.addWidget(QLabel("Должность:"))
        self.position_filter = QComboBox()
        self.position_filter.setEditable(True)
        self.position_filter.addItem("Все должности", None)
        self.position_filter.lineEdit().setPlaceholderText("Поиск должности...")
        self.position_filter.currentIndexChanged.connect(self.apply_filters)
        row2_layout.addWidget(self.position_filter)
        
        # Поиск
        row2_layout.addWidget(QLabel("Поиск:"))
        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("Фамилия, имя, должность...")
        self.search_filter.textChanged.connect(self.apply_filters)
        row2_layout.addWidget(self.search_filter)
        
        filter_layout.addLayout(row2_layout)
        
        # Третья строка фильтров
        row3_layout = QHBoxLayout()
        
        # Дата приема от
        row3_layout.addWidget(QLabel("Дата приема от:"))
        self.hire_date_from = QDateEdit()
        self.hire_date_from.setCalendarPopup(True)
        self.hire_date_from.setDate(QDate(1990, 1, 1))
        self.hire_date_from.setSpecialValueText("Не выбрано")
        self.hire_date_from.dateChanged.connect(self.apply_filters)
        row3_layout.addWidget(self.hire_date_from)
        
        # Дата приема до
        row3_layout.addWidget(QLabel("до:"))
        self.hire_date_to = QDateEdit()
        self.hire_date_to.setCalendarPopup(True)
        self.hire_date_to.setDate(QDate.currentDate())
        self.hire_date_to.setSpecialValueText("Не выбрано")
        self.hire_date_to.dateChanged.connect(self.apply_filters)
        row3_layout.addWidget(self.hire_date_to)
        
        filter_layout.addLayout(row3_layout)
        
        # Четвертая строка фильтров
        row4_layout = QHBoxLayout()
        
        # Зарплата от
        row4_layout.addWidget(QLabel("Зарплата от:"))
        self.salary_from = QDoubleSpinBox()
        self.salary_from.setRange(0, 10000000)
        self.salary_from.setPrefix("₽ ")
        self.salary_from.setSpecialValueText("Не выбрано")
        self.salary_from.valueChanged.connect(self.apply_filters)
        row4_layout.addWidget(self.salary_from)
        
        # Зарплата до
        row4_layout.addWidget(QLabel("до:"))
        self.salary_to = QDoubleSpinBox()
        self.salary_to.setRange(0, 10000000)
        self.salary_to.setPrefix("₽ ")
        self.salary_to.setSpecialValueText("Не выбрано")
        self.salary_to.valueChanged.connect(self.apply_filters)
        row4_layout.addWidget(self.salary_to)
        
        filter_layout.addLayout(row4_layout)
        
        # Пятая строка фильтров
        row5_layout = QHBoxLayout()
        
        # Возраст от
        row5_layout.addWidget(QLabel("Возраст от:"))
        self.age_from = QSpinBox()
        self.age_from.setRange(0, 100)
        self.age_from.setSpecialValueText("Не выбрано")
        self.age_from.valueChanged.connect(self.apply_filters)
        row5_layout.addWidget(self.age_from)
        
        # Возраст до
        row5_layout.addWidget(QLabel("до:"))
        self.age_to = QSpinBox()
        self.age_to.setRange(0, 100)
        self.age_to.setSpecialValueText("Не выбрано")
        self.age_to.valueChanged.connect(self.apply_filters)
        row5_layout.addWidget(self.age_to)
        
        filter_layout.addLayout(row5_layout)
        
        # Кнопки управления фильтрами
        buttons_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("Применить фильтры")
        self.apply_btn.clicked.connect(self.apply_filters)
        
        self.clear_btn = QPushButton("Сбросить фильтры")
        self.clear_btn.clicked.connect(self.clear_filters)
        
        self.export_btn = QPushButton("Экспорт в CSV")
        self.export_btn.clicked.connect(self.export_to_csv)
        
        buttons_layout.addWidget(self.apply_btn)
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addWidget(self.export_btn)
        buttons_layout.addStretch()
        
        filter_layout.addLayout(buttons_layout)
        self.filter_group.setLayout(filter_layout)
        main_layout.addWidget(self.filter_group)
        
        self.setLayout(main_layout)
    
    def load_departments(self):
        """Загрузка списка отделов"""
        if self.main_window and self.main_window.db:
            self.department_filter.clear()
            self.department_filter.addItem("Все отделы", None)
            departments = self.main_window.db.get_departments()
            for dept in departments:
                if dept:  # Пропускаем пустые значения
                    self.department_filter.addItem(dept, dept)
    
    def load_positions(self):
        """Загрузка списка должностей"""
        if self.main_window and self.main_window.db:
            self.position_filter.clear()
            self.position_filter.addItem("Все должности", None)
            positions = self.main_window.db.get_positions()
            for pos in positions:
                if pos:  # Пропускаем пустые значения
                    self.position_filter.addItem(pos, pos)
    
    def toggle_visibility(self):
        """Переключение видимости фильтров"""
        self.is_visible = not self.is_visible
        self.filter_group.setVisible(self.is_visible)
        return self.is_visible
    
    def get_filters(self):
        """Получение текущих фильтров"""
        filters = {}
        
        # Статус
        status = self.status_filter.currentData()
        if status:
            filters['status'] = status
        
        # Отдел
        department = self.department_filter.currentData()
        if department:
            filters['department'] = department
        
        # Должность
        position = self.position_filter.currentData()
        if position:
            filters['position'] = position
        
        # Поиск
        search = self.search_filter.text().strip()
        if search:
            filters['search'] = search
        
        # Даты приема
        if self.hire_date_from.date() != QDate(1990, 1, 1):
            filters['hire_date_from'] = self.hire_date_from.date().toString("yyyy-MM-dd")
        
        if self.hire_date_to.date() != QDate.currentDate():
            filters['hire_date_to'] = self.hire_date_to.date().toString("yyyy-MM-dd")
        
        # Зарплата
        if self.salary_from.value() > 0:
            filters['salary_from'] = self.salary_from.value()
        
        if self.salary_to.value() > 0:
            filters['salary_to'] = self.salary_to.value()
        
        # Возраст
        if self.age_from.value() > 0:
            filters['age_from'] = self.age_from.value()
        
        if self.age_to.value() > 0:
            filters['age_to'] = self.age_to.value()
        
        return filters
    
    def apply_filters(self):
        """Применение фильтров"""
        if self.main_window:
            self.main_window.load_employees()
    
    def clear_filters(self):
        """Сброс всех фильтров"""
        self.status_filter.setCurrentIndex(0)
        self.department_filter.setCurrentIndex(0)
        self.position_filter.setCurrentIndex(0)
        self.search_filter.clear()
        self.hire_date_from.setDate(QDate(1990, 1, 1))
        self.hire_date_to.setDate(QDate.currentDate())
        self.salary_from.setValue(0)
        self.salary_to.setValue(0)
        self.age_from.setValue(0)
        self.age_to.setValue(0)
        
        self.apply_filters()
    
    def export_to_csv(self):
        """Экспорт данных в CSV"""
        if not self.main_window:
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в CSV", "employees.csv", 
            "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_name:
            try:
                filters = self.get_filters()
                csv_data = self.main_window.db.export_to_csv(filters)
                
                with open(file_name, 'w', encoding='utf-8-sig') as f:
                    f.write(csv_data)
                
                QMessageBox.information(self, "Успех", f"Данные экспортированы в {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {str(e)}")


class EmployeeDialog(QDialog):
    """Диалог добавления/редактирования сотрудника"""
    
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = parent.db if parent else None
        self.setWindowTitle("Добавление сотрудника" if not employee_id else "Редактирование сотрудника")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QLineEdit.error {
                border: 2px solid red;
                background-color: #FFE6E6;
            }
            QLineEdit.warning {
                border: 2px solid orange;
                background-color: #FFF3E6;
            }
        """)
        self.init_ui()
        self.setup_validators()
        
        if employee_id:
            self.load_employee_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Личные данные
        self.last_name_edit = QLineEdit()
        self.last_name_edit.setPlaceholderText("Обязательно")
        self.last_name_edit.textChanged.connect(lambda: self.validate_field('last_name'))
        
        self.first_name_edit = QLineEdit()
        self.first_name_edit.setPlaceholderText("Обязательно")
        self.first_name_edit.textChanged.connect(lambda: self.validate_field('first_name'))
        
        self.patronymic_edit = QLineEdit()
        self.patronymic_edit.setPlaceholderText("Не обязательно")
        self.patronymic_edit.textChanged.connect(lambda: self.validate_field('patronymic'))
        
        self.birth_date = QDateEdit()
        self.birth_date.setCalendarPopup(True)
        self.birth_date.setDate(QDate.currentDate().addYears(-30))
        self.birth_date.dateChanged.connect(lambda: self.validate_field('birth_date'))
        
        # Рабочая информация
        self.position_edit = QLineEdit()
        self.position_edit.setPlaceholderText("Обязательно")
        
        self.department_combo = QComboBox()
        self.department_combo.setEditable(True)
        
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("+7(999)123-45-67")
        self.phone_edit.textChanged.connect(lambda: self.validate_field('phone'))
        
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("example@mail.com")
        self.email_edit.textChanged.connect(lambda: self.validate_field('email'))
        
        self.hire_date = QDateEdit()
        self.hire_date.setCalendarPopup(True)
        self.hire_date.setDate(QDate.currentDate())
        self.hire_date.dateChanged.connect(lambda: self.validate_field('hire_date'))
        
        self.salary_edit = QLineEdit()
        self.salary_edit.setPlaceholderText("от 16 000 до 10 000 000")
        self.salary_edit.textChanged.connect(lambda: self.validate_field('salary'))
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Активен", "В отпуске", "На больничном", "Уволен"])
        
        # Создаем метки для отображения ошибок
        self.error_labels = {}
        fields = [
            ("Фамилия:*", self.last_name_edit, 'last_name'),
            ("Имя:*", self.first_name_edit, 'first_name'),
            ("Отчество:", self.patronymic_edit, 'patronymic'),
            ("Дата рождения:*", self.birth_date, 'birth_date'),
            ("Должность:*", self.position_edit, 'position'),
            ("Отдел:", self.department_combo, 'department'),
            ("Телефон:", self.phone_edit, 'phone'),
            ("Email:", self.email_edit, 'email'),
            ("Дата приема:*", self.hire_date, 'hire_date'),
            ("Зарплата (руб.):*", self.salary_edit, 'salary'),
            ("Статус:", self.status_combo, 'status')
        ]
        
        for label_text, widget, field_name in fields:
            form_layout.addRow(label_text, widget)
            
            # Добавляем метку для ошибок
            error_label = QLabel("")
            error_label.setStyleSheet("color: red; font-size: 10px;")
            error_label.setVisible(False)
            self.error_labels[field_name] = error_label
            form_layout.addRow("", error_label)
        
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
        self.load_departments()
    
    def setup_validators(self):
        """Настройка валидаторов для полей ввода"""
        # Валидатор для имени (только буквы, дефис, апостроф)
        name_regex = QRegularExpression(r'^[а-яёА-ЯЁa-zA-Z\-\'\s]*$')
        name_validator = QRegularExpressionValidator(name_regex)
        
        self.last_name_edit.setValidator(name_validator)
        self.first_name_edit.setValidator(name_validator)
        self.patronymic_edit.setValidator(name_validator)
        
        # Валидатор для зарплаты (только цифры и точка)
        salary_regex = QRegularExpression(r'^\d*\.?\d*$')
        salary_validator = QRegularExpressionValidator(salary_regex)
        self.salary_edit.setValidator(salary_validator)
    
    def validate_field(self, field_name):
        """Валидация отдельного поля"""
        error_label = self.error_labels.get(field_name)
        if not error_label:
            return True
        
        widget = None
        if field_name == 'last_name':
            widget = self.last_name_edit
        elif field_name == 'first_name':
            widget = self.first_name_edit
        elif field_name == 'patronymic':
            widget = self.patronymic_edit
        elif field_name == 'birth_date':
            widget = self.birth_date
        elif field_name == 'hire_date':
            widget = self.hire_date
        elif field_name == 'phone':
            widget = self.phone_edit
        elif field_name == 'email':
            widget = self.email_edit
        elif field_name == 'salary':
            widget = self.salary_edit
        
        if not widget:
            return True
        
        # Очищаем предыдущую ошибку
        error_label.setVisible(False)
        error_label.setText("")
        widget.setProperty("class", "")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        
        validation_result = ValidationResult()
        
        # Проверяем поле
        if field_name in ['last_name', 'first_name']:
            if widget.text().strip():
                is_valid, message = Validators.validate_name(widget.text(), 
                    "Фамилия" if field_name == 'last_name' else "Имя")
                if not is_valid:
                    validation_result.add_error(message)
        
        elif field_name == 'patronymic':
            if widget.text().strip():
                is_valid, message = Validators.validate_name(widget.text(), "Отчество")
                if not is_valid:
                    validation_result.add_warning(message)
        
        elif field_name == 'birth_date':
            is_valid, message = Validators.validate_birth_date(widget.date())
            if not is_valid:
                validation_result.add_error(message)
        
        elif field_name == 'hire_date':
            is_valid, message = Validators.validate_hire_date(
                widget.date(), self.birth_date.date())
            if not is_valid:
                validation_result.add_error(message)
        
        elif field_name == 'phone':
            is_valid, message = Validators.validate_phone(widget.text())
            if not is_valid:
                validation_result.add_warning(message)
        
        elif field_name == 'email':
            is_valid, message = Validators.validate_email(widget.text())
            if not is_valid:
                validation_result.add_error(message)
        
        elif field_name == 'salary':
            is_valid, message = Validators.validate_salary(widget.text())
            if not is_valid:
                validation_result.add_error(message)
        
        # Отображаем ошибки
        if not validation_result.is_valid():
            error_label.setText(validation_result.get_all_messages()[0])
            error_label.setVisible(True)
            widget.setProperty("class", "error")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            return False
        
        return True
    
    def load_departments(self):
        """Загрузка отделов"""
        if self.db:
            self.department_combo.clear()
            self.department_combo.addItem("")
            departments = self.db.get_departments()
            self.department_combo.addItems(departments)
    
    def load_employee_data(self):
        """Загрузка данных сотрудника"""
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
            
            index = self.department_combo.findText(employee[6] or "")
            if index >= 0:
                self.department_combo.setCurrentIndex(index)
            
            self.phone_edit.setText(employee[7] or "")
            self.email_edit.setText(employee[8] or "")
            
            if employee[9]:
                date = QDate.fromString(str(employee[9]), "yyyy-MM-dd")
                self.hire_date.setDate(date)
            
            self.salary_edit.setText(str(employee[10]) if employee[10] else "")
            
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
        """Сохранение сотрудника с полной валидацией"""
        # Полная валидация всех полей
        validation_result = ValidationResult()
        
        # Проверка обязательных полей
        if not self.last_name_edit.text().strip():
            validation_result.add_error("Фамилия обязательна")
        else:
            is_valid, message = Validators.validate_name(self.last_name_edit.text(), "Фамилия")
            if not is_valid:
                validation_result.add_error(message)
        
        if not self.first_name_edit.text().strip():
            validation_result.add_error("Имя обязательно")
        else:
            is_valid, message = Validators.validate_name(self.first_name_edit.text(), "Имя")
            if not is_valid:
                validation_result.add_error(message)
        
        # Проверка отчества (если заполнено)
        if self.patronymic_edit.text().strip():
            is_valid, message = Validators.validate_name(self.patronymic_edit.text(), "Отчество")
            if not is_valid:
                validation_result.add_warning(message)
        
        # Проверка даты рождения
        is_valid, message = Validators.validate_birth_date(self.birth_date.date())
        if not is_valid:
            validation_result.add_error(message)
        
        # Проверка должности
        if not self.position_edit.text().strip():
            validation_result.add_error("Должность обязательна")
        
        # Проверка даты приема
        is_valid, message = Validators.validate_hire_date(
            self.hire_date.date(), self.birth_date.date())
        if not is_valid:
            validation_result.add_error(message)
        
        # Проверка зарплаты
        is_valid, message = Validators.validate_salary(self.salary_edit.text())
        if not is_valid:
            validation_result.add_error(message)
        
        # Проверка email
        is_valid, message = Validators.validate_email(self.email_edit.text())
        if not is_valid:
            validation_result.add_error(message)
        
        # Проверка телефона
        is_valid, message = Validators.validate_phone(self.phone_edit.text())
        if not is_valid:
            validation_result.add_warning(message)
        
        # Если есть ошибки, показываем их
        if not validation_result.is_valid():
            error_message = "Ошибки при заполнении формы:\n\n"
            error_message += "\n".join([f"• {err}" for err in validation_result.get_all_messages()])
            QMessageBox.warning(self, "Ошибка валидации", error_message)
            return
        
        # Если есть только предупреждения, спрашиваем подтверждение
        if validation_result.warnings:
            warning_message = "Предупреждения:\n\n"
            warning_message += "\n".join([f"• {w}" for w in validation_result.warnings])
            warning_message += "\n\nПродолжить сохранение?"
            reply = QMessageBox.question(self, "Предупреждения", warning_message,
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        # Сохранение данных
        status_map = {
            "Активен": "active",
            "В отпуске": "on_vacation",
            "На больничном": "sick_leave",
            "Уволен": "fired"
        }
        
        data = (
            Validators.format_name(self.last_name_edit.text()),
            Validators.format_name(self.first_name_edit.text()),
            Validators.format_name(self.patronymic_edit.text()) if self.patronymic_edit.text() else None,
            self.birth_date.date().toString("yyyy-MM-dd"),
            self.position_edit.text().strip() or None,
            self.department_combo.currentText() or None,
            self.phone_edit.text().strip() or None,
            self.email_edit.text().strip().lower() if self.email_edit.text() else None,
            self.hire_date.date().toString("yyyy-MM-dd"),
            float(self.salary_edit.text()) if self.salary_edit.text() else None,
            status_map.get(self.status_combo.currentText(), "active")
        )
        
        try:
            if self.employee_id:
                self.db.update_employee(self.employee_id, data)
                QMessageBox.information(self, "Успех", "Данные сотрудника обновлены!")
            else:
                self.db.add_employee(data)
                QMessageBox.information(self, "Успех", "Новый сотрудник добавлен!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка базы данных", 
                               f"Не удалось сохранить данные:\n{str(e)}")


class VacationDialog(QDialog):
    """Диалог добавления отпуска с валидацией"""
    
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = parent.db if parent else None
        self.setWindowTitle("Добавление отпуска")
        self.setModal(True)
        self.setFixedSize(400, 250)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.dateChanged.connect(self.validate_dates)
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(14))
        self.end_date.dateChanged.connect(self.validate_dates)
        
        self.vacation_type = QComboBox()
        self.vacation_type.addItems(["Ежегодный", "Дополнительный", "Без содержания", "Учебный"])
        
        form_layout.addRow("Дата начала:", self.start_date)
        form_layout.addRow("Дата окончания:", self.end_date)
        form_layout.addRow("Тип отпуска:", self.vacation_type)
        
        # Метка для ошибок
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setVisible(False)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.error_label)
        
        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save_vacation)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def validate_dates(self):
        """Валидация дат отпуска"""
        is_valid, message = Validators.validate_vacation_dates(
            self.start_date.date(), self.end_date.date())
        
        if not is_valid:
            self.error_label.setText(message)
            self.error_label.setVisible(True)
        else:
            self.error_label.setVisible(False)
        
        return is_valid
    
    def save_vacation(self):
        """Сохранение отпуска с валидацией"""
        if not self.validate_dates():
            QMessageBox.warning(self, "Ошибка", self.error_label.text())
            return
        
        # Проверка, что даты не в прошлом
        today = date.today()
        start = self.start_date.date().toPython()
        end = self.end_date.date().toPython()
        
        if start < today and end < today:
            reply = QMessageBox.question(self, "Предупреждение",
                "Все даты отпуска уже прошли. Добавить эту запись?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
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
            QMessageBox.critical(self, "Ошибка", f"Ошибка при добавлении отпуска:\n{str(e)}")


class HRApp(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.filter_visible = False
        self.init_ui()
        self.load_employees()
    
    def init_ui(self):
        self.setWindowTitle("Система кадрового учета")
        self.setGeometry(100, 100, 1400, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Верхняя панель
        top_panel = QHBoxLayout()
        
        self.add_btn = QPushButton(" Добавить")
        self.add_btn.clicked.connect(self.add_employee)
        
        self.edit_btn = QPushButton(" Редактировать")
        self.edit_btn.clicked.connect(self.edit_employee)
        
        self.delete_btn = QPushButton(" Удалить")
        self.delete_btn.clicked.connect(self.delete_employee)
        
        self.vacation_btn = QPushButton(" Отпуск")
        self.vacation_btn.clicked.connect(self.add_vacation)
        
        self.refresh_btn = QPushButton(" Обновить")
        self.refresh_btn.clicked.connect(self.load_employees)
        
        self.stats_btn = QPushButton(" Статистика")
        self.stats_btn.clicked.connect(self.show_statistics)
        
        # Кнопка для показа/скрытия фильтров
        self.filter_toggle_btn = QPushButton("🔍 Фильтры")
        self.filter_toggle_btn.setCheckable(True)
        self.filter_toggle_btn.clicked.connect(self.toggle_filters)
        
        top_panel.addWidget(self.add_btn)
        top_panel.addWidget(self.edit_btn)
        top_panel.addWidget(self.delete_btn)
        top_panel.addWidget(self.vacation_btn)
        top_panel.addWidget(self.refresh_btn)
        top_panel.addWidget(self.stats_btn)
        top_panel.addWidget(self.filter_toggle_btn)
        top_panel.addStretch()
        
        main_layout.addLayout(top_panel)
        
        # Фильтры (скрыты по умолчанию)
        self.filter_widget = FilterWidget(self)
        main_layout.addWidget(self.filter_widget)
        
        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Фамилия", "Имя", "Отчество", "Возраст", 
            "Должность", "Отдел", "Телефон", "Email", 
            "Дата приема", "Статус"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.view_details)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        main_layout.addWidget(self.table)
        
        # Нижняя панель
        info_panel = QHBoxLayout()
        self.status_label = QLabel("Готов")
        info_panel.addWidget(self.status_label)
        info_panel.addStretch()
        main_layout.addLayout(info_panel)
        
        # Загружаем данные для фильтров
        self.filter_widget.load_departments()
        self.filter_widget.load_positions()
        
        self.update_status_stats()
    
    def toggle_filters(self):
        """Переключение видимости панели фильтров"""
        self.filter_visible = self.filter_widget.toggle_visibility()
        
        if self.filter_visible:
            self.filter_toggle_btn.setText("🔍 Скрыть фильтры")
            self.filter_toggle_btn.setChecked(True)
        else:
            self.filter_toggle_btn.setText("🔍 Фильтры")
            self.filter_toggle_btn.setChecked(False)
            # Сбрасываем фильтры при скрытии
            self.filter_widget.clear_filters()
    
    def load_employees(self):
        """Загрузка сотрудников с учетом фильтров"""
        try:
            filters = self.filter_widget.get_filters() if self.filter_visible else None
            employees = self.db.get_employees(filters)
            self.table.setRowCount(len(employees))
            
            status_translation = {
                "active": "Активен",
                "on_vacation": "В отпуске",
                "sick_leave": "На больничном",
                "fired": "Уволен"
            }
            
            today = date.today()
            
            for row, emp in enumerate(employees):
                self.table.setItem(row, 0, QTableWidgetItem(str(emp[0])))
                self.table.setItem(row, 1, QTableWidgetItem(emp[1]))
                self.table.setItem(row, 2, QTableWidgetItem(emp[2]))
                self.table.setItem(row, 3, QTableWidgetItem(emp[3] or ""))
                
                # Расчет возраста
                age = ""
                if emp[4]:
                    birth_date = emp[4]
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    self.table.setItem(row, 4, QTableWidgetItem(str(age)))
                else:
                    self.table.setItem(row, 4, QTableWidgetItem(""))
                
                self.table.setItem(row, 5, QTableWidgetItem(emp[5] or ""))
                self.table.setItem(row, 6, QTableWidgetItem(emp[6] or ""))
                self.table.setItem(row, 7, QTableWidgetItem(emp[7] or ""))
                self.table.setItem(row, 8, QTableWidgetItem(emp[8] or ""))
                self.table.setItem(row, 9, QTableWidgetItem(str(emp[9]) if emp[9] else ""))
                
                status_text = status_translation.get(emp[11], emp[11])
                status_item = QTableWidgetItem(status_text)
                
                # Цветовое кодирование всей строки и статуса
                color_map = {
                    "active": QColor(240, 255, 240),      # Светло-зеленый
                    "on_vacation": QColor(240, 240, 255),  # Светло-синий
                    "sick_leave": QColor(255, 240, 220),   # Светло-оранжевый
                    "fired": QColor(255, 240, 240)         # Светло-красный
                }
                
                text_color_map = {
                    "active": QColor(0, 128, 0),
                    "on_vacation": QColor(0, 0, 255),
                    "sick_leave": QColor(255, 140, 0),
                    "fired": QColor(255, 0, 0)
                }
                
                bg_color = color_map.get(emp[11], QColor(255, 255, 255))
                status_color = text_color_map.get(emp[11], QColor(0, 0, 0))
                
                # # Применяем цвет ко всей строке
                # for col in range(self.table.columnCount()):
                #     item = self.table.item(row, col)
                #     if item:
                #         item.setBackground(QBrush(bg_color))
                
                # Особый цвет для статуса
                status_item.setForeground(status_color)
                status_item.setBackground(QBrush(bg_color))
                self.table.setItem(row, 10, status_item)
            
            self.table.resizeColumnsToContents()
            self.update_status_stats()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки: {str(e)}")
    
    def show_context_menu(self, position):
        """Показ контекстного меню"""
        menu = QMenu()
        
        view_action = QAction("Просмотреть", self)
        view_action.triggered.connect(self.view_details_current)
        
        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(self.edit_employee)
        
        vacation_action = QAction("Добавить отпуск", self)
        vacation_action.triggered.connect(self.add_vacation)
        
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(self.delete_employee)
        
        menu.addAction(view_action)
        menu.addAction(edit_action)
        menu.addAction(vacation_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def view_details_current(self):
        """Просмотр деталей текущего сотрудника"""
        row = self.table.currentRow()
        if row >= 0:
            self.view_details(self.table.model().index(row, 0))
    
    def add_employee(self):
        dialog = EmployeeDialog(self)
        if dialog.exec():
            self.load_employees()
            self.filter_widget.load_departments()
            self.filter_widget.load_positions()
    
    def edit_employee(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника!")
            return
        employee_id = int(self.table.item(row, 0).text())
        dialog = EmployeeDialog(self, employee_id)
        if dialog.exec():
            self.load_employees()
            self.filter_widget.load_departments()
            self.filter_widget.load_positions()
    
    def delete_employee(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника!")
            return
        
        employee_id = int(self.table.item(row, 0).text())
        name = f"{self.table.item(row, 1).text()} {self.table.item(row, 2).text()}"
        
        reply = QMessageBox.question(self, "Удаление", f"Удалить {name}?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_employee(employee_id)
                self.load_employees()
                self.filter_widget.load_departments()
                self.filter_widget.load_positions()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления: {str(e)}")
    
    def add_vacation(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника!")
            return
        employee_id = int(self.table.item(row, 0).text())
        dialog = VacationDialog(self, employee_id)
        if dialog.exec():
            self.load_employees()
    
    def view_details(self, index):
        """Просмотр деталей"""
        row = index.row()
        employee_id = int(self.table.item(row, 0).text())
        employee = self.db.get_employee_by_id(employee_id)
        
        if not employee:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Информация - {employee[1]} {employee[2]}")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        tabs = QTabWidget()
        
        # Основная информация
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        
        # Расчет возраста
        age = ""
        if employee[4]:
            today = date.today()
            birth = employee[4]
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        
        info = [
            ("Фамилия:", employee[1]),
            ("Имя:", employee[2]),
            ("Отчество:", employee[3] or "—"),
            ("Дата рождения:", str(employee[4]) if employee[4] else "—"),
            ("Возраст:", f"{age} лет" if age else "—"),
            ("Должность:", employee[5] or "—"),
            ("Отдел:", employee[6] or "—"),
            ("Телефон:", employee[7] or "—"),
            ("Email:", employee[8] or "—"),
            ("Дата приема:", str(employee[9]) if employee[9] else "—"),
            ("Зарплата:", f"{employee[10]:,.2f} ₽" if employee[10] else "—"),
        ]
        
        for label, value in info:
            lbl = QLabel(label)
            lbl.setStyleSheet("font-weight: bold;")
            basic_layout.addRow(lbl, QLabel(str(value)))
        
        tabs.addTab(basic_tab, "Основная информация")
        
        # Отпуска
        vacation_tab = QWidget()
        vacation_layout = QVBoxLayout(vacation_tab)
        vacation_table = QTableWidget()
        vacation_table.setColumnCount(4)
        vacation_table.setHorizontalHeaderLabels(["Начало", "Окончание", "Тип", "Статус"])
        
        try:
            vacations = self.db.get_employee_vacations(employee_id)
            vacation_table.setRowCount(len(vacations))
            for r, vac in enumerate(vacations):
                vacation_table.setItem(r, 0, QTableWidgetItem(str(vac[2])))
                vacation_table.setItem(r, 1, QTableWidgetItem(str(vac[3])))
                vacation_table.setItem(r, 2, QTableWidgetItem(vac[4]))
                vacation_table.setItem(r, 3, QTableWidgetItem(vac[5]))
        except Exception as e:
            vacation_table.setRowCount(1)
            vacation_table.setItem(0, 0, QTableWidgetItem("Нет данных"))
        
        vacation_layout.addWidget(vacation_table)
        tabs.addTab(vacation_tab, "Отпуска")
        
        layout.addWidget(tabs)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def show_statistics(self):
        """Показ статистики"""
        try:
            stats = self.db.get_statistics()
            dialog = QDialog(self)
            dialog.setWindowTitle("Статистика")
            dialog.setMinimumSize(350, 250)
            
            layout = QVBoxLayout()
            title = QLabel(" Статистика сотрудников")
            title.setStyleSheet("font-size: 16px; font-weight: bold;")
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)
            
            group = QGroupBox()
            form = QFormLayout()
            form.addRow(" Всего:", QLabel(str(stats['total'])))
            form.addRow(" Активных:", QLabel(str(stats['active'])))
            form.addRow(" В отпуске:", QLabel(str(stats['on_vacation'])))
            form.addRow(" На больничном:", QLabel(str(stats['sick_leave'])))
            form.addRow(" Уволенных:", QLabel(str(stats['fired'])))
            group.setLayout(form)
            layout.addWidget(group)
            
            btn = QPushButton("Закрыть")
            btn.clicked.connect(dialog.accept)
            layout.addWidget(btn)
            
            dialog.setLayout(layout)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка: {str(e)}")
    
    def update_status_stats(self):
        """Обновление статуса"""
        try:
            stats = self.db.get_statistics()
            visible_rows = self.table.rowCount()
            
            filter_text = ""
            if self.filter_visible:
                filter_text = " | 🔍 Фильтры активны"
            
            self.status_label.setText(
                f" Отображается: {visible_rows}{filter_text} | "
                f"Всего: {stats['total']} | "
                f"Активны: {stats['active']} | "
                f"В отпуске: {stats['on_vacation']} | "
                f"На больничном: {stats['sick_leave']} | "
                f"Уволены: {stats['fired']}"
            )
        except Exception as e:
            self.status_label.setText("Ошибка статистики")
    
    def closeEvent(self, event):
        self.db.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Установка глобальных стилей
    app.setStyleSheet("""
        QToolTip {
            background-color: #FFF3CD;
            color: #856404;
            border: 1px solid #FFEEBA;
            padding: 4px;
            border-radius: 4px;
        }
        QPushButton#filter_toggle_btn:checked {
            background-color: #0078D7;
            color: white;
            border: 2px solid #005A9E;
        }
    """)
    
    try:
        db = Database()
        window = HRApp(db)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "Критическая ошибка", 
                           f"Не удалось запустить приложение:\n{str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
