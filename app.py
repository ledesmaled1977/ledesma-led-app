# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from fpdf import FPDF
from datetime import datetime
import re
import sys
import pandas as pd
import io

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
app = Flask(__name__)
app.secret_key = 'MakroSurco2024-' 

# Configuración de MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'MakroSurco2024-'
app.config['MYSQL_DB'] = 'ledesma_led_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# --- TEST DE CONEXIÓN ---
with app.app_context():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT 1")
        cur.close()
        print(">>> Conexión a la base de datos exitosa.")
    except Exception as e:
        print("!!! ERROR DE CONEXIÓN CON LA BASE DE DATOS !!!", file=sys.stderr)
        print(f"!!! Error: {e}", file=sys.stderr)
        sys.exit(1)

# --- FUNCIÓN AUXILIAR PARA CODIFICAR TEXTO PARA PDF ---
def encode_text(text):
    """Codifica el texto a latin-1 reemplazando caracteres no soportados."""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

# --- CLASE PDF PROFESIONAL (VERSIÓN CORREGIDA FINAL) ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Creamos un atributo para pasarle el estado del IGV
        self.incluye_igv = False 

    def header(self):
        # --- ORDEN DE DIBUJO CORREGIDO ---
        # 1. PRIMERO: Dibujamos la franja de fondo en toda la página.
        try:
            self.image('static/img/pdf_background.png', 0, 0, 40, self.h)
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo cargar la imagen de fondo del PDF: {e}", file=sys.stderr)

        # 2. LUEGO: Dibujamos el logo y el texto ENCIMA del fondo.
        self.set_y(10)
        try:
            # El logo ahora se dibujará sobre la franja.
            self.image('static/img/logo.png', 15, 12, 33)
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo cargar el logo: {e}", file=sys.stderr)
        
        # Mover a la derecha del logo para la info de la empresa
        self.set_y(15)
        self.set_x(55)
        
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 7, 'Ledesma LED - Cotizacion', 0, 1, 'L')
        self.set_font('Helvetica', '', 9)
        self.set_x(55)
        self.cell(0, 5, 'RUC: 10105573281 (Cesar Antonio Ledesma Sanchez)', 0, 1, 'L')
        self.set_x(55)
        self.cell(0, 5, 'Jr. Tacna 121 - Urb. Cercado - Santiago de Surco, Lima, Peru', 0, 1, 'L')
        self.set_x(55)
        self.cell(0, 5, 'Celular: 941368586 | Correo: ledesmaled@hotmail.com', 0, 1, 'L')
        
        # Salto de línea para separar del cuerpo
        self.ln(15)

    def footer(self):
        self.set_y(-20) # Subimos un poco el footer para que quepan las dos líneas
        self.set_font('Helvetica', 'I', 8)
        
        # Texto del IGV que se obtiene del atributo que le pasamos
        igv_text = "La proforma SI incluye IGV" if self.incluye_igv else "La proforma NO incluye IGV"
        self.cell(0, 5, igv_text, 0, 1, 'C')

        # Cuenta bancaria
        self.set_font('Helvetica', '', 8)
        bcp_text = "Numero de Cuenta BCP: 194-38403786-0-01 (a nombre de Cesar Antonio Ledesma Sanchez)"
        self.cell(0, 5, bcp_text, 0, 1, 'C')
        
        # Número de página
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 5, f'Pagina {self.page_no()}', 0, 0, 'R')

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password'], password):
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            session['fullname'] = user['fullname']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Usuario o contraseña incorrectos")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        password = request.form['password']

        hashed_password = generate_password_hash(password)
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users (fullname, username, password) VALUES (%s, %s, %s)", (fullname, username, hashed_password))
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('login', success="Usuario registrado exitosamente"))
        except Exception as e:
            return render_template('register.html', error="El usuario ya existe o hubo un error.")
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- RUTAS DE LA APLICACIÓN ---
@app.route('/')
def dashboard():
    if 'loggedin' in session:
        user_id = session['id']
        cur = mysql.connection.cursor()
        
        cur.execute("SELECT COUNT(id) as total FROM proformas WHERE user_id = %s", [user_id])
        total_proformas = cur.fetchone()['total']
        
        cur.execute("SELECT SUM(monto_total) as total_monto FROM proformas WHERE user_id = %s", [user_id])
        total_monto_result = cur.fetchone()
        total_monto = total_monto_result['total_monto'] if total_monto_result['total_monto'] else 0
        
        cur.execute("SELECT id, cotizacion_nro, fecha, cliente, monto_total, incluye_igv, status FROM proformas WHERE user_id = %s ORDER BY id DESC", [session['id']])
        ultimas_proformas = cur.fetchall()
        
        cur.close()
        
        return render_template('dashboard.html', 
                               total_proformas=total_proformas, 
                               total_monto=total_monto,
                               ultimas_proformas=ultimas_proformas)
    return redirect(url_for('login'))

