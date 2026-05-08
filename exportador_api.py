import sqlite3
import json
import os

def generar_json_para_safari():
    nombre_db = 'club_miembros.db'
    if not os.path.exists(nombre_db):
        print(f"Error: No se encuentra el archivo {nombre_db}")
        return

    conn = sqlite3.connect(nombre_db)
    cursor = conn.cursor()

    try:
        # Consulta principal: Obtenemos la estructura de personas, eventos y roles
        query = """
        SELECT 
            m.cedula, 
            m.nombres || ' ' || m.apellidos as nombre_completo,
            m.id as socio_id,
            e.id as evento_id,
            e.nombre as evento_nombre,
            e.fecha as evento_fecha,
            j.rol as miembro_rol,
            j.coordinador_id,
            r.id as resp_id,
            r.descripcion as resp_desc,
            r.estado as resp_estado
        FROM miembros m
        JOIN jerarquia_roles j ON m.id = j.socio_id
        JOIN eventos e ON j.evento_id = e.id
        LEFT JOIN responsabilidades r ON (e.id = r.evento_id AND m.id = r.socio_id)
        """
        
        cursor.execute(query)
        filas = cursor.fetchall()

        data_sintetica = {}

        for fila in filas:
            cedula, nombre_completo, socio_id, ev_id, ev_nombre, ev_fecha, rol, sup_id, r_id, r_desc, r_estado = fila
            
            if cedula not in data_sintetica:
                data_sintetica[cedula] = {
                    "nombre": nombre_completo,
                    "socio_id": socio_id,
                    "eventos": {}
                }
            
            if ev_id not in data_sintetica[cedula]["eventos"]:
                data_sintetica[cedula]["eventos"][ev_id] = {
                    "titulo": ev_nombre,
                    "fecha": ev_fecha,
                    "rol": rol,
                    "superior_id": sup_id,
                    "responsabilidades": {}
                }
            
            if r_id is not None:
                # AJUSTE CRÍTICO: Ahora traemos el ID de la tarea (it[2])
                # Sin este ID, el iPhone no puede avisar qué tarea se completó
                cursor.execute("SELECT texto, completado, id FROM checklist_items WHERE responsabilidad_id = ?", (r_id,))
                items = cursor.fetchall()
                
                lista_items = []
                for it in items:
                    lista_items.append({
                        "tarea_texto": it[0], 
                        "esta_listo": it[1],
                        "id_tarea": it[2]  # <--- Esto es lo que el Actualizador usará como llave
                    })

                data_sintetica[cedula]["eventos"][ev_id]["responsabilidades"][r_id] = {
                    "titulo_resp": r_desc,
                    "estado_resp": r_estado,
                    "items_checklist": lista_items
                }

        # Guardado del JSON
        with open('data_servidor.json', 'w', encoding='utf-8') as f:
            json.dump(data_sintetica, f, indent=4, ensure_ascii=False)
        
        print(f"[{os.path.basename(__file__)}] data_servidor.json actualizado correctamente.")

    except sqlite3.Error as e:
        print(f"Error técnico en el exportador: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    generar_json_para_safari()