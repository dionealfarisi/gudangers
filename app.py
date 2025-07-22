from flask import Flask, render_template, request, redirect, url_for, flash, Response
import sqlite3
from datetime import datetime
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = 'rahasia'
DB_NAME = 'inventory.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                category TEXT,
                location TEXT,
                description TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                transaction_date DATETIME NOT NULL,
                notes TEXT,
                FOREIGN KEY (item_id) REFERENCES items(id))''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    search = request.args.get('search', '').strip()
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if search:
        c.execute("SELECT * FROM items WHERE name LIKE ?", ('%' + search + '%',))
    else:
        c.execute("SELECT * FROM items")
        
    items = c.fetchall()
    conn.close()
    return render_template('index.html', items=items, search=search)

@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        category = request.form['category']
        location = request.form['location']
        description = request.form['description']
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            c.execute('''INSERT INTO items (name, quantity, category, location, description)
                         VALUES (?, ?, ?, ?, ?)''', 
                     (name, quantity, category, location, description))
            item_id = c.lastrowid
            c.execute('''INSERT INTO transactions (item_id, transaction_type, quantity, transaction_date, notes)
                         VALUES (?, ?, ?, ?, ?)''', 
                     (item_id, 'masuk', quantity, datetime.now(), 'Stok awal'))
            conn.commit()
            flash('Barang berhasil ditambahkan!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('index'))
    return render_template('add_item.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_item(id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        location = request.form['location']
        description = request.form['description']
        
        c.execute('''UPDATE items SET
                    name = ?,
                    category = ?,
                    location = ?,
                    description = ?
                    WHERE id = ?''',
                (name, category, location, description, id))
        conn.commit()
        conn.close()
        flash('Informasi barang berhasil diupdate!', 'success')
        return redirect(url_for('index'))
    
    c.execute("SELECT * FROM items WHERE id = ?", (id,))
    item = c.fetchone()
    conn.close()
    return render_template('edit_item.html', item=item)

@app.route('/delete/<int:id>')
def delete_item(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM items WHERE id = ?", (id,))
    c.execute("DELETE FROM transactions WHERE item_id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Barang berhasil dihapus!', 'success')
    return redirect(url_for('index'))

@app.route('/in/<int:id>', methods=['GET', 'POST'])
def stock_in(id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if request.method == 'POST':
        quantity = int(request.form['quantity'])
        notes = request.form['notes']
        
        try:
            c.execute("UPDATE items SET quantity = quantity + ? WHERE id = ?", (quantity, id))
            c.execute('''INSERT INTO transactions (item_id, transaction_type, quantity, transaction_date, notes)
                         VALUES (?, ?, ?, ?, ?)''', 
                     (id, 'masuk', quantity, datetime.now(), notes))
            conn.commit()
            flash(f'Barang masuk berhasil dicatat! (+{quantity})', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('item_detail', id=id))
    
    c.execute("SELECT * FROM items WHERE id = ?", (id,))
    item = c.fetchone()
    conn.close()
    return render_template('stock_in.html', item=item)

@app.route('/out/<int:id>', methods=['GET', 'POST'])
def stock_out(id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if request.method == 'POST':
        quantity = int(request.form['quantity'])
        notes = request.form['notes']
        
        try:
            c.execute("SELECT quantity FROM items WHERE id = ?", (id,))
            current_stock = c.fetchone()['quantity']
            
            if current_stock < quantity:
                flash(f'Stok tidak cukup! Stok tersedia: {current_stock}', 'danger')
                return redirect(url_for('stock_out', id=id))
            
            c.execute("UPDATE items SET quantity = quantity - ? WHERE id = ?", (quantity, id))
            c.execute('''INSERT INTO transactions (item_id, transaction_type, quantity, transaction_date, notes)
                         VALUES (?, ?, ?, ?, ?)''', 
                     (id, 'keluar', quantity, datetime.now(), notes))
            conn.commit()
            flash(f'Barang keluar berhasil dicatat! (-{quantity})', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('item_detail', id=id))
    
    c.execute("SELECT * FROM items WHERE id = ?", (id,))
    item = c.fetchone()
    conn.close()
    return render_template('stock_out.html', item=item)

@app.route('/item/<int:id>')
def item_detail(id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM items WHERE id = ?", (id,))
    item = c.fetchone()
    
    # Pencarian transaksi berdasarkan tanggal
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if start_date and end_date:
        c.execute('''SELECT * FROM transactions 
                    WHERE item_id = ? 
                    AND DATE(transaction_date) BETWEEN ? AND ?
                    ORDER BY transaction_date DESC''', 
                 (id, start_date, end_date))
    else:
        c.execute("SELECT * FROM transactions WHERE item_id = ? ORDER BY transaction_date DESC", (id,))
    
    transactions = c.fetchall()
    
    conn.close()
    return render_template('item_detail.html', item=item, transactions=transactions, start_date=start_date, end_date=end_date)

@app.route('/transactions')
def transaction_report():
    search = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = '''SELECT transactions.*, items.name 
               FROM transactions 
               JOIN items ON transactions.item_id = items.id'''
    
    conditions = []
    params = []
    
    # Filter berdasarkan nama barang
    if search:
        conditions.append("items.name LIKE ?")
        params.append('%' + search + '%')
    
    # Filter berdasarkan rentang tanggal
    if start_date:
        conditions.append("DATE(transactions.transaction_date) >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("DATE(transactions.transaction_date) <= ?")
        params.append(end_date)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY transactions.transaction_date DESC"
    
    c.execute(query, tuple(params))
    transactions = c.fetchall()
    
    conn.close()
    return render_template('transactions.html', transactions=transactions, 
                           search=search, start_date=start_date, end_date=end_date)

@app.route('/item/<int:id>/backup')
def backup_item_transactions(id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM items WHERE id = ?", (id,))
    item = c.fetchone()
    
    # Ambil parameter tanggal jika ada
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if start_date and end_date:
        c.execute('''SELECT * FROM transactions 
                    WHERE item_id = ? 
                    AND DATE(transaction_date) BETWEEN ? AND ?
                    ORDER BY transaction_date DESC''', 
                 (id, start_date, end_date))
    else:
        c.execute("SELECT * FROM transactions WHERE item_id = ? ORDER BY transaction_date DESC", (id,))
    
    transactions = c.fetchall()
    
    csv_data = StringIO()
    csv_writer = csv.writer(csv_data)
    
    csv_writer.writerow([
        'ID Transaksi', 'ID Barang', 'Nama Barang', 
        'Jenis Transaksi', 'Jumlah', 'Tanggal Transaksi', 'Keterangan'
    ])
    
    for trans in transactions:
        csv_writer.writerow([
            trans['id'],
            item['id'],
            item['name'],
            'MASUK' if trans['transaction_type'] == 'masuk' else 'KELUAR',
            trans['quantity'],
            trans['transaction_date'],
            trans['notes'] or ''
        ])
    
    conn.close()
    
    filename = f'transaksi_{item["name"]}_{datetime.now().strftime("%Y%m%d")}'
    if start_date and end_date:
        filename += f'_{start_date}_to_{end_date}'
    filename += '.csv'
    
    response = Response(
        csv_data.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment;filename={filename}'
        }
    )
    return response

if __name__ == '__main__':
    init_db()
    app.run(debug=True)