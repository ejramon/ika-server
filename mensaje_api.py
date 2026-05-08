import sqlite3
import os
from datetime import datetime

DB_CHAT = 'club_chat.db'

def conectar_chat():
    """Establece conexión con la base de datos de mensajes."""
    return sqlite3.connect(DB_CHAT, timeout=10)

def obtener_mensajes_sala(evento_id, socio_id, target_id):
    """
    Recupera el historial basándose en la tabla 'conversaciones' y 'mensajes' de club_chat.db
    """
    conn = conectar_chat()
    cursor = conn.cursor()
    
    try:
        if target_id == 'GENERAL':
            # Chat grupal: unimos con la tabla conversaciones donde tipo es 'grupal'
            query = """
                SELECT m.remitente_nombre, m.texto, m.timestamp 
                FROM mensajes m
                JOIN conversaciones c ON m.conversacion_id = c.id
                WHERE m.evento_id = ? AND c.tipo_conv = 'grupal'
                ORDER BY m.timestamp ASC
            """
            cursor.execute(query, (evento_id,))
        else:
            # Chat privado: buscamos la conversacion individual entre los dos socios
            query = """
                SELECT m.remitente_nombre, m.texto, m.timestamp 
                FROM mensajes m
                JOIN conversaciones c ON m.conversacion_id = c.id
                WHERE m.evento_id = ? AND c.tipo_conv = 'individual'
                AND ((c.participante_a = ? AND c.participante_b = ?) 
                     OR (c.participante_a = ? AND c.participante_b = ?))
                ORDER BY m.timestamp ASC
            """
            cursor.execute(query, (evento_id, socio_id, target_id, target_id, socio_id))
        
        columnas = [col[0] for col in cursor.description]
        resultado = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return resultado

    except sqlite3.Error as e:
        print(f"Error recuperando mensajes: {e}")
        return []
    finally:
        conn.close()

def registrar_nuevo_mensaje(datos):
    """
    Inserta un mensaje enviado desde el celular cumpliendo con las reglas
    de las tablas 'conversaciones' y 'mensajes'.
    """
    conn = conectar_chat()
    cursor = conn.cursor()
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    evento_id = datos['evento_id']
    remitente_nombre = datos['remitente_nombre']
    socio_id = datos['remitente_id']
    target_id = datos.get('receptor_id')
    texto = datos['texto']
    
    try:
        conversacion_id = None
        destinatario_id = None
        
        # 1. Encontrar o crear el ID de la conversacion (Obligatorio en tu BD)
        if target_id == 'GENERAL':
            cursor.execute("SELECT id FROM conversaciones WHERE evento_id = ? AND tipo_conv = 'grupal'", (evento_id,))
            row = cursor.fetchone()
            if row:
                conversacion_id = row[0]
            else:
                cursor.execute("INSERT INTO conversaciones (evento_id, nombre_conv, tipo_conv, participante_a) VALUES (?, 'Chat Grupal', 'grupal', ?)", (evento_id, socio_id))
                conversacion_id = cursor.lastrowid
        else:
            destinatario_id = target_id
            cursor.execute("""
                SELECT id FROM conversaciones 
                WHERE evento_id = ? AND tipo_conv = 'individual'
                AND ((participante_a = ? AND participante_b = ?) OR (participante_a = ? AND participante_b = ?))
            """, (evento_id, socio_id, target_id, target_id, socio_id))
            row = cursor.fetchone()
            if row:
                conversacion_id = row[0]
            else:
                cursor.execute("""
                    INSERT INTO conversaciones (evento_id, nombre_conv, tipo_conv, participante_a, participante_b) 
                    VALUES (?, 'Privado', 'individual', ?, ?)
                """, (evento_id, socio_id, target_id))
                conversacion_id = cursor.lastrowid

        # 2. Insertar el mensaje usando los campos reales de tu BD
        query = """
            INSERT INTO mensajes (conversacion_id, evento_id, remitente_nombre, 
                                 destinatario_id, texto, timestamp, leido, borrado)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        """
        cursor.execute(query, (
            conversacion_id,
            evento_id,
            remitente_nombre,
            destinatario_id,
            texto,
            fecha_actual
        ))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error crítico en BD al registrar mensaje: {e}")
        return False
    finally:
        conn.close()