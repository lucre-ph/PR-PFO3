import argparse
import concurrent.futures
import hashlib
import hmac
import json
import secrets
import socket
import sqlite3
import threading
from datetime import datetime

# Nueva nomenclatura para las constantes globales
HOST_IP = "127.0.0.1"
PORT_NUM = 5001
WORKER_THREADS = 4
DB_NAME = "tareas.db"

lock_db = threading.Lock()


def preparar_base_datos():
    with sqlite3.connect(DB_NAME) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                contrasena_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tareas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                descripcion TEXT NOT NULL,
                creada_en TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            );
            """
        )
        columnas = {
            col[1] for col in conexion.execute("PRAGMA table_info(usuarios)").fetchall()
        }
        if "salt" not in columnas:
            conexion.execute("ALTER TABLE usuarios ADD COLUMN salt TEXT NOT NULL DEFAULT ''")
        conexion.commit()


def cifrar_password(password, salt=None):
    valor_salt = salt or secrets.token_hex(16)
    hash_resultado = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), valor_salt.encode("utf-8"), 100_000
    ).hex()
    return valor_salt, hash_resultado


def comprobar_password(password, salt, expected_hash):
    _, hash_actual = cifrar_password(password, salt)
    return hmac.compare_digest(hash_actual, expected_hash)


def respuesta_exitosa(**datos):
    out = {"ok": True}
    out.update(datos)
    return out


def respuesta_fallida(mensaje_error):
    return {"ok": False, "error": mensaje_error}


def extraer_campo_texto(datos_req, llave):
    texto = datos_req.get(llave)
    if not isinstance(texto, str) or not texto.strip():
        return None
    return texto.strip()


def verificar_usuario(conexion, nombre_usuario, clave):
    registro = conexion.execute(
        "SELECT id, salt, contrasena_hash FROM usuarios WHERE usuario = ?",
        (nombre_usuario,),
    ).fetchone()
    if registro is None:
        return None

    u_id, salt_usuario, hash_almacenado = registro
    if not comprobar_password(clave, salt_usuario, hash_almacenado):
        return None

    return u_id


def registrar_nuevo_usuario(datos_req):
    usr = extraer_campo_texto(datos_req, "usuario")
    pwd = extraer_campo_texto(datos_req, "contrasena")

    if usr is None or pwd is None:
        return respuesta_fallida("Se requieren 'usuario' y 'contrasena'.")
    if len(usr) < 3:
        return respuesta_fallida("El usuario debe tener al menos 3 caracteres.")
    if len(pwd) < 4:
        return respuesta_fallida("La contrasena debe tener al menos 4 caracteres.")

    salt, p_hash = cifrar_password(pwd)
    try:
        with lock_db, sqlite3.connect(DB_NAME) as conexion:
            conexion.execute(
                """
                INSERT INTO usuarios (usuario, salt, contrasena_hash)
                VALUES (?, ?, ?)
                """,
                (usr, salt, p_hash),
            )
            conexion.commit()
    except sqlite3.IntegrityError:
        return respuesta_fallida("El usuario ya existe.")

    return respuesta_exitosa(mensaje=f"Usuario '{usr}' registrado exitosamente.")


def iniciar_sesion_usuario(datos_req):
    usr = extraer_campo_texto(datos_req, "usuario")
    pwd = extraer_campo_texto(datos_req, "contrasena")

    if usr is None or pwd is None:
        return respuesta_fallida("Se requieren 'usuario' y 'contrasena'.")

    with sqlite3.connect(DB_NAME) as conexion:
        id_usuario = verificar_usuario(conexion, usr, pwd)

    if id_usuario is None:
        return respuesta_fallida("Credenciales invalidas.")

    return respuesta_exitosa(mensaje=f"Bienvenido, {usr}!")


def obligar_autenticacion(datos_req):
    usr = extraer_campo_texto(datos_req, "usuario")
    pwd = extraer_campo_texto(datos_req, "contrasena")

    if usr is None or pwd is None:
        return None, respuesta_fallida("Necesitas iniciar sesion primero.")

    with sqlite3.connect(DB_NAME) as conexion:
        id_usuario = verificar_usuario(conexion, usr, pwd)

    if id_usuario is None:
        return None, respuesta_fallida("Credenciales invalidas.")

    return id_usuario, None


def agregar_nueva_tarea(datos_req):
    id_usuario, err_auth = obligar_autenticacion(datos_req)
    if err_auth:
        return err_auth

    desc = extraer_campo_texto(datos_req, "descripcion")
    if desc is None:
        return respuesta_fallida("Se requiere 'descripcion'.")

    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with lock_db, sqlite3.connect(DB_NAME) as conexion:
        cursor_db = conexion.execute(
            """
            INSERT INTO tareas (usuario_id, descripcion, creada_en)
            VALUES (?, ?, ?)
            """,
            (id_usuario, desc, fecha_creacion),
        )
        conexion.commit()

    return respuesta_exitosa(
        mensaje="Tarea creada.",
        tarea={"id": cursor_db.lastrowid, "descripcion": desc, "creada_en": fecha_creacion},
    )


def consultar_tareas_usuario(datos_req):
    id_usuario, err_auth = obligar_autenticacion(datos_req)
    if err_auth:
        return err_auth

    with sqlite3.connect(DB_NAME) as conexion:
        conexion.row_factory = sqlite3.Row
        filas = conexion.execute(
            """
            SELECT id, descripcion, creada_en
            FROM tareas
            WHERE usuario_id = ?
            ORDER BY id
            """,
            (id_usuario,),
        ).fetchall()

    return respuesta_exitosa(tareas=[dict(f) for f in filas])


def borrar_tarea_usuario(datos_req):
    id_usuario, err_auth = obligar_autenticacion(datos_req)
    if err_auth:
        return err_auth

    id_tarea = datos_req.get("id")
    if not isinstance(id_tarea, int):
        return respuesta_fallida("Se requiere un 'id' numerico.")

    with lock_db, sqlite3.connect(DB_NAME) as conexion:
        cursor_db = conexion.execute(
            "DELETE FROM tareas WHERE id = ? AND usuario_id = ?",
            (id_tarea, id_usuario),
        )
        conexion.commit()

    if cursor_db.rowcount == 0:
        return respuesta_fallida("Tarea no encontrada o no te pertenece.")

    return respuesta_exitosa(mensaje=f"Tarea #{id_tarea} eliminada.")


def atender_peticion(datos_req):
    operacion = datos_req.get("accion")
    rutas = {
        "registrar": registrar_nuevo_usuario,
        "login": iniciar_sesion_usuario,
        "crear_tarea": agregar_nueva_tarea,
        "listar_tareas": consultar_tareas_usuario,
        "eliminar_tarea": borrar_tarea_usuario,
    }

    ejecutor = rutas.get(operacion)
    if ejecutor is None:
        return respuesta_fallida("Accion no reconocida.")

    return ejecutor(datos_req)


def despachar_json(descriptor_archivo, objeto_respuesta):
    descriptor_archivo.write(json.dumps(objeto_respuesta, ensure_ascii=False).encode("utf-8") + b"\n")
    descriptor_archivo.flush()


def gestionar_cliente(canal_conexion, info_red, grupo_hilos):
    print(f"[CONEXIÓN] Remoto: {info_red[0]}:{info_red[1]}")
    with canal_conexion:
        flujo_archivo = canal_conexion.makefile("rwb")
        for linea_cruda in flujo_archivo:
            try:
                datos_entrada = json.loads(linea_cruda.decode("utf-8"))
                promesa = grupo_hilos.submit(atender_peticion, datos_entrada)
                salida_json = promesa.result()
            except json.JSONDecodeError:
                salida_json = respuesta_fallida("El mensaje recibido no es JSON valido.")
            except Exception as error_servidor:
                salida_json = respuesta_fallida(f"Error interno del servidor: {error_servidor}")

            despachar_json(flujo_archivo, salida_json)

    print(f"[DESCONEXIÓN] Remoto: {info_red[0]}:{info_red[1]}")


def encender_servidor(ip, puerto, max_hilos):
    preparar_base_datos()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_hilos) as pool_trabajadores:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_escucha:
            socket_escucha.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socket_escucha.bind((ip, puerto))
            socket_escucha.listen()

            print(f"-> Servidor activo en Puerto: {puerto} (Host: {ip})")
            print(f"-> Pool configurado con {max_hilos} hilos de procesamiento.")

            while True:
                conexion_cliente, direccion_cliente = socket_escucha.accept()
                hilo_atencion = threading.Thread(
                    target=gestionar_cliente,
                    args=(conexion_cliente, direccion_cliente, pool_trabajadores),
                    daemon=True,
                )
                hilo_atencion.start()


def lectura_argumentos():
    analizador = argparse.ArgumentParser(
        description="Servidor TCP para gestion distribuida de tareas."
    )
    analizador.add_argument("--host", default=HOST_IP)
    analizador.add_argument("--port", type=int, default=PORT_NUM)
    analizador.add_argument("--workers", type=int, default=WORKER_THREADS)
    return analizador.parse_args()


if __name__ == "__main__":
    argumentos = lectura_argumentos()
    encender_servidor(argumentos.host, argumentos.port, argumentos.workers)