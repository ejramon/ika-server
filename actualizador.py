from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import os
import logging
from datetime import datetime

# --- IMPORTACIÓN DE TUS APIS EXTERNAS ---
try:
    from exportador_api import generar_json_para_safari
except ImportError:
    def generar_json_para_safari():
        print("Aviso: No se pudo importar exportador_api.py.")

try:
    from mensaje_api import registrar_nuevo_mensaje, obtener_mensajes_sala
except ImportError:
    print("Error: No se encontró mensaje_api.py. El chat no funcionará.")

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app) 

DB_PATH = 'club_miembros.db'
LOG_FILE = 'registro_actividad.log'

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(message)s')

def ejecutar_db(query, params):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Error de base de datos: {e}")
        return False

# --- SERVIR EL FRONTEND ---
@app.route('/')
def servir_index():
    return send_from_directory('.', 'INDEX.HTML')

# --- RUTA PARA BLACKBELT (RECIBIR DB) ---
@app.route('/recibir_db', methods=['POST'])
def recibir_db():
    if 'file' not in request.files:
        return "No hay archivo", 400
    archivo = request.files['file']
    archivo.save(os.path.join('.', 'club_miembros.db'))
    return "Base de datos actualizada", 200

# --- RUTA PARA NOTIFICACIONES (BADGES) ---
@app.route('/obtener_no_leidos', methods=['GET'])
def api_no_leidos():
    # Simulación de respuesta para activar los badges en el INDEX
    # En una fase pro, aquí contarías los 'leido = 0' en club_chat.db
    return jsonify({"total": 0, "detalle": {}})

@app.route('/actualizar_tareas', methods=['POST'])
def actualizar_tareas():
    data = request.get_json()
    if not data: return jsonify({"status": "error"}), 400
    socio_id = data.get('socio_id')
    cambios = data.get('cambios')
    exitos = 0
    for id_tarea, nuevo_estado in cambios.items():
        query = "UPDATE checklist_items SET completado = ? WHERE id = ?"
        if ejecutar_db(query, (nuevo_estado, id_tarea)):
            exitos += 1
    if exitos > 0: generar_json_para_safari()
    return jsonify({"status": "success", "actualizado": datetime.now().strftime("%H:%M:%S")})

@app.route('/enviar_mensaje', methods=['POST'])
def api_enviar_mensaje():
    datos = request.get_json()
    exito = registrar_nuevo_mensaje(datos)
    return jsonify({"status": "ok"}) if exito else jsonify({"status": "error"}), 500

@app.route('/obtener_chat', methods=['GET'])
def api_obtener_chat():
    evento = request.args.get('evento')
    socio = request.args.get('socio')
    target = request.args.get('target')
    mensajes = obtener_mensajes_sala(evento, socio, target)
    return jsonify(mensajes)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
