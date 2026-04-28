import sys
import os
import re
import csv
import hashlib
import secrets
from datetime import datetime, date, timedelta
from io import StringIO, BytesIO

import mysql.connector
from mysql.connector import Error
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QDialog, QFormLayout, QDateEdit, QComboBox, QMessageBox,
    QGroupBox, QHeaderView, QTabWidget, QToolTip, QMenu,
    QFileDialog, QCheckBox, QSpinBox, QDoubleSpinBox, QStackedWidget,
    QProgressBar, QSplashScreen
)
from PySide6.QtCore import Qt, QDate, QRegularExpression, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QRegularExpressionValidator, QPalette, QAction, QBrush, QFont, QPixmap, QIcon


class Database:
    """Класс для работы с MySQL базой данных"""
    
    def __init__(self):
        self.host = os.getenv('MYSQL_HOST', '127.0.0.1')
        self.user = os.getenv('MYSQL_USER', 'root')
        self.password = os.getenv('MYSQL_PASSWORD', '12345')
        self.database = os.getenv('MYSQL_DATABASE', 'hr')
        self.connection = None
        self.connect()
        self.create_database_if_not_exists()
        self.create_tables()
        self.create_default_admin()
    
    def connect(self):
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
        cursor = self.connection.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role ENUM('admin', 'manager', 'viewer') DEFAULT 'viewer',
                    full_name VARCHAR(100),
                    email VARCHAR(100),
                    is_active BOOLEAN DEFAULT TRUE,
                    last_login TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            ''')
            
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS departments (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT,
                    head_id INT
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            ''')
            
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    user_id INT,
                    action VARCHAR(50),
                    table_name VARCHAR(50),
                    record_id INT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            ''')
            
            self.connection.commit()
            
        except Error as e:
            print(f"Ошибка создания таблиц: {e}")
            sys.exit(1)
        finally:
            cursor.close()
    
    def create_default_admin(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            if cursor.fetchone()[0] == 0:
                password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
                cursor.execute('''
                    INSERT INTO users (username, password_hash, role, full_name)
                    VALUES ('admin', %s, 'admin', 'Администратор системы')
                ''', (password_hash,))
                self.connection.commit()
                print("Создан пользователь по умолчанию: admin / admin123")
        except Error as e:
            print(f"Ошибка создания администратора: {e}")
        finally:
            cursor.close()
    
    def authenticate_user(self, username, password):
        cursor = self.connection.cursor(dictionary=True)
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('''
                SELECT * FROM users 
                WHERE username = %s AND password_hash = %s AND is_active = TRUE
            ''', (username, password_hash))
            user = cursor.fetchone()
            
            if user:
                cursor.execute('''
                    UPDATE users SET last_login = NOW() WHERE id = %s
                ''', (user['id'],))
                self.connection.commit()
                
                self.add_audit_log(user['id'], 'login', 'users', user['id'], 
                                 f"Пользователь {username} вошел в систему")
            
            return user
        except Error as e:
            print(f"Ошибка аутентификации: {e}")
            return None
        finally:
            cursor.close()
    
    def add_audit_log(self, user_id, action, table_name, record_id, description):
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, table_name, record_id, description)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, action, table_name, record_id, description))
            self.connection.commit()
        except Error as e:
            print(f"Ошибка аудита: {e}")
        finally:
            cursor.close()
    
    def add_employee(self, data):
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
        cursor = self.connection.cursor()
        
        query = "SELECT * FROM employees WHERE 1=1"
        params = []
        
        if filters:
            if filters.get('search'):
                query += " AND (last_name LIKE %s OR first_name LIKE %s OR position LIKE %s)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term, search_term])
            
            if filters.get('status'):
                query += " AND status = %s"
                params.append(filters['status'])
            
            if filters.get('department'):
                query += " AND department = %s"
                params.append(filters['department'])
            
            if filters.get('position'):
                query += " AND position LIKE %s"
                params.append(f"%{filters['position']}%")
            
            if filters.get('hire_date_from'):
                query += " AND hire_date >= %s"
                params.append(filters['hire_date_from'])
            
            if filters.get('hire_date_to'):
                query += " AND hire_date <= %s"
                params.append(filters['hire_date_to'])
            
            if filters.get('salary_from') is not None:
                query += " AND salary >= %s"
                params.append(filters['salary_from'])
            
            if filters.get('salary_to') is not None:
                query += " AND salary <= %s"
                params.append(filters['salary_to'])
            
            if filters.get('age_from') is not None:
                query += " AND TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) >= %s"
                params.append(filters['age_from'])
            
            if filters.get('age_to') is not None:
                query += " AND TIMESTAMPDIFF(YEAR, birth_date, CURDATE()) <= %s"
                params.append(filters['age_to'])
        
        query += " ORDER BY last_name, first_name"
        
        cursor.execute(query, params)
        employees = cursor.fetchall()
        cursor.close()
        return employees
    
    def get_employee_by_id(self, employee_id):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        cursor.close()
        return employee
    
    def update_employee(self, employee_id, data):
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
        cursor = self.connection.cursor()
        cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL ORDER BY department")
        departments = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return departments
    
    def get_positions(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT DISTINCT position FROM employees WHERE position IS NOT NULL ORDER BY position")
        positions = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return positions
    
    def add_vacation(self, employee_id, start_date, end_date, vacation_type):
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO vacations (employee_id, start_date, end_date, type, status)
                VALUES (%s, %s, %s, %s, 'approved')
            ''', (employee_id, start_date, end_date, vacation_type))
            self.connection.commit()
            
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
        employees = self.get_employees(filters)
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['ID', 'Фамилия', 'Имя', 'Отчество', 'Дата рождения', 
                         'Должность', 'Отдел', 'Телефон', 'Email', 'Дата приема', 
                         'Зарплата', 'Статус'])
        
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
        if self.connection and self.connection.is_connected():
            self.connection.close()


