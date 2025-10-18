from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from flask_session import Session
import sqlite3
import pandas as pd
import datetime
import json
import os
import hashlib
import logging
from io import BytesIO
import tempfile

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Configure logging
logging.basicConfig(level=logging.INFO)

class InventoryManager:
    def __init__(self):
        self.init_db()
    
    def get_connection(self):
        """Get database connection - use in-memory for Vercel"""
        # On Vercel, use in-memory database since filesystem is read-only
        if os.environ.get('VERCEL'):
            return sqlite3.connect(':memory:', check_same_thread=False)
        else:
            return sqlite3.connect('dmc_inventory.db', check_same_thread=False)
    
    def init_db(self):
        """Initialize the database with sample data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Drop tables if they exist (for clean slate)
        cursor.execute('DROP TABLE IF EXISTS it_inventory')
        cursor.execute('DROP TABLE IF EXISTS inventory_tracker')
        cursor.execute('DROP TABLE IF EXISTS users')
        
        # Create IT Inventory table
        cursor.execute('''
            CREATE TABLE it_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assets_id TEXT UNIQUE,
                system_type TEXT,
                location TEXT,
                brand TEXT,
                model TEXT,
                serial_number TEXT UNIQUE,
                status TEXT,
                windows TEXT,
                config TEXT,
                warranty_status TEXT,
                last_audit_date TEXT,
                remarks TEXT
            )
        ''')
        
        # Create Inventory Tracker table
        cursor.execute('''
            CREATE TABLE inventory_tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                assets_id TEXT,
                system_type TEXT,
                location TEXT,
                brand TEXT,
                model TEXT,
                serial_number TEXT,
                status TEXT,
                windows TEXT,
                config TEXT,
                warranty_status TEXT,
                date_of_allocation TEXT,
                date_of_return TEXT,
                last_audit_date TEXT,
                phone_number TEXT,
                extra_allocated_item TEXT
            )
        ''')
        
        # Create user table
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT
            )
        ''')
        
        # Insert default admin user
        default_password = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash) 
            VALUES (?, ?)
        ''', ("admin", default_password))
        
        # Insert sample IT inventory data
        sample_it_items = [
            ('LAPTOP001', 'Laptop', 'Indore', 'Dell', 'Latitude 5420', 
             'SN-DELL-001', 'Available', 'Windows 10', 'i5/8GB/256GB', 
             'Active', '2024-01-15', 'Good condition'),
            ('DESKTOP001', 'Desktop', 'Mumbai', 'HP', 'ProDesk 600', 
             'SN-HP-001', 'Allocated', 'Windows 11', 'i7/16GB/512GB', 
             'Active', '2024-01-10', 'Allocated to John'),
            ('MONITOR001', 'Monitor', 'Indore', 'Dell', 'UltraSharp 24', 
             'SN-MON-001', 'Available', 'N/A', '24 inch FHD', 
             'No Warranty', '2024-01-20', 'Like new')
        ]
        
        cursor.executemany('''
            INSERT INTO it_inventory 
            (assets_id, system_type, location, brand, model, serial_number, 
             status, windows, config, warranty_status, last_audit_date, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_it_items)
        
        # Insert sample tracker data
        sample_tracker_items = [
            ('John Doe', 'DESKTOP001', 'Desktop', 'Mumbai', 'HP', 'ProDesk 600',
             'SN-HP-001', 'Allocated', 'Windows 11', 'i7/16GB/512GB', 'Active',
             '2024-01-10', '', '2024-01-10', '9876543210', 'Wireless Mouse'),
            ('Jane Smith', 'LAPTOP001', 'Laptop', 'Indore', 'Dell', 'Latitude 5420',
             'SN-DELL-001', 'Returned', 'Windows 10', 'i5/8GB/256GB', 'Active', 
             '2023-12-01', '2024-01-14', '2024-01-14', '9876543211', 'Laptop Bag')
        ]
        
        cursor.executemany('''
            INSERT INTO inventory_tracker 
            (employee_name, assets_id, system_type, location, brand, model, 
             serial_number, status, windows, config, warranty_status, 
             date_of_allocation, date_of_return, last_audit_date, 
             phone_number, extra_allocated_item)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_tracker_items)
        
        conn.commit()
        conn.close()

inventory_manager = InventoryManager()

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        
        conn = inventory_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == hashlib.sha256(password.encode()).hexdigest():
            session['user'] = username
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

# IT Inventory API Routes
@app.route('/api/it_inventory', methods=['GET'])
def get_it_inventory():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = inventory_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM it_inventory")
        rows = cursor.fetchall()
        conn.close()
        
        columns = ["id", "assets_id", "system_type", "location", "brand", "model", 
                  "serial_number", "status", "windows", "config", "warranty_status", 
                  "last_audit_date", "remarks"]
        
        data = [dict(zip(columns, row)) for row in rows]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/it_inventory', methods=['POST'])
def add_it_item():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    conn = inventory_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO it_inventory 
            (assets_id, system_type, location, brand, model, serial_number, 
             status, windows, config, warranty_status, last_audit_date, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('assets_id'), data.get('system_type'), data.get('location'),
            data.get('brand'), data.get('model'), data.get('serial_number'),
            data.get('status'), data.get('windows'), data.get('config'),
            data.get('warranty_status'), data.get('last_audit_date'), data.get('remarks')
        ))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Item added successfully'})
    
    except sqlite3.IntegrityError as e:
        conn.close()
        return jsonify({'success': False, 'message': 'Assets ID or Serial Number already exists'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

# Add other routes similarly...

@app.route('/api/reports/summary')
def get_reports_summary():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = inventory_manager.get_connection()
        cursor = conn.cursor()
        
        # Get summary data
        cursor.execute("SELECT COUNT(*) FROM it_inventory")
        total_assets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM it_inventory WHERE status='Available'")
        available_assets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM it_inventory WHERE status='Allocated'")
        allocated_assets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM it_inventory WHERE status='Under Maintenance'")
        maintenance_assets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventory_tracker WHERE status='Allocated'")
        active_allocations = cursor.fetchone()[0]
        
        conn.close()
        
        summary = {
            'total_assets': total_assets,
            'available_assets': available_assets,
            'allocated_assets': allocated_assets,
            'maintenance_assets': maintenance_assets,
            'active_allocations': active_allocations
        }
        
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Health check endpoint
@app.route('/health')
def health():
    try:
        conn = inventory_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
