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
app.secret_key = 'your-secret-key-here'  # Change in production!
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Configure logging
logging.basicConfig(level=logging.INFO)

class InventoryManager:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """Initialize the SQLite database"""
        conn = sqlite3.connect('dmc_inventory.db')
        cursor = conn.cursor()
        
        # Create IT Inventory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS it_inventory (
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
            CREATE TABLE IF NOT EXISTS inventory_tracker (
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
            CREATE TABLE IF NOT EXISTS users (
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
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect('dmc_inventory.db')

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

@app.route('/api/it_inventory/<int:item_id>', methods=['PUT'])
def update_it_item(item_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    conn = inventory_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE it_inventory 
            SET assets_id=?, system_type=?, location=?, brand=?, model=?, 
                serial_number=?, status=?, windows=?, config=?, warranty_status=?, 
                last_audit_date=?, remarks=?
            WHERE id=?
        ''', (
            data.get('assets_id'), data.get('system_type'), data.get('location'),
            data.get('brand'), data.get('model'), data.get('serial_number'),
            data.get('status'), data.get('windows'), data.get('config'),
            data.get('warranty_status'), data.get('last_audit_date'), data.get('remarks'),
            item_id
        ))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Item updated successfully'})
    
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/it_inventory/<int:item_id>', methods=['DELETE'])
def delete_it_item(item_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = inventory_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM it_inventory WHERE id=?", (item_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Item deleted successfully'})
    
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

# Inventory Tracker API Routes
@app.route('/api/inventory_tracker', methods=['GET'])
def get_inventory_tracker():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = inventory_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory_tracker")
    rows = cursor.fetchall()
    conn.close()
    
    columns = ["id", "employee_name", "assets_id", "system_type", "location", "brand", "model", 
              "serial_number", "status", "windows", "config", "warranty_status", 
              "date_of_allocation", "date_of_return", "last_audit_date", "phone_number", 
              "extra_allocated_item"]
    
    data = [dict(zip(columns, row)) for row in rows]
    return jsonify(data)

@app.route('/api/inventory_tracker', methods=['POST'])
def add_tracker_record():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    conn = inventory_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO inventory_tracker 
            (employee_name, assets_id, system_type, location, brand, model, 
             serial_number, status, windows, config, warranty_status, 
             date_of_allocation, date_of_return, last_audit_date, 
             phone_number, extra_allocated_item)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('employee_name'), data.get('assets_id'), data.get('system_type'),
            data.get('location'), data.get('brand'), data.get('model'),
            data.get('serial_number'), data.get('status'), data.get('windows'),
            data.get('config'), data.get('warranty_status'), data.get('date_of_allocation'),
            data.get('date_of_return'), data.get('last_audit_date'), data.get('phone_number'),
            data.get('extra_allocated_item')
        ))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Record added successfully'})
    
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/inventory_tracker/<int:record_id>', methods=['PUT'])
def update_tracker_record(record_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    conn = inventory_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE inventory_tracker 
            SET employee_name=?, assets_id=?, system_type=?, location=?, brand=?, model=?, 
                serial_number=?, status=?, windows=?, config=?, warranty_status=?, 
                date_of_allocation=?, date_of_return=?, last_audit_date=?, 
                phone_number=?, extra_allocated_item=?
            WHERE id=?
        ''', (
            data.get('employee_name'), data.get('assets_id'), data.get('system_type'),
            data.get('location'), data.get('brand'), data.get('model'),
            data.get('serial_number'), data.get('status'), data.get('windows'),
            data.get('config'), data.get('warranty_status'), data.get('date_of_allocation'),
            data.get('date_of_return'), data.get('last_audit_date'), data.get('phone_number'),
            data.get('extra_allocated_item'), record_id
        ))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Record updated successfully'})
    
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/inventory_tracker/<int:record_id>', methods=['DELETE'])
def delete_tracker_record(record_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = inventory_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM inventory_tracker WHERE id=?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Record deleted successfully'})
    
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

# Export Routes
@app.route('/api/export/it_inventory')
def export_it_inventory():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = inventory_manager.get_connection()
    df = pd.read_sql_query("SELECT * FROM it_inventory", conn)
    conn.close()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='IT_Inventory', index=False)
    
    output.seek(0)
    
    filename = f"IT_Inventory_Export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

@app.route('/api/export/inventory_tracker')
def export_inventory_tracker():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = inventory_manager.get_connection()
    df = pd.read_sql_query("SELECT * FROM inventory_tracker", conn)
    conn.close()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Inventory_Tracker', index=False)
    
    output.seek(0)
    
    filename = f"Inventory_Tracker_Export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

# Reports Route
@app.route('/api/reports/summary')
def get_reports_summary():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = inventory_manager.get_connection()
    
    # Get summary data
    cursor = conn.cursor()
    
    # IT Inventory summary
    cursor.execute("SELECT COUNT(*) FROM it_inventory")
    total_assets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM it_inventory WHERE status='Available'")
    available_assets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM it_inventory WHERE status='Allocated'")
    allocated_assets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM it_inventory WHERE status='Under Maintenance'")
    maintenance_assets = cursor.fetchone()[0]
    
    # Inventory Tracker summary
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

if __name__ == '__main__':
    app.run(debug=True)
