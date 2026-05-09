import sqlite3
import os
from datetime import datetime

DB_CHAT = 'club_chat.db'

def conectar_chat():
    return sqlite3.connect(DB_CHAT, timeout=10)

def obtener_mensajes_sala(evento_id, socio_id, target_id):
    conn = conectar_chat()
    cursor = conn.cursor()
    try:
        if target_id == 'GENERAL':
            query = """
                SELECT m.remitente_nombre, m.texto, m.timestamp 
                FROM mensajes m
                JOIN conversaciones c ON m.conversacion_id = c.id
                WHERE m.evento_id = ? AND c.tipo_conv = 'grupal'
                ORDER BY m.timestamp ASC
            """
            cursor.execute(query, (evento_id,))
        else:
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
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Error recuperando mensajes: {e}")
        return []
    finally:
        conn.close()

def registrar_nuevo_mensaje(datos):
    conn = conectar_chat()
    cursor = conn.cursor()
    from datetime import datetime, timezone, timedelta
    ecuador = timezone(timedelta(hours=-5))
    fecha_actual = datetime.now(ecuador).strftime("%Y-%m-%d %H:%M:%S")
    evento_id        = datos['evento_id']
    remitente_nombre = datos['remitente_nombre']
    socio_id         = datos['remitente_id']
    target_id        = datos.get('receptor_id')
    texto            = datos['texto']
    try:
        conversacion_id = None
        destinatario_id = None
        if target_id == 'GENERAL':
            cursor.execute("SELECT id FROM conversaciones WHERE evento_id = ? AND tipo_conv = 'grupal'", (evento_id,))
            row = cursor.fetchone()
            if row:
                conversacion_id = row[0]
            else:
                cursor.execute("INSERT INTO conversaciones (evento_id, nombre_conv, tipo_conv, participante_a) VALUES (?, 'Chat Grupal', 'grupal', ?)", (evento_id, socio_id))
                conversacion_id = cursor.lastrowid
        else:
            destinatario_id = int(target_id)
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
        cursor.execute("""
            INSERT INTO mensajes (conversacion_id, evento_id, remitente_nombre, 
                                 destinatario_id, texto, timestamp, leido, borrado)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        """, (conversacion_id, evento_id, remitente_nombre, destinatario_id, texto, fecha_actual))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error crítico en BD al registrar mensaje: {e}")
        return False
    finally:
        conn.close()

def marcar_leido(evento_id, socio_id, target_id):
    """Marca leídos los mensajes privados o registra visita al grupal."""
    conn = conectar_chat()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if target_id == 'GENERAL':
            cursor.execute(
                "SELECT id FROM conversaciones WHERE evento_id = ? AND tipo_conv = 'grupal'",
                (evento_id,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    INSERT INTO ultima_lectura (socio_id, conversacion_id, visto_en)
                    VALUES (?, ?, ?)
                    ON CONFLICT(socio_id, conversacion_id) DO UPDATE SET visto_en = excluded.visto_en
                """, (socio_id, row[0], ahora))
        else:
            cursor.execute("""
                UPDATE mensajes SET leido = 1
                WHERE evento_id = ?
                  AND destinatario_id = ?
                  AND conversacion_id IN (
                      SELECT id FROM conversaciones
                      WHERE tipo_conv = 'individual'
                        AND ((participante_a = ? AND participante_b = ?)
                             OR (participante_a = ? AND participante_b = ?))
                  )
                  AND leido = 0
            """, (evento_id, socio_id, socio_id, int(target_id), int(target_id), socio_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error marcando como leído: {e}")
        return False
    finally:
        conn.close()

def obtener_no_leidos(evento_id, socio_id):
    """Devuelve { total, detalle } con mensajes sin leer por conversación."""
    conn = conectar_chat()
    cursor = conn.cursor()
    detalle = {}
    total   = 0
    try:
        # ── GRUPAL: hay algo nuevo desde la última visita? ──
        cursor.execute(
            "SELECT id FROM conversaciones WHERE evento_id = ? AND tipo_conv = 'grupal'",
            (evento_id,)
        )
        row = cursor.fetchone()
        if row:
            conv_id_grupal = row[0]
            cursor.execute(
                "SELECT visto_en FROM ultima_lectura WHERE socio_id = ? AND conversacion_id = ?",
                (socio_id, conv_id_grupal)
            )
            lectura = cursor.fetchone()
            if lectura:
                cursor.execute("""
                    SELECT COUNT(*) FROM mensajes
                    WHERE conversacion_id = ? AND timestamp > ? AND borrado = 0
                """, (conv_id_grupal, lectura[0]))
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM mensajes WHERE conversacion_id = ? AND borrado = 0",
                    (conv_id_grupal,)
                )
            if cursor.fetchone()[0] > 0:
                detalle['GENERAL'] = 1
                total += 1

        # ── INDIVIDUALES: mensajes dirigidos a mí sin leer ──
        cursor.execute("""
            SELECT c.participante_a, c.participante_b, COUNT(m.id)
            FROM conversaciones c
            JOIN mensajes m ON m.conversacion_id = c.id
            WHERE c.evento_id = ?
              AND c.tipo_conv = 'individual'
              AND (c.participante_a = ? OR c.participante_b = ?)
              AND m.destinatario_id = ?
              AND m.leido = 0
              AND m.borrado = 0
            GROUP BY c.id
        """, (evento_id, socio_id, socio_id, socio_id))
        for part_a, part_b, count in cursor.fetchall():
            otro = part_b if part_a == socio_id else part_a
            if otro is not None and count > 0:
                detalle[str(otro)] = count
                total += count

        return {'total': total, 'detalle': detalle}
    except sqlite3.Error as e:
        print(f"Error obteniendo no leídos: {e}")
        return {'total': 0, 'detalle': {}}
    finally:
        conn.close()