class PDFGenerator:
    """Класс для генерации PDF документов"""
    @staticmethod
    def generate_employee_report(employee, vacations=None):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1
        )
        elements.append(Paragraph(f"Личная карточка сотрудника", title_style))
        elements.append(Spacer(1, 20))
        
        data = [
            ['Параметр', 'Значение'],
            ['Фамилия:', employee[1]],
            ['Имя:', employee[2]],
            ['Отчество:', employee[3] or '—'],
            ['Дата рождения:', str(employee[4]) if employee[4] else '—'],
            ['Должность:', employee[5] or '—'],
            ['Отдел:', employee[6] or '—'],
            ['Телефон:', employee[7] or '—'],
            ['Email:', employee[8] or '—'],
            ['Дата приема:', str(employee[9]) if employee[9] else '—'],
            ['Зарплата:', f"{employee[10]:,.2f} ₽" if employee[10] else '—'],
        ]
        
        table = Table(data, colWidths=[150, 350])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 30))
        
        status_map = {
            'active': 'Активен',
            'on_vacation': 'В отпуске',
            'sick_leave': 'На больничном',
            'fired': 'Уволен'
        }
        status_text = status_map.get(employee[11], employee[11])
        elements.append(Paragraph(f"Статус: {status_text}", styles['Normal']))
        elements.append(Spacer(1, 30))
        
        if vacations:
            elements.append(Paragraph("История отпусков", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            vac_data = [['Начало', 'Окончание', 'Тип', 'Статус']]
            for vac in vacations:
                vac_data.append([
                    str(vac[2]),
                    str(vac[3]),
                    vac[4] or '—',
                    vac[5] or '—'
                ])
            
            vac_table = Table(vac_data, colWidths=[100, 100, 150, 150])
            vac_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(vac_table)
        
        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
    
    @staticmethod
    def generate_department_report(department_name, employees):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1
        )
        elements.append(Paragraph(f"Отчет по отделу: {department_name}", title_style))
        elements.append(Spacer(1, 20))
        
        total_salary = sum(emp[10] for emp in employees if emp[10])
        avg_salary = total_salary / len(employees) if employees else 0
        
        info_data = [
            ['Показатель', 'Значение'],
            ['Количество сотрудников:', str(len(employees))],
            ['Средняя зарплата:', f"{avg_salary:,.2f} ₽"],
            ['Фонд оплаты труда:', f"{total_salary:,.2f} ₽"],
        ]
        
        info_table = Table(info_data, colWidths=[300, 300])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 30))
        
        elements.append(Paragraph("Список сотрудников", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        emp_data = [['Фамилия', 'Имя', 'Должность', 'Телефон', 'Email', 'Зарплата']]
        for emp in employees:
            emp_data.append([
                emp[1],
                emp[2],
                emp[5] or '—',
                emp[7] or '—',
                emp[8] or '—',
                f"{emp[10]:,.2f} ₽" if emp[10] else '—'
            ])
        
        emp_table = Table(emp_data, colWidths=[100, 100, 120, 120, 150, 100])
        emp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(emp_table)
        
        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data


class LoginDialog(QDialog):
    """Диалог авторизации"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.authenticated_user = None
        self.setWindowTitle("Авторизация")
        self.setModal(True)
        self.setFixedSize(400, 250)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #0078D7;
            }
            QPushButton {
                padding: 10px;
                border-radius: 4px;
            }
        """)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        title = QLabel(" Вход в систему")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px; color: #0078D7;")
        layout.addWidget(title)
        
        form_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Введите логин")
        self.username_edit.setMinimumHeight(35)
        
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Введите пароль")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setMinimumHeight(35)
        self.password_edit.returnPressed.connect(self.login)
        
        form_layout.addRow("Логин:", self.username_edit)
        form_layout.addRow("Пароль:", self.password_edit)
        
        layout.addLayout(form_layout)
        layout.addSpacing(20)
        
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff4444;")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        
        buttons_layout = QHBoxLayout()
        
        login_btn = QPushButton("Войти")
        login_btn.setMinimumHeight(35)
        login_btn.clicked.connect(self.login)
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
        """)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setMinimumHeight(35)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        buttons_layout.addWidget(login_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        info_label = QLabel("По умолчанию: admin / admin123")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 10px;")
        layout.addWidget(info_label)
        
        self.setLayout(layout)
    
    def login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        
        if not username or not password:
            self.error_label.setText("Введите логин и пароль")
            self.error_label.setVisible(True)
            return
        
        user = self.db.authenticate_user(username, password)
        
        if user:
            self.authenticated_user = user
            self.accept()
        else:
            self.error_label.setText("Неверный логин или пароль")
            self.error_label.setVisible(True)
            self.password_edit.clear()
            self.password_edit.setFocus()


class Validators:
    """Класс с методами валидации"""
    
    @staticmethod
    def validate_name(name, field_name):
        if not name or len(name.strip()) < 2:
            return False, f"{field_name} должно содержать минимум 2 символа"
        if not re.match(r'^[а-яёА-ЯЁa-zA-Z\-\'\s]+$', name):
            return False, f"{field_name} может содержать только буквы, дефис, апостроф и пробел"
        return True, ""
    
    @staticmethod
    def validate_birth_date(birth_date):
        today = date.today()
        birth = birth_date.toPython()
        if birth > today:
            return False, "Дата рождения не может быть в будущем"
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if age > 100:
            return False, "Возраст не может быть больше 100 лет"
        if age < 16:
            return False, "Сотрудник должен быть не младше 16 лет"
        return True, ""
    
    @staticmethod
    def validate_hire_date(hire_date, birth_date):
        today = date.today()
        hire = hire_date.toPython()
        birth = birth_date.toPython()
        if hire > today:
            return False, "Дата приема не может быть в будущем"
        age_at_hire = hire.year - birth.year - ((hire.month, hire.day) < (birth.month, birth.day))
        if age_at_hire < 16:
            return False, "На момент приема сотруднику должно быть минимум 16 лет"
        if hire.year < 1990:
            return False, "Дата приема не может быть раньше 1990 года"
        return True, ""
    
    @staticmethod
    def validate_salary(salary_text):
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
        if not email.strip():
            return True, ""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False, "Некорректный формат email"
        return True, ""
    
    @staticmethod
    def validate_phone(phone):
        if not phone.strip():
            return True, ""
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 6:
            return False, "Номер телефона слишком короткий (минимум 6 цифр)"
        if len(digits) > 15:
            return False, "Номер телефона слишком длинный (максимум 15 цифр)"
        return True, ""
    
    @staticmethod
    def validate_vacation_dates(start_date, end_date):
        start = start_date.toPython()
        end = end_date.toPython()
        if start > end:
            return False, "Дата окончания не может быть раньше даты начала"
        if start == end:
            return False, "Отпуск должен быть минимум 1 день"
        return True, ""
    
    @staticmethod
    def format_name(name):
        if name:
            return name.strip().title()
        return name


class ValidationResult:
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.is_visible = False
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.filter_group = QGroupBox("Фильтры")
        self.filter_group.setVisible(False)
        self.filter_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                color: #ffffff;
                background-color: #2d2d2d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #0078D7;
            }
        """)
        filter_layout = QVBoxLayout()
        
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("Статус:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все статусы", None)
        self.status_filter.addItem("Активен", "active")
        self.status_filter.addItem("В отпуске", "on_vacation")
        self.status_filter.addItem("На больничном", "sick_leave")
        self.status_filter.addItem("Уволен", "fired")
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        row1_layout.addWidget(self.status_filter)
        
        row1_layout.addWidget(QLabel("Отдел:"))
        self.department_filter = QComboBox()
        self.department_filter.addItem("Все отделы", None)
        self.department_filter.currentIndexChanged.connect(self.apply_filters)
        row1_layout.addWidget(self.department_filter)
        filter_layout.addLayout(row1_layout)
        
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("Должность:"))
        self.position_filter = QComboBox()
        self.position_filter.setEditable(True)
        self.position_filter.addItem("Все должности", None)
        self.position_filter.lineEdit().setPlaceholderText("Поиск должности...")
        self.position_filter.currentIndexChanged.connect(self.apply_filters)
        row2_layout.addWidget(self.position_filter)
        
        row2_layout.addWidget(QLabel("Поиск:"))
        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("Фамилия, имя, должность...")
        self.search_filter.textChanged.connect(self.apply_filters)
        row2_layout.addWidget(self.search_filter)
        filter_layout.addLayout(row2_layout)
        
        row3_layout = QHBoxLayout()
        row3_layout.addWidget(QLabel("Дата приема от:"))
        self.hire_date_from = QDateEdit()
        self.hire_date_from.setCalendarPopup(True)
        self.hire_date_from.setDate(QDate(1990, 1, 1))
        self.hire_date_from.setSpecialValueText("Не выбрано")
        self.hire_date_from.dateChanged.connect(self.apply_filters)
        row3_layout.addWidget(self.hire_date_from)
        
        row3_layout.addWidget(QLabel("до:"))
        self.hire_date_to = QDateEdit()
        self.hire_date_to.setCalendarPopup(True)
        self.hire_date_to.setDate(QDate.currentDate())
        self.hire_date_to.setSpecialValueText("Не выбрано")
        self.hire_date_to.dateChanged.connect(self.apply_filters)
        row3_layout.addWidget(self.hire_date_to)
        filter_layout.addLayout(row3_layout)
        
        row4_layout = QHBoxLayout()
        row4_layout.addWidget(QLabel("Зарплата от:"))
        self.salary_from = QDoubleSpinBox()
        self.salary_from.setRange(0, 10000000)
        self.salary_from.setPrefix("₽ ")
        self.salary_from.setSpecialValueText("Не выбрано")
        self.salary_from.valueChanged.connect(self.apply_filters)
        row4_layout.addWidget(self.salary_from)
        
        row4_layout.addWidget(QLabel("до:"))
        self.salary_to = QDoubleSpinBox()
        self.salary_to.setRange(0, 10000000)
        self.salary_to.setPrefix("₽ ")
        self.salary_to.setSpecialValueText("Не выбрано")
        self.salary_to.valueChanged.connect(self.apply_filters)
        row4_layout.addWidget(self.salary_to)
        filter_layout.addLayout(row4_layout)
        
        row5_layout = QHBoxLayout()
        row5_layout.addWidget(QLabel("Возраст от:"))
        self.age_from = QSpinBox()
        self.age_from.setRange(0, 100)
        self.age_from.setSpecialValueText("Не выбрано")
        self.age_from.valueChanged.connect(self.apply_filters)
        row5_layout.addWidget(self.age_from)
        
        row5_layout.addWidget(QLabel("до:"))
        self.age_to = QSpinBox()
        self.age_to.setRange(0, 100)
        self.age_to.setSpecialValueText("Не выбрано")
        self.age_to.valueChanged.connect(self.apply_filters)
        row5_layout.addWidget(self.age_to)
        filter_layout.addLayout(row5_layout)
        
        buttons_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("Применить фильтры")
        self.apply_btn.clicked.connect(self.apply_filters)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        self.clear_btn = QPushButton("Сбросить фильтры")
        self.clear_btn.clicked.connect(self.clear_filters)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        
        self.export_csv_btn = QPushButton("Экспорт в CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        
        self.export_pdf_btn = QPushButton("Экспорт в PDF")
        self.export_pdf_btn.clicked.connect(self.export_to_pdf)
        self.export_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        
        buttons_layout.addWidget(self.apply_btn)
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addWidget(self.export_csv_btn)
        buttons_layout.addWidget(self.export_pdf_btn)
        buttons_layout.addStretch()
        
        filter_layout.addLayout(buttons_layout)
        self.filter_group.setLayout(filter_layout)
        main_layout.addWidget(self.filter_group)
        
        self.setLayout(main_layout)
    
    def load_departments(self):
        if self.main_window and self.main_window.db:
            self.department_filter.clear()
            self.department_filter.addItem("Все отделы", None)
            departments = self.main_window.db.get_departments()
            for dept in departments:
                if dept:
                    self.department_filter.addItem(dept, dept)
    
    def load_positions(self):
        if self.main_window and self.main_window.db:
            self.position_filter.clear()
            self.position_filter.addItem("Все должности", None)
            positions = self.main_window.db.get_positions()
            for pos in positions:
                if pos:
                    self.position_filter.addItem(pos, pos)
    
    def toggle_visibility(self):
        self.is_visible = not self.is_visible
        self.filter_group.setVisible(self.is_visible)
        return self.is_visible
    
    def get_filters(self):
        filters = {}
        
        status = self.status_filter.currentData()
        if status:
            filters['status'] = status
        
        department = self.department_filter.currentData()
        if department:
            filters['department'] = department
        
        position = self.position_filter.currentData()
        if position:
            filters['position'] = position
        
        search = self.search_filter.text().strip()
        if search:
            filters['search'] = search
        
        if self.hire_date_from.date() != QDate(1990, 1, 1):
            filters['hire_date_from'] = self.hire_date_from.date().toString("yyyy-MM-dd")
        
        if self.hire_date_to.date() != QDate.currentDate():
            filters['hire_date_to'] = self.hire_date_to.date().toString("yyyy-MM-dd")
        
        if self.salary_from.value() > 0:
            filters['salary_from'] = self.salary_from.value()
        
        if self.salary_to.value() > 0:
            filters['salary_to'] = self.salary_to.value()
        
        if self.age_from.value() > 0:
            filters['age_from'] = self.age_from.value()
        
        if self.age_to.value() > 0:
            filters['age_to'] = self.age_to.value()
        
        return filters
    
    def apply_filters(self):
        if self.main_window:
            self.main_window.load_employees()
    
    def clear_filters(self):
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
    
    def export_to_pdf(self):
        if not self.main_window:
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в PDF", "employees_report.pdf", 
            "PDF files (*.pdf);;All files (*.*)"
        )
        
        if file_name:
            try:
                filters = self.get_filters()
                employees = self.main_window.db.get_employees(filters)
                
                if employees:
                    departments = {}
                    for emp in employees:
                        dept = emp[6] or "Без отдела"
                        if dept not in departments:
                            departments[dept] = []
                        departments[dept].append(emp)
                    
                    dept_name = list(departments.keys())[0]
                    pdf_data = PDFGenerator.generate_department_report(
                        dept_name, departments[dept_name]
                    )
                    
                    with open(file_name, 'wb') as f:
                        f.write(pdf_data)
                    
                    QMessageBox.information(self, "Успех", 
                        f"Отчет экспортирован в {file_name}\n"
                        f"Сотрудников: {len(employees)}\n"
                        f"Отделов: {len(departments)}")
                else:
                    QMessageBox.warning(self, "Предупреждение", "Нет данных для экспорта")
                    
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта PDF: {str(e)}")


