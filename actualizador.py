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
    from mensaje_api import registrar_nuevo_mensaje, obtener_mensajes_sala, marcar_leido, obtener_no_leidos
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

# ---------------------------------------------------------
# SERVIR INDEX.HTML
# ---------------------------------------------------------
@app.route('/')
def servir_index():
    return send_from_directory('.', 'INDEX.HTML')

# ---------------------------------------------------------
# RUTA 1: ACTUALIZACIÓN DE TAREAS
# ---------------------------------------------------------
@app.route('/actualizar_tareas', methods=['POST'])
def actualizar_tareas():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No se recibieron datos"}), 400

    socio_id = data.get('socio_id')
    cambios  = data.get('cambios')

    if not socio_id or not cambios:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400

    exitos = 0
    for id_tarea, nuevo_estado in cambios.items():
        query = "UPDATE checklist_items SET completado = ? WHERE id = ?"
        if ejecutar_db(query, (nuevo_estado, id_tarea)):
            exitos += 1
            logging.info(f"Socio ID {socio_id} - Tarea ID {id_tarea} - Estado: {nuevo_estado}")

    if exitos > 0:
        generar_json_para_safari()

    return jsonify({
        "status": "success",
        "mensaje": f"Procesado: {exitos} éxitos.",
        "actualizado": datetime.now().strftime("%H:%M:%S")
    })

# ---------------------------------------------------------
# RUTA 2: ENVIAR MENSAJE
# ---------------------------------------------------------
@app.route('/enviar_mensaje', methods=['POST'])
def api_enviar_mensaje():
    datos = request.get_json()
    exito = registrar_nuevo_mensaje(datos)
    if exito:
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"status": "error"}), 500

# ---------------------------------------------------------
# RUTA 3: OBTENER MENSAJES
# ---------------------------------------------------------
@app.route('/obtener_chat', methods=['GET'])
def api_obtener_chat():
    evento = request.args.get('evento')
    socio  = request.args.get('socio')
    target = request.args.get('target')
    mensajes = obtener_mensajes_sala(evento, socio, target)
    return jsonify(mensajes)

# ---------------------------------------------------------
# RUTA 4: MARCAR LEÍDO (se llama al abrir una conversación)
# ---------------------------------------------------------
@app.route('/marcar_leido', methods=['POST'])
def api_marcar_leido():
    datos     = request.get_json()
    evento_id = datos.get('evento_id')
    socio_id  = datos.get('socio_id')
    target_id = datos.get('target_id')
    exito = marcar_leido(evento_id, socio_id, target_id)
    if exito:
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"status": "error"}), 500

# ---------------------------------------------------------
# RUTA 5: OBTENER NO LEÍDOS (polling del badge)
# ---------------------------------------------------------
@app.route('/obtener_no_leidos', methods=['GET'])
def api_obtener_no_leidos():
    evento_id = request.args.get('evento')
    socio_id  = int(request.args.get('socio'))
    resultado = obtener_no_leidos(evento_id, socio_id)
    return jsonify(resultado)

# ---------------------------------------------------------
# INICIO DEL SERVIDOR
# ---------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