@app.route('/crear_proforma')
def crear_proforma():
    if 'loggedin' in session:
        return render_template('crear_proforma.html')
    return redirect(url_for('login'))

@app.route('/exito')
def exito():
    if 'loggedin' in session:
        proforma_id = request.args.get('id')
        return render_template('exito.html', proforma_id=proforma_id)
    return redirect(url_for('login'))

@app.route('/lista_proformas')
def lista_proformas():
    if 'loggedin' in session:
        return render_template('lista_proformas.html')
    return redirect(url_for('login'))

# --- NUEVA RUTA PARA DUPLICAR PROFORMAS ---
@app.route('/proforma/duplicar/<int:id>')
def duplicar_proforma(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()

        # 1. Obtener los datos de la proforma original
        cur.execute("SELECT * FROM proformas WHERE id = %s AND user_id = %s", (id, session['id']))
        proforma_original = cur.fetchone()

        if not proforma_original:
            return "Proforma no encontrada o sin permisos.", 404

        # 2. Obtener los items de la proforma original
        cur.execute("SELECT * FROM proforma_items WHERE proforma_id = %s", [id])
        items_originales = cur.fetchall()

        # 3. Obtener el siguiente número de cotización para la copia
        query_next_num = "SELECT MAX(CAST(cotizacion_nro AS UNSIGNED)) as max_num FROM proformas WHERE user_id = %s"
        cur.execute(query_next_num, [session['id']])
        max_num_result = cur.fetchone()
        next_number = (max_num_result['max_num'] or 0) + 1

        # 4. Crear la nueva proforma (la copia)
        cur.execute(
            """INSERT INTO proformas (user_id, cotizacion_nro, fecha, cliente, incluye_igv, monto_total, status) 
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                session['id'], 
                str(next_number), # Nuevo número
                datetime.now(), # Fecha de hoy
                proforma_original['cliente'] + " (Copia)", # Indicador de que es una copia
                proforma_original['incluye_igv'],
                proforma_original['monto_total'],
                'Enviada' # Estado por defecto
            )
        )
        nueva_proforma_id = cur.lastrowid

        # 5. Copiar todos los items a la nueva proforma
        for item in items_originales:
            cur.execute(
                """INSERT INTO proforma_items (proforma_id, item_descripcion, cantidad, precio_unitario)
                   VALUES (%s, %s, %s, %s)""",
                (nueva_proforma_id, item['item_descripcion'], item['cantidad'], item['precio_unitario'])
            )

        mysql.connection.commit()
        cur.close()

        # 6. Redirigir a la página de EDICIÓN de la nueva proforma
        return redirect(url_for('editar_proforma_page', id=nueva_proforma_id))

    except Exception as e:
        mysql.connection.rollback()
        print(f"Error al duplicar proforma: {e}", file=sys.stderr)
        return "Error interno al duplicar la proforma.", 500

# --- NUEVA RUTA PARA LA PÁGINA DE EDICIÓN ---
@app.route('/proforma/editar/<int:id>')
def editar_proforma_page(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    # Reutilizamos la plantilla de creación, pero le pasamos el ID
    # para que JavaScript sepa que estamos en modo edición.
    return render_template('crear_proforma.html', proforma_id=id)

# --- RUTAS DE API (DATOS) ---
@app.route('/api/proformas', methods=['POST'])
def api_crear_proforma():
    if 'loggedin' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    try:
        mysql.connection.ping()
        data = request.get_json()
        cur = mysql.connection.cursor()
        
        total = sum(float(item['precio_unitario']) * float(item['cantidad']) for item in data['items'])
        
        cur.execute(
            "INSERT INTO proformas (user_id, cotizacion_nro, fecha, cliente, incluye_igv, monto_total) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['id'], data['cotizacion_nro'], data['fecha'], data['cliente'], data['incluye_igv'], total)
        )
        proforma_id = cur.lastrowid

        for item in data['items']:
            cur.execute(
                "INSERT INTO proforma_items (proforma_id, item_descripcion, cantidad, precio_unitario) VALUES (%s, %s, %s, %s)",
                (proforma_id, item['item'], item['cantidad'], item['precio_unitario'])
            )
        
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True, "proforma_id": proforma_id})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "error": "Error interno del servidor."}), 500

@app.route('/api/proformas', methods=['GET'])
def api_obtener_proformas():
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    try:
        mysql.connection.ping()
        
        # --- Lógica Unificada de Paginación y Búsqueda ---
        page = request.args.get('page', 1, type=int)
        per_page = 10 # Proformas por página
        search_term = request.args.get('search', '')
        
        offset = (page - 1) * per_page
        
        # Construcción de la consulta base y los parámetros
        params = []
        
        # El SELECT ahora une las tablas desde el principio
        base_query = """
            FROM proformas p 
            JOIN users u ON p.user_id = u.id 
        """
        
        # El WHERE cambia según el rol y si hay búsqueda
        where_clauses = []
        if session.get('role') != 'admin':
            where_clauses.append("p.user_id = %s")
            params.append(session['id'])
        
        if search_term:
            where_clauses.append("(p.cliente LIKE %s OR p.cotizacion_nro LIKE %s)")
            params.extend([f"%{search_term}%", f"%{search_term}%"])

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)

        # --- Obtener el total de resultados para la paginación ---
        cur = mysql.connection.cursor()
        count_query = "SELECT COUNT(p.id) as total " + base_query
        cur.execute(count_query, params)
        total_results = cur.fetchone()['total']
        total_pages = (total_results + per_page - 1) // per_page

        # --- Obtener los resultados de la página actual ---
        data_query = "SELECT p.*, u.fullname as author " + base_query + " ORDER BY p.id DESC LIMIT %s OFFSET %s"
        final_params = params + [per_page, offset]
        cur.execute(data_query, final_params)
        
        # Convertir a lista para poder modificar
        proformas = list(cur.fetchall())

        # Procesar la lista obtenida
        for proforma in proformas:
            if proforma.get('fecha'):
                proforma['fecha'] = proforma['fecha'].strftime('%d/%m/%Y')
            if proforma.get('monto_total'):
                proforma['monto_total'] = float(proforma['monto_total'])
            
            if not proforma.get('author'):
                proforma['author'] = 'Usuario Eliminado'

            cur.execute("SELECT * FROM proforma_items WHERE proforma_id = %s", [proforma['id']])
            items = cur.fetchall()
            
            proforma['items'] = [
                {"item_descripcion": item['item_descripcion'], "cantidad": float(item['cantidad']), "precio_unitario": float(item['precio_unitario'])}
                for item in items
            ]
        
        cur.close()
        
        # Devolver tanto los datos como la información de paginación
        return jsonify({
            'proformas': proformas,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'total_results': total_results
            }
        })

    except Exception as e:
        print(f"Error en api_obtener_proformas: {e}", file=sys.stderr)
        return jsonify({"error": "Error al obtener las proformas"}), 500

@app.route('/api/proformas/<int:id>', methods=['DELETE'])
def api_eliminar_proforma(id):
    if 'loggedin' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
        
    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM proformas WHERE id = %s", [id])
        proforma = cur.fetchone()

        if not proforma or proforma['user_id'] != session['id']:
            return jsonify({"success": False, "error": "No tiene permiso para eliminar esta proforma."}), 403

        cur.execute("DELETE FROM proformas WHERE id = %s", [id])
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "error": "Error interno del servidor."}), 500

# --- RUTA DE GENERACIÓN DE PDF (VERSIÓN PROFESIONAL) ---
@app.route('/api/proforma/<int:id>/pdf')
def generar_pdf(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM proformas WHERE id = %s AND user_id = %s", (id, session['id']))
        proforma = cur.fetchone()
        
        if not proforma:
            return Response("Proforma no encontrada o no tiene permiso.", status=404, mimetype='text/plain')

        cur.execute("SELECT * FROM proforma_items WHERE proforma_id = %s", [id])
        items = cur.fetchall()
        cur.close()

        pdf = PDF()
        pdf.incluye_igv = proforma['incluye_igv']
        
        # add_page ahora se encarga de todo (fondo y header)
        pdf.add_page() 
        
        # Establecemos los márgenes para que el texto no quede debajo de la franja
        pdf.set_left_margin(45)
        pdf.set_right_margin(15)
        pdf.set_y(55) # Bajamos el cursor para empezar después del header

        # Datos del cliente
        pdf.set_font('Helvetica', '', 11)
        fecha_formateada = proforma['fecha'].strftime('%d/%m/%Y') if proforma.get('fecha') else ''
        pdf.cell(0, 7, f"Fecha: {fecha_formateada}", 0, 1)
        pdf.cell(0, 7, f"Cotizacion Nro: {proforma['cotizacion_nro']}", 0, 1)
        pdf.cell(0, 7, f"Cliente: {proforma['cliente']}", 0, 1)
        pdf.ln(5)

        # Mensaje de saludo
        pdf.set_font('Helvetica', 'I', 11)
        pdf.multi_cell(0, 7, "Estimado Cliente. Aqui le enviamos la proforma del trabajo a tratar.", 0, 'L')
        pdf.ln(5)

        # Tabla de items (con anchos ajustados)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(80, 10, 'Item', 1, 0, 'C')
        pdf.cell(20, 10, 'Cant.', 1, 0, 'C')
        pdf.cell(25, 10, 'P. Unit.', 1, 0, 'C')
        pdf.cell(25, 10, 'Costo', 1, 1, 'C')

        pdf.set_font('Helvetica', '', 10)
        subtotal = 0.0
        for item in items:
            costo = float(item['cantidad']) * float(item['precio_unitario'])
            subtotal += costo
            pdf.cell(80, 10, str(item['item_descripcion']), 1, 0)
            pdf.cell(20, 10, str(item['cantidad']), 1, 0, 'R')
            pdf.cell(25, 10, f"S/ {float(item['precio_unitario']):.2f}", 1, 0, 'R')
            pdf.cell(25, 10, f"S/ {costo:.2f}", 1, 1, 'R')
        
        pdf.ln(10)
        
        # Totales alineados a la derecha
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_x(100)
        pdf.cell(40, 10, 'SUBTOTAL:', 0, 0, 'R')
        pdf.cell(25, 10, f"S/ {subtotal:.2f}", 0, 1, 'R')
        
        total_final = subtotal
        if proforma['incluye_igv']:
            igv = subtotal * 0.18
            pdf.set_x(100)
            pdf.cell(40, 10, 'IGV (18%):', 0, 0, 'R')
            pdf.cell(25, 10, f"S/ {igv:.2f}", 0, 1, 'R')
            total_final += igv

        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_x(100)
        pdf.cell(40, 10, 'TOTAL:', 0, 0, 'R')
        pdf.cell(25, 10, f"S/ {total_final:.2f}", 0, 1, 'R')
        
        filename = f"proforma_{proforma['cotizacion_nro']}.pdf"
        sanitized_filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)
        
        return Response(bytes(pdf.output()), mimetype='application/pdf', headers={'Content-Disposition':f'attachment;filename={sanitized_filename}'})
    except Exception as e:
        print(f"Error al generar PDF para proforma {id}: {e}", file=sys.stderr)
        return Response("Error interno al generar el archivo PDF.", status=500, mimetype='text/plain')

# --- NUEVAS RUTAS PARA GESTIÓN DE CLIENTES ---

# Ruta para mostrar la página de gestión de clientes
@app.route('/clientes')
def clientes():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    return render_template('clientes.html')

# API para OBTENER todos los clientes del usuario logueado
@app.route('/api/clientes', methods=['GET'])
def api_obtener_clientes():
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401
    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM clientes WHERE user_id = %s ORDER BY nombre ASC", [session['id']])
        clientes = cur.fetchall()
        cur.close()
        return jsonify(clientes)
    except Exception as e:
        print(f"Error en api_obtener_clientes: {e}", file=sys.stderr)
        return jsonify({"error": "Error al obtener los clientes"}), 500

# API para CREAR un nuevo cliente
@app.route('/api/clientes', methods=['POST'])
def api_crear_cliente():
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401
    try:
        mysql.connection.ping()
        data = request.get_json()
        
        if not data or not data.get('nombre'):
            return jsonify({"success": False, "error": "El nombre es obligatorio"}), 400

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO clientes (user_id, nombre, ruc_dni, direccion, telefono, email) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['id'], data['nombre'], data.get('ruc_dni'), data.get('direccion'), data.get('telefono'), data.get('email'))
        )
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error en api_crear_cliente: {e}", file=sys.stderr)
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

# API para ACTUALIZAR un cliente existente
@app.route('/api/clientes/<int:id>', methods=['PUT'])
def api_actualizar_cliente(id):
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401
    try:
        mysql.connection.ping()
        data = request.get_json()
        if not data or not data.get('nombre'):
            return jsonify({"success": False, "error": "El nombre es obligatorio"}), 400

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM clientes WHERE id = %s AND user_id = %s", (id, session['id']))
        if not cur.fetchone():
            return jsonify({"success": False, "error": "Cliente no encontrado o sin permisos"}), 404

        cur.execute(
            """UPDATE clientes SET nombre = %s, ruc_dni = %s, direccion = %s, telefono = %s, email = %s
               WHERE id = %s""",
            (data['nombre'], data.get('ruc_dni'), data.get('direccion'), data.get('telefono'), data.get('email'), id)
        )
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error en api_actualizar_cliente: {e}", file=sys.stderr)
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

# API para ELIMINAR un cliente
@app.route('/api/clientes/<int:id>', methods=['DELETE'])
def api_eliminar_cliente(id):
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401
    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM clientes WHERE id = %s AND user_id = %s", (id, session['id']))
        if not cur.fetchone():
            return jsonify({"success": False, "error": "Cliente no encontrado o sin permisos"}), 404
        
        cur.execute("DELETE FROM clientes WHERE id = %s", [id])
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error en api_eliminar_cliente: {e}", file=sys.stderr)
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

# --- NUEVAS RUTAS API PARA EDICIÓN ---

# API para OBTENER los datos de UNA proforma específica por su ID
@app.route('/api/proforma/<int:id>', methods=['GET'])
def api_obtener_proforma_por_id(id):
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        
        cur.execute("SELECT * FROM proformas WHERE id = %s AND user_id = %s", (id, session['id']))
        proforma = cur.fetchone()

        if not proforma:
            return jsonify({"error": "Proforma no encontrada o sin permisos"}), 404

        cur.execute("SELECT * FROM proforma_items WHERE proforma_id = %s", [id])
        items = cur.fetchall()
        cur.close()

        proforma['fecha'] = proforma['fecha'].strftime('%Y-%m-%d')
        proforma['monto_total'] = float(proforma['monto_total'])
        proforma['items'] = [
            {
                "item": item['item_descripcion'],
                "cantidad": float(item['cantidad']),
                "precio_unitario": float(item['precio_unitario'])
            } for item in items
        ]
        
        return jsonify(proforma)
    except Exception as e:
        print(f"Error en api_obtener_proforma_por_id: {e}", file=sys.stderr)
        return jsonify({"error": "Error al obtener los datos de la proforma"}), 500

# API para ACTUALIZAR (PUT) una proforma existente
@app.route('/api/proformas/<int:id>', methods=['PUT'])
def api_actualizar_proforma(id):
    if 'loggedin' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    try:
        mysql.connection.ping()
        data = request.get_json()
        cur = mysql.connection.cursor()

        cur.execute("SELECT user_id FROM proformas WHERE id = %s", [id])
        proforma_owner = cur.fetchone()
        if not proforma_owner or proforma_owner['user_id'] != session['id']:
            return jsonify({"success": False, "error": "Permiso denegado"}), 403

        nuevo_total = sum(float(item['precio_unitario']) * float(item['cantidad']) for item in data['items'])
        cur.execute(
            """UPDATE proformas SET cotizacion_nro = %s, fecha = %s, cliente = %s, incluye_igv = %s, monto_total = %s
               WHERE id = %s""",
            (data['cotizacion_nro'], data['fecha'], data['cliente'], data['incluye_igv'], nuevo_total, id)
        )

        cur.execute("DELETE FROM proforma_items WHERE proforma_id = %s", [id])
        for item in data['items']:
            cur.execute(
                "INSERT INTO proforma_items (proforma_id, item_descripcion, cantidad, precio_unitario) VALUES (%s, %s, %s, %s)",
                (id, item['item'], item['cantidad'], item['precio_unitario'])
            )
        
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True, "proforma_id": id})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error en api_actualizar_proforma: {e}", file=sys.stderr)
        return jsonify({"success": False, "error": "Error interno del servidor al actualizar."}), 500

# --- NUEVA RUTA API PARA AUTOCOMPLETADO DE CLIENTES ---
@app.route('/api/clientes/search')
def api_search_clientes():
    if 'loggedin' not in session:
        return jsonify([]), 401
    
    search_term = request.args.get('term', '')
    if not search_term:
        return jsonify([])

    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        # Busca clientes cuyo nombre COMIENCE CON el término de búsqueda
        query = "SELECT id, nombre, ruc_dni, direccion, telefono, email FROM clientes WHERE user_id = %s AND nombre LIKE %s LIMIT 10"
        # El '%%' es para que SQL busque coincidencias parciales
        like_term = f"{search_term}%"
        cur.execute(query, (session['id'], like_term))
        clientes = cur.fetchall()
        cur.close()
        return jsonify(clientes)
    except Exception as e:
        print(f"Error en api_search_clientes: {e}", file=sys.stderr)
        return jsonify([]), 500

# --- NUEVA RUTA API PARA VISTA PREVIA DE PDF (VERSIÓN COMPLETA Y CORREGIDA) ---
@app.route('/api/proforma/<int:id>/preview')
def preview_pdf(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM proformas WHERE id = %s AND user_id = %s", (id, session['id']))
        proforma = cur.fetchone()
        
        if not proforma:
            return Response("Proforma no encontrada o no tiene permiso.", status=404, mimetype='text/plain')

        cur.execute("SELECT * FROM proforma_items WHERE proforma_id = %s", [id])
        items = cur.fetchall()
        cur.close()

        pdf = PDF()
        pdf.incluye_igv = proforma['incluye_igv']
        pdf.add_page()
        
        # Mover el contenido a la derecha de la franja
        pdf.set_left_margin(45)
        pdf.set_right_margin(15)
        pdf.set_y(55) # Bajar el cursor para empezar después del header

        # Datos del cliente
        pdf.set_font('Helvetica', '', 11)
        fecha_formateada = proforma['fecha'].strftime('%d/%m/%Y') if proforma.get('fecha') else ''
        pdf.cell(0, 7, f"Fecha: {fecha_formateada}", 0, 1)
        pdf.cell(0, 7, f"Cotizacion Nro: {proforma['cotizacion_nro']}", 0, 1)
        pdf.cell(0, 7, f"Cliente: {proforma['cliente']}", 0, 1)
        pdf.ln(5)

        # Mensaje de saludo
        pdf.set_font('Helvetica', 'I', 11)
        pdf.multi_cell(0, 7, "Estimado Cliente. Aqui le enviamos la proforma del trabajo a tratar.", 0, 'L')
        pdf.ln(5)

        # Tabla de items
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(80, 10, 'Item', 1, 0, 'C')
        pdf.cell(20, 10, 'Cant.', 1, 0, 'C')
        pdf.cell(25, 10, 'P. Unit.', 1, 0, 'C')
        pdf.cell(25, 10, 'Costo', 1, 1, 'C')

        pdf.set_font('Helvetica', '', 10)
        subtotal = 0.0
        for item in items:
            costo = float(item['cantidad']) * float(item['precio_unitario'])
            subtotal += costo
            pdf.cell(80, 10, str(item['item_descripcion']), 1, 0)
            pdf.cell(20, 10, str(item['cantidad']), 1, 0, 'R')
            pdf.cell(25, 10, f"S/ {float(item['precio_unitario']):.2f}", 1, 0, 'R')
            pdf.cell(25, 10, f"S/ {costo:.2f}", 1, 1, 'R')
        
        pdf.ln(10)
        
        # Totales
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_x(100)
        pdf.cell(40, 10, 'SUBTOTAL:', 0, 0, 'R')
        pdf.cell(25, 10, f"S/ {subtotal:.2f}", 0, 1, 'R')
        
        total_final = subtotal
        if proforma['incluye_igv']:
            igv = subtotal * 0.18
            pdf.set_x(100)
            pdf.cell(40, 10, 'IGV (18%):', 0, 0, 'R')
            pdf.cell(25, 10, f"S/ {igv:.2f}", 0, 1, 'R')
            total_final += igv

        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_x(100)
        pdf.cell(40, 10, 'TOTAL:', 0, 0, 'R')
        pdf.cell(25, 10, f"S/ {total_final:.2f}", 0, 1, 'R')
        
        filename = f"proforma_{proforma['cotizacion_nro']}.pdf"
        sanitized_filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)
        
        # La única diferencia clave: 'inline' para ver, 'attachment' para descargar
        return Response(bytes(pdf.output()), mimetype='application/pdf', headers={'Content-Disposition':f'inline; filename={sanitized_filename}'})
    except Exception as e:
        print(f"Error al generar vista previa de PDF para proforma {id}: {e}", file=sys.stderr)
        return Response("Error interno al generar el archivo PDF.", status=500, mimetype='text/plain')

# --- NUEVA RUTA API PARA ACTUALIZAR ESTADO ---
@app.route('/api/proformas/<int:id>/status', methods=['PUT'])
def api_actualizar_status(id):
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401

    try:
        nuevo_status = request.get_json().get('status')
        if nuevo_status not in ['Enviada', 'Aprobada', 'Rechazada']:
            return jsonify({"success": False, "error": "Estado no válido"}), 400

        mysql.connection.ping()
        cur = mysql.connection.cursor()
        # Verificación de permiso
        cur.execute("UPDATE proformas SET status = %s WHERE id = %s AND user_id = %s", (nuevo_status, id, session['id']))
        mysql.connection.commit()

        if cur.rowcount == 0: # Si no se actualizó ninguna fila, el usuario no tiene permiso
             return jsonify({"success": False, "error": "Proforma no encontrada o sin permisos"}), 404

        cur.close()
        return jsonify({"success": True, "new_status": nuevo_status})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error al actualizar estado: {e}", file=sys.stderr)
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

# --- NUEVA RUTA API PARA ESTADÍSTICAS DEL DASHBOARD ---
@app.route('/api/dashboard_stats')
def dashboard_stats():
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401

    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        # Contar proformas por mes en el último año
        query = """
            SELECT DATE_FORMAT(fecha, '%%Y-%%m') AS mes, COUNT(id) AS cantidad
            FROM proformas
            WHERE user_id = %s AND fecha >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
            GROUP BY mes
            ORDER BY mes ASC;
        """
        cur.execute(query, [session['id']])
        stats = cur.fetchall()
        cur.close()

        labels = [row['mes'] for row in stats]
        data = [row['cantidad'] for row in stats]

        return jsonify({"labels": labels, "data": data})
    except Exception as e:
        print(f"Error en dashboard_stats: {e}", file=sys.stderr)
        return jsonify({"error": "Error al obtener estadísticas"}), 500

# --- NUEVA RUTA API PARA EXPORTAR A EXCEL ---
@app.route('/api/proformas/export')
def export_proformas_excel():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        
        # Usamos la misma consulta optimizada que para la lista
        sql = """
            SELECT 
                p.id, p.cotizacion_nro, p.fecha, p.cliente, p.monto_total, p.incluye_igv, p.status,
                pi.item_descripcion, pi.cantidad, pi.precio_unitario
            FROM 
                proformas p
            LEFT JOIN 
                proforma_items pi ON p.id = pi.proforma_id
            WHERE p.user_id = %s
            ORDER BY 
                p.id DESC, pi.id ASC
        """
        cur.execute(sql, [session['id']])
        results = cur.fetchall()
        cur.close()

        # Preparamos los datos para un formato plano de Excel
        data_for_excel = []
        for row in results:
            data_for_excel.append({
                'Nro Proforma': row['cotizacion_nro'],
                'Fecha': row['fecha'].strftime('%Y-%m-%d') if row['fecha'] else '',
                'Cliente': row['cliente'],
                'Estado': row['status'],
                'Item': row['item_descripcion'],
                'Cantidad': row['cantidad'],
                'Precio Unitario': row['precio_unitario'],
                'Monto Total Proforma': row['monto_total'],
                'Incluye IGV': 'Sí' if row['incluye_igv'] else 'No'
            })

        if not data_for_excel:
            return "No hay datos para exportar.", 404

        # Usamos Pandas para crear el archivo de Excel en memoria
        df = pd.DataFrame(data_for_excel)
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='Proformas')
        writer.close()
        output.seek(0)

        # Preparamos la respuesta para que el navegador la descargue
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment;filename=reporte_proformas.xlsx"}
        )

    except Exception as e:
        print(f"Error al exportar a Excel: {e}", file=sys.stderr)
        return "Error al generar el archivo Excel.", 500

# --- NUEVA RUTA API PARA OBTENER EL SIGUIENTE NÚMERO DE PROFORMA ---
@app.route('/api/proformas/next_number')
def api_next_proforma_number():
    if 'loggedin' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    try:
        mysql.connection.ping()
        cur = mysql.connection.cursor()
        
        # Se busca el valor numérico más alto en la columna cotizacion_nro
        query = """
            SELECT MAX(CAST(cotizacion_nro AS UNSIGNED)) as max_num 
            FROM proformas 
            WHERE user_id = %s
        """
        cur.execute(query, [session['id']])
        result = cur.fetchone()
        cur.close()

        if result and result['max_num']:
            next_number = result['max_num'] + 1
        else:
            next_number = 1 # Si no hay proformas, empezamos en 1

        return jsonify({'next_number': next_number})
    except Exception as e:
        print(f"Error en api_next_proforma_number: {e}", file=sys.stderr)
        return jsonify({"error": "Error al obtener el número de proforma"}), 500

if __name__ == '__main__':
    app.run(debug=True)