class EmployeeDialog(QDialog):
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = parent.db if parent else None
        self.setWindowTitle("Добавление сотрудника" if not employee_id else "Редактирование сотрудника")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #0078D7;
            }
            QLineEdit.error {
                border: 2px solid #dc3545;
                background-color: #3d2020;
            }
            QLineEdit.warning {
                border: 2px solid #ffc107;
                background-color: #3d3520;
            }
            QComboBox {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #0078D7;
            }
            QDateEdit {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QPushButton {
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        self.init_ui()
        self.setup_validators()
        
        if employee_id:
            self.load_employee_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
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
            
            error_label = QLabel("")
            error_label.setStyleSheet("color: #ff4444; font-size: 11px; margin-left: 10px;")
            error_label.setVisible(False)
            self.error_labels[field_name] = error_label
            form_layout.addRow("", error_label)
        
        layout.addLayout(form_layout)
        
        buttons_layout = QHBoxLayout()
        save_btn = QPushButton(" Сохранить")
        save_btn.clicked.connect(self.save_employee)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
        """)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        self.load_departments()
    
    def setup_validators(self):
        name_regex = QRegularExpression(r'^[а-яёА-ЯЁa-zA-Z\-\'\s]*$')
        name_validator = QRegularExpressionValidator(name_regex)
        
        self.last_name_edit.setValidator(name_validator)
        self.first_name_edit.setValidator(name_validator)
        self.patronymic_edit.setValidator(name_validator)
        
        salary_regex = QRegularExpression(r'^\d*\.?\d*$')
        salary_validator = QRegularExpressionValidator(salary_regex)
        self.salary_edit.setValidator(salary_validator)
    
    def validate_field(self, field_name):
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
        
        error_label.setVisible(False)
        error_label.setText("")
        widget.setProperty("class", "")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        
        validation_result = ValidationResult()
        
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
        
        if not validation_result.is_valid():
            error_label.setText(validation_result.get_all_messages()[0])
            error_label.setVisible(True)
            widget.setProperty("class", "error")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            return False
        
        return True
    
    def load_departments(self):
        if self.db:
            self.department_combo.clear()
            self.department_combo.addItem("")
            departments = self.db.get_departments()
            self.department_combo.addItems(departments)
    
    def load_employee_data(self):
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
        validation_result = ValidationResult()
        
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
        
        if self.patronymic_edit.text().strip():
            is_valid, message = Validators.validate_name(self.patronymic_edit.text(), "Отчество")
            if not is_valid:
                validation_result.add_warning(message)
        
        is_valid, message = Validators.validate_birth_date(self.birth_date.date())
        if not is_valid:
            validation_result.add_error(message)
        
        if not self.position_edit.text().strip():
            validation_result.add_error("Должность обязательна")
        
        is_valid, message = Validators.validate_hire_date(
            self.hire_date.date(), self.birth_date.date())
        if not is_valid:
            validation_result.add_error(message)
        
        is_valid, message = Validators.validate_salary(self.salary_edit.text())
        if not is_valid:
            validation_result.add_error(message)
        
        is_valid, message = Validators.validate_email(self.email_edit.text())
        if not is_valid:
            validation_result.add_error(message)
        
        is_valid, message = Validators.validate_phone(self.phone_edit.text())
        if not is_valid:
            validation_result.add_warning(message)
        
        if not validation_result.is_valid():
            error_message = "Ошибки при заполнении формы:\n\n"
            error_message += "\n".join([f"• {err}" for err in validation_result.get_all_messages()])
            QMessageBox.warning(self, "Ошибка валидации", error_message)
            return
        
        if validation_result.warnings:
            warning_message = "Предупреждения:\n\n"
            warning_message += "\n".join([f"• {w}" for w in validation_result.warnings])
            warning_message += "\n\nПродолжить сохранение?"
            reply = QMessageBox.question(self, "Предупреждения", warning_message,
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
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
                QMessageBox.information(self, "Успех", " Данные сотрудника обновлены!")
            else:
                self.db.add_employee(data)
                QMessageBox.information(self, "Успех", " Новый сотрудник добавлен!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка базы данных", 
                               f" Не удалось сохранить данные:\n{str(e)}")


class VacationDialog(QDialog):
    def __init__(self, parent=None, employee_id=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.db = parent.db if parent else None
        self.setWindowTitle(" Добавление отпуска")
        self.setModal(True)
        self.setFixedSize(400, 250)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QDateEdit, QComboBox {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #0078D7;
            }
            QPushButton {
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
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
        
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.error_label.setVisible(False)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.error_label)
        layout.addSpacing(20)
        
        buttons_layout = QHBoxLayout()
        save_btn = QPushButton(" Сохранить")
        save_btn.clicked.connect(self.save_vacation)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
        """)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def validate_dates(self):
        is_valid, message = Validators.validate_vacation_dates(
            self.start_date.date(), self.end_date.date())
        
        if not is_valid:
            self.error_label.setText(message)
            self.error_label.setVisible(True)
        else:
            self.error_label.setVisible(False)
        
        return is_valid
    
    def save_vacation(self):
        if not self.validate_dates():
            QMessageBox.warning(self, "Ошибка", self.error_label.text())
            return
        
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
            QMessageBox.information(self, "Успех", " Отпуск добавлен!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f" Ошибка при добавлении отпуска:\n{str(e)}")


class HRApp(QMainWindow):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.current_user = user
        self.filter_visible = False
        self.init_ui()
        self.load_employees()
    
    def init_ui(self):
        self.setWindowTitle(f"Система кадрового учета - {self.current_user['full_name']}")
        self.setGeometry(100, 100, 1400, 800)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QPushButton {
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                background-color: #2d2d2d;
                border: 1px solid #444;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 4px;
                gridline-color: #333;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #0078D7;
                font-weight: bold;
            }
            QLabel {
                color: #ffffff;
            }
            QComboBox {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #0078D7;
            }
            QDateEdit {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QSpinBox, QDoubleSpinBox {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: #ffffff;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
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
        
        self.filter_toggle_btn = QPushButton(" Фильтры")
        self.filter_toggle_btn.setCheckable(True)
        self.filter_toggle_btn.clicked.connect(self.toggle_filters)
        
        self.pdf_report_btn = QPushButton(" PDF отчет")
        self.pdf_report_btn.clicked.connect(self.generate_pdf_report)
        
        top_panel.addWidget(self.add_btn)
        top_panel.addWidget(self.edit_btn)
        top_panel.addWidget(self.delete_btn)
        top_panel.addWidget(self.vacation_btn)
        top_panel.addWidget(self.refresh_btn)
        top_panel.addWidget(self.stats_btn)
        top_panel.addWidget(self.filter_toggle_btn)

        top_panel.addWidget(self.pdf_report_btn)
        top_panel.addStretch()
        
        main_layout.addLayout(top_panel)
        
        self.filter_widget = FilterWidget(self)
        main_layout.addWidget(self.filter_widget)
        
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
        self.table.setAlternatingRowColors(True)
        
        main_layout.addWidget(self.table)
        
        info_panel = QHBoxLayout()
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("font-weight: bold; color: #0078D7;")
        info_panel.addWidget(self.status_label)
        info_panel.addStretch()
        main_layout.addLayout(info_panel)
        
        self.filter_widget.load_departments()
        self.filter_widget.load_positions()
        
        self.update_status_stats()
    
    def toggle_filters(self):
        self.filter_visible = self.filter_widget.toggle_visibility()
        
        if self.filter_visible:
            self.filter_toggle_btn.setText(" Скрыть фильтры")
            self.filter_toggle_btn.setChecked(True)
            self.filter_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    padding: 8px 15px;
                    border-radius: 4px;
                    font-weight: bold;
                    border: 2px solid #005A9E;
                }
            """)
        else:
            self.filter_toggle_btn.setText(" Фильтры")
            self.filter_toggle_btn.setChecked(False)
            self.filter_toggle_btn.setStyleSheet("""
                QPushButton {
                    padding: 8px 15px;
                    border-radius: 4px;
                    font-weight: bold;
                    background-color: #2d2d2d;
                    border: 1px solid #444;
                    color: #ffffff;
                }
            """)
            self.filter_widget.clear_filters()
    
    
    def generate_pdf_report(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите сотрудника для отчета!")
            return
        
        employee_id = int(self.table.item(row, 0).text())
        employee = self.db.get_employee_by_id(employee_id)
        
        if not employee:
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить PDF отчет", 
            f"employee_{employee[1]}_{employee[2]}.pdf", 
            "PDF files (*.pdf);;All files (*.*)"
        )
        
        if file_name:
            try:
                vacations = self.db.get_employee_vacations(employee_id)
                pdf_data = PDFGenerator.generate_employee_report(employee, vacations)
                
                with open(file_name, 'wb') as f:
                    f.write(pdf_data)
                
                QMessageBox.information(self, "Успех", 
                    f" PDF отчет сохранен в {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", 
                    f" Ошибка создания PDF: {str(e)}")
    
    def load_employees(self):
        try:
            filters = self.filter_widget.get_filters() if self.filter_visible else None
            employees = self.db.get_employees(filters)
            self.update_table(employees)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки: {str(e)}")
    
    def update_table(self, employees):
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
            
            color_map = {
                "active": QColor(40, 60, 40),
                "on_vacation": QColor(40, 40, 60),
                "sick_leave": QColor(60, 50, 30),
                "fired": QColor(60, 30, 30)
            }
            
            text_color_map = {
                "active": QColor(100, 255, 100),
                "on_vacation": QColor(100, 100, 255),
                "sick_leave": QColor(255, 200, 100),
                "fired": QColor(255, 100, 100)
            }
            
            bg_color = color_map.get(emp[11], QColor(30, 30, 30))
            status_color = text_color_map.get(emp[11], QColor(255, 255, 255))
            
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QBrush(bg_color))
                    item.setForeground(QBrush(QColor(255, 255, 255)))
            
            status_item.setForeground(status_color)
            status_item.setBackground(QBrush(bg_color))
            self.table.setItem(row, 10, status_item)
        
        self.table.resizeColumnsToContents()
        self.update_status_stats()
    
    def show_context_menu(self, position):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #0078D7;
            }
        """)
        
        view_action = QAction(" Просмотреть", self)
        view_action.triggered.connect(self.view_details_current)
        
        edit_action = QAction(" Редактировать", self)
        edit_action.triggered.connect(self.edit_employee)
        
        vacation_action = QAction(" Добавить отпуск", self)
        vacation_action.triggered.connect(self.add_vacation)
        
        pdf_action = QAction(" PDF отчет", self)
        pdf_action.triggered.connect(self.generate_pdf_report)
        
        delete_action = QAction(" Удалить", self)
        delete_action.triggered.connect(self.delete_employee)
        
        menu.addAction(view_action)
        menu.addAction(edit_action)
        menu.addAction(vacation_action)
        menu.addAction(pdf_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def view_details_current(self):
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
        
        reply = QMessageBox.question(self, "Удаление", f"? Удалить {name}?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_employee(employee_id)
                self.load_employees()
                self.filter_widget.load_departments()
                self.filter_widget.load_positions()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f" Ошибка удаления: {str(e)}")
    
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
        row = index.row()
        employee_id = int(self.table.item(row, 0).text())
        employee = self.db.get_employee_by_id(employee_id)
        
        if not employee:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f" Информация - {employee[1]} {employee[2]}")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2d2d2d;
            }
            QTabBar::tab {
                padding: 10px 20px;
                margin-right: 2px;
                background-color: #333;
                color: #fff;
            }
            QTabBar::tab:selected {
                background-color: #0078D7;
                color: white;
            }
        """)
        
        layout = QVBoxLayout()
        tabs = QTabWidget()
        
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        basic_layout.setSpacing(15)
        
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
            lbl.setStyleSheet("font-weight: bold; color: #0078D7;")
            basic_layout.addRow(lbl, QLabel(str(value)))
        
        tabs.addTab(basic_tab, "Основная информация")
        
        vacation_tab = QWidget()
        vacation_layout = QVBoxLayout(vacation_tab)
        vacation_table = QTableWidget()
        vacation_table.setColumnCount(4)
        vacation_table.setHorizontalHeaderLabels(["Начало", "Окончание", "Тип", "Статус"])
        vacation_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #444;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                border-bottom: 2px solid #0078D7;
            }
        """)
        
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
        tabs.addTab(vacation_tab, " Отпуска")
        
        layout.addWidget(tabs)
        
        buttons_layout = QHBoxLayout()
        
        pdf_btn = QPushButton(" Сохранить PDF")
        pdf_btn.clicked.connect(lambda: self.save_employee_pdf(employee, vacations, dialog))
        pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        buttons_layout.addWidget(pdf_btn)
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def save_employee_pdf(self, employee, vacations, parent_dialog):
        file_name, _ = QFileDialog.getSaveFileName(
            parent_dialog, "Сохранить PDF отчет", 
            f"employee_{employee[1]}_{employee[2]}.pdf", 
            "PDF files (*.pdf);;All files (*.*)"
        )

        if file_name:
            try:
                pdf_data = PDFGenerator.generate_employee_report(employee, vacations)
                
                with open(file_name, 'wb') as f:
                    f.write(pdf_data)
                
                QMessageBox.information(parent_dialog, "Успех", 
                    f" PDF отчет сохранен в {file_name}")
            except Exception as e:
                QMessageBox.critical(parent_dialog, "Ошибка", 
                    f" Ошибка создания PDF: {str(e)}")
    
    def show_statistics(self):
        try:
            stats = self.db.get_statistics()
            dialog = QDialog(self)
            dialog.setWindowTitle(" Статистика")
            dialog.setMinimumSize(400, 300)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #1e1e1e;
                }
                QLabel {
                    color: #ffffff;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #0078D7;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
            """)
            
            layout = QVBoxLayout()
            title = QLabel(" Статистика сотрудников")
            title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0078D7; padding: 10px;")
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)
            
            group = QGroupBox()
            form = QFormLayout()
            form.setSpacing(10)
            
            stats_data = [
                ("Всего:", str(stats['total']), "#0078D7"),
                ("Активных:", str(stats['active']), "#28a745"),
                ("В отпуске:", str(stats['on_vacation']), "#0078D7"),
                ("На больничном:", str(stats['sick_leave']), "#ffc107"),
                ("Уволенных:", str(stats['fired']), "#dc3545"),
            ]
            
            for label, value, color in stats_data:
                lbl = QLabel(label)
                lbl.setStyleSheet(f"font-weight: bold; color: {color}; font-size: 14px;")
                val_lbl = QLabel(value)
                val_lbl.setStyleSheet(f"font-weight: bold; color: {color}; font-size: 14px;")
                form.addRow(lbl, val_lbl)
            
            group.setLayout(form)
            layout.addWidget(group)
            
            btn = QPushButton("Закрыть")
            btn.clicked.connect(dialog.accept)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #555;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #666;
                }
            """)
            layout.addWidget(btn)
            
            dialog.setLayout(layout)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f" Ошибка: {str(e)}")
    
    def update_status_stats(self):
        try:
            stats = self.db.get_statistics()
            visible_rows = self.table.rowCount()
            
            filter_text = " |  Фильтры активны" if self.filter_visible else ""

            
            self.status_label.setText(
                f" {self.current_user['full_name']} | "
                f"Отображается: {visible_rows}{filter_text}{update_text} | "
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
    
    app.setStyleSheet("""
        QToolTip {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #0078D7;
            padding: 8px;
            border-radius: 6px;
            font-size: 12px;
        }
        QMessageBox {
            background-color: #2d2d2d;
            color: #ffffff;
        }
        QMessageBox QPushButton {
            min-width: 100px;
            min-height: 35px;
            padding: 5px 15px;
        }
    """)
    
    try:
        db = Database()
        
        login_dialog = LoginDialog(db)
        if login_dialog.exec() != QDialog.Accepted:
            sys.exit(0)
        
        user = login_dialog.authenticated_user
        
        window = HRApp(db, user)
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "Критическая ошибка", 
                           f" Не удалось запустить приложение:\n{str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
