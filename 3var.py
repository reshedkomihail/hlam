import sys
import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QDialog, QFormLayout, QDateEdit, QComboBox, QMessageBox,
    QGroupBox, QHeaderView, QTabWidget
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor


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
        self.add_test_data()
    
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
    
    def add_test_data(self):
        """Добавление тестовых данных"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM employees")
            count = cursor.fetchone()[0]
            
            if count == 0:
                test_employees = [
                    ("Иванов", "Иван", "Иванович", "1990-05-15", "Разработчик", "IT-отдел", 
                     "+7 (999) 123-45-67", "ivanov@company.ru", "2020-01-10", 50000, "active"),
                    ("Петрова", "Мария", "Сергеевна", "1988-03-22", "HR-менеджер", "Отдел кадров", 
                     "+7 (999) 234-56-78", "petrova@company.ru", "2019-06-15", 45000, "active"),
                    ("Сидоров", "Алексей", "Викторович", "1985-11-10", "Системный администратор", "IT-отдел", 
                     "+7 (999) 345-67-89", "sidorov@company.ru", "2018-03-20", 48000, "on_vacation"),
                    ("Козлова", "Елена", "Андреевна", "1992-07-18", "Бухгалтер", "Бухгалтерия", 
                     "+7 (999) 456-78-90", "kozlova@company.ru", "2021-02-01", 47000, "active"),
                    ("Смирнов", "Дмитрий", "Павлович", "1987-09-25", "Тестировщик", "IT-отдел", 
                     "+7 (999) 567-89-01", "smirnov@company.ru", "2019-11-15", 42000, "sick_leave"),
                ]
                
                for emp in test_employees:
                    cursor.execute('''
                        INSERT INTO employees (
                            last_name, first_name, patronymic, birth_date, position,
                            department, phone, email, hire_date, salary, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', emp)
                
                departments = [
                    ("IT-отдел", "Информационные технологии", 1),
                    ("Отдел кадров", "Управление персоналом", 2),
                    ("Бухгалтерия", "Финансовый учет", 4),
                    ("Отдел продаж", "Продажи и маркетинг", None),
                ]
                
                for dept in departments:
                    cursor.execute('''
                        INSERT INTO departments (name, description, head_id)
                        VALUES (%s, %s, %s)
                    ''', dept)
                
                self.connection.commit()
                
        except Error as e:
            print(f"Ошибка добавления данных: {e}")
            self.connection.rollback()
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
    
    def get_employees(self, search=None):
        """Получение списка сотрудников"""
        cursor = self.connection.cursor()
        
        if search:
            query = """
                SELECT * FROM employees 
                WHERE last_name LIKE %s OR first_name LIKE %s OR position LIKE %s
                ORDER BY last_name, first_name
            """
            search_term = f"%{search}%"
            cursor.execute(query, (search_term, search_term, search_term))
        else:
            cursor.execute("SELECT * FROM employees ORDER BY last_name, first_name")
        
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
        cursor.execute("SELECT name FROM departments ORDER BY name")
        departments = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return departments
    
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
    
    def close(self):
        """Закрытие соединения"""
        if self.connection and self.connection.is_connected():
            self.connection.close()


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
        self.department_combo.setEditable(True)
        
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.hire_date = QDateEdit()
        self.hire_date.setCalendarPopup(True)
        self.hire_date.setDate(QDate.currentDate())
        
        self.salary_edit = QLineEdit()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Активен", "В отпуске", "На больничном", "Уволен"])
        
        form_layout.addRow("Фамилия:*", self.last_name_edit)
        form_layout.addRow("Имя:*", self.first_name_edit)
        form_layout.addRow("Отчество:", self.patronymic_edit)
        form_layout.addRow("Дата рождения:", self.birth_date)
        form_layout.addRow("Должность:*", self.position_edit)
        form_layout.addRow("Отдел:", self.department_combo)
        form_layout.addRow("Телефон:", self.phone_edit)
        form_layout.addRow("Email:", self.email_edit)
        form_layout.addRow("Дата приема:", self.hire_date)
        form_layout.addRow("Зарплата (руб.):", self.salary_edit)
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
        self.load_departments()
    
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
        """Сохранение сотрудника"""
        if not self.last_name_edit.text() or not self.first_name_edit.text():
            QMessageBox.warning(self, "Ошибка", "Фамилия и имя обязательны!")
            return
        
        status_map = {
            "Активен": "active",
            "В отпуске": "on_vacation",
            "На больничном": "sick_leave",
            "Уволен": "fired"
        }
        
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
            status_map.get(self.status_combo.currentText(), "active")
        )
        
        try:
            if self.employee_id:
                self.db.update_employee(self.employee_id, data)
                QMessageBox.information(self, "Успех", "Данные обновлены!")
            else:
                self.db.add_employee(data)
                QMessageBox.information(self, "Успех", "Сотрудник добавлен!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка: {str(e)}")


class VacationDialog(QDialog):
    """Диалог добавления отпуска"""
    
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = parent.db if parent else None
        self.setWindowTitle("Добавление отпуска")
        self.setModal(True)
        self.setFixedSize(400, 200)
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
            QMessageBox.critical(self, "Ошибка", f"Ошибка: {str(e)}")


class HRApp(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_employees()
    
    def init_ui(self):
        self.setWindowTitle("Система кадрового учета")
        self.setGeometry(100, 100, 1300, 700)
        
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
        
        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск...")
        self.search_edit.textChanged.connect(self.search_employees)
        
        top_panel.addWidget(self.add_btn)
        top_panel.addWidget(self.edit_btn)
        top_panel.addWidget(self.delete_btn)
        top_panel.addWidget(self.vacation_btn)
        top_panel.addWidget(self.refresh_btn)
        top_panel.addWidget(self.stats_btn)
        top_panel.addStretch()
        top_panel.addWidget(QLabel("🔍:"))
        top_panel.addWidget(self.search_edit)
        
        main_layout.addLayout(top_panel)
        
        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Фамилия", "Имя", "Должность", "Отдел", "Телефон", "Email", "Дата приема", "Статус"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.view_details)
        
        main_layout.addWidget(self.table)
        
        # Нижняя панель
        info_panel = QHBoxLayout()
        self.status_label = QLabel("Готов")
        info_panel.addWidget(self.status_label)
        info_panel.addStretch()
        main_layout.addLayout(info_panel)
        
        self.update_status_stats()
    
    def load_employees(self):
        """Загрузка сотрудников"""
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
                self.table.setItem(row, 3, QTableWidgetItem(emp[5] or ""))
                self.table.setItem(row, 4, QTableWidgetItem(emp[6] or ""))
                self.table.setItem(row, 5, QTableWidgetItem(emp[7] or ""))
                self.table.setItem(row, 6, QTableWidgetItem(emp[8] or ""))
                self.table.setItem(row, 7, QTableWidgetItem(str(emp[9]) if emp[9] else ""))
                
                status_text = status_translation.get(emp[11], emp[11])
                status_item = QTableWidgetItem(status_text)
                
                # Цвет статуса
                if emp[11] == "fired":
                    status_item.setForeground(QColor(255, 0, 0))
                elif emp[11] == "on_vacation":
                    status_item.setForeground(QColor(0, 0, 255))
                elif emp[11] == "sick_leave":
                    status_item.setForeground(QColor(255, 140, 0))
                elif emp[11] == "active":
                    status_item.setForeground(QColor(0, 128, 0))
                
                self.table.setItem(row, 8, status_item)
            
            self.table.resizeColumnsToContents()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки: {str(e)}")
    
    def search_employees(self):
        """Поиск сотрудников"""
        search_text = self.search_edit.text()
        try:
            employees = self.db.get_employees(search_text if search_text else None)
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
                self.table.setItem(row, 3, QTableWidgetItem(emp[5] or ""))
                self.table.setItem(row, 4, QTableWidgetItem(emp[6] or ""))
                self.table.setItem(row, 5, QTableWidgetItem(emp[7] or ""))
                self.table.setItem(row, 6, QTableWidgetItem(emp[8] or ""))
                self.table.setItem(row, 7, QTableWidgetItem(str(emp[9]) if emp[9] else ""))
                
                status_text = status_translation.get(emp[11], emp[11])
                self.table.setItem(row, 8, QTableWidgetItem(status_text))
        except Exception as e:
            pass
    
    def add_employee(self):
        dialog = EmployeeDialog(self)
        if dialog.exec():
            self.load_employees()
            self.update_status_stats()
    
    def edit_employee(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника!")
            return
        employee_id = int(self.table.item(row, 0).text())
        dialog = EmployeeDialog(self, employee_id)
        if dialog.exec():
            self.load_employees()
            self.update_status_stats()
    
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
                self.update_status_stats()
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
            self.update_status_stats()
    
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
        
        info = [
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
            self.status_label.setText(
                f" Всего: {stats['total']} | "
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
    
    try:
        db = Database()
        window = HRApp(db)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"Не удалось запустить приложение:\n{str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
