from flask import Flask, request, jsonify
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

# IMPORTANTE: Cargamos las funciones de chat que definimos en mensaje_api.py
try:
    from mensaje_api import registrar_nuevo_mensaje, obtener_mensajes_sala
except ImportError:
    print("Error: No se encontró mensaje_api.py. El chat no funcionará.")

app = Flask(__name__)
CORS(app) 

DB_PATH = 'club_miembros.db'
LOG_FILE = 'registro_actividad.log'

# Configuración del LOG
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(message)s')

def ejecutar_db(query, params):
    """Maneja la conexión segura para las tareas (Checklist)"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Error de base de datos en tareas: {e}")
        return False

# ---------------------------------------------------------
# RUTA 1: ACTUALIZACIÓN DE TAREAS (CHECKLIST)
# ---------------------------------------------------------
@app.route('/actualizar_tareas', methods=['POST'])
def actualizar_tareas():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No se recibieron datos"}), 400

    socio_id = data.get('socio_id')
    cambios = data.get('cambios')

    if not socio_id or not cambios:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400

    exitos = 0
    for id_tarea, nuevo_estado in cambios.items():
        query = "UPDATE checklist_items SET completado = ? WHERE id = ?"
        if ejecutar_db(query, (nuevo_estado, id_tarea)):
            exitos += 1
            accion = "Marcada" if nuevo_estado == 1 else "Desmarcada"
            logging.info(f"Socio ID {socio_id} - Tarea ID {id_tarea} - Estado: {accion}")

    if exitos > 0:
        generar_json_para_safari()

    return jsonify({
        "status": "success",
        "mensaje": f"Procesado: {exitos} éxitos.",
        "actualizado": datetime.now().strftime("%H:%M:%S")
    })

# ---------------------------------------------------------
# RUTA 2: ENVIAR MENSAJES (API CHAT)
# ---------------------------------------------------------
@app.route('/enviar_mensaje', methods=['POST'])
def api_enviar_mensaje():
    datos = request.get_json()
    # Esta función vive en mensaje_api.py y escribe en club_chat.db
    exito = registrar_nuevo_mensaje(datos)
    if exito:
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"status": "error", "message": "No se pudo guardar el mensaje"}), 500

# ---------------------------------------------------------
# RUTA 3: OBTENER MENSAJES (API CHAT)
# ---------------------------------------------------------
@app.route('/obtener_chat', methods=['GET'])
def api_obtener_chat():
    evento = request.args.get('evento')
    socio = request.args.get('socio')
    target = request.args.get('target')
    
    # Esta función vive en mensaje_api.py y lee de club_chat.db
    mensajes = obtener_mensajes_sala(evento, socio, target)
    return jsonify(mensajes)

# ---------------------------------------------------------
# INICIO DEL SERVIDOR
# ---------------------------------------------------------
if __name__ == '__main__':
    # Usamos el puerto 5001 como configuraste en tu INDEX.HTML
    app.run(host='0.0.0.0', port=5001, debug=True)