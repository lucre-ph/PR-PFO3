import argparse
import json
import socket

REMOTE_HOST = "127.0.0.1"
REMOTE_PORT = 5001

estado_sesion = {"usuario": None, "contrasena": None}
red_config = {"host": REMOTE_HOST, "port": REMOTE_PORT}


def realizar_peticion(datos_envio):
    try:
        with socket.create_connection((red_config["host"], red_config["port"]), timeout=5) as canal_sock:
            manejador_io = canal_sock.makefile("rwb")
            manejador_io.write(json.dumps(datos_envio, ensure_ascii=False).encode("utf-8") + b"\n")
            manejador_io.flush()

            linea_respuesta = manejador_io.readline()
            if not linea_respuesta:
                return {"ok": False, "error": "El servidor cerro la conexion."}

            return json.loads(linea_respuesta.decode("utf-8"))
    except ConnectionRefusedError:
        return {"ok": False, "error": "No se puede conectar al servidor."}
    except socket.timeout:
        return {"ok": False, "error": "La conexion con el servidor expiro."}
    except OSError as err_os:
        return {"ok": False, "error": f"Error de red: {err_os}"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "El servidor respondio con JSON invalido."}


def empaquetar_auth():
    return {"usuario": estado_sesion["usuario"], "contrasena": estado_sesion["contrasena"]}


def imprimir_salida(dict_res):
    if dict_res.get("ok"):
        print(f"  >>> {dict_res.get('mensaje', 'Operacion realizada.')}")
    else:
        print(f"  >>> [ERROR] {dict_res.get('error', 'Error desconocido.')}")


def cmd_registrar():
    usr_input = input("  Nombre de usuario: ").strip()
    pwd_input = input("  Contrasena: ").strip()
    res = realizar_peticion(
        {"accion": "registrar", "usuario": usr_input, "contrasena": pwd_input}
    )
    imprimir_salida(res)


def cmd_login():
    usr_input = input("  Usuario: ").strip()
    pwd_input = input("  Contrasena: ").strip()
    res = realizar_peticion(
        {"accion": "login", "usuario": usr_input, "contrasena": pwd_input}
    )

    if res.get("ok"):
        estado_sesion["usuario"] = usr_input
        estado_sesion["contrasena"] = pwd_input

    imprimir_salida(res)


def cmd_ver_tareas():
    res = realizar_peticion({"accion": "listar_tareas", **empaquetar_auth()})
    if not res.get("ok"):
        imprimir_salida(res)
        return

    lista_tareas = res.get("tareas", [])
    if not lista_tareas:
        print("  No tenes tareas registradas.")
        return

    print(f"  Tareas de {estado_sesion['usuario']}:")
    for t in lista_tareas:
        print(f"    #{t['id']} - {t['descripcion']} ({t['creada_en']})")


def cmd_crear_tarea():
    texto_tarea = input("  Descripcion de la tarea: ").strip()
    if not texto_tarea:
        print("  La descripcion no puede estar vacia.")
        return

    res = realizar_peticion(
        {"accion": "crear_tarea", "descripcion": texto_tarea, **empaquetar_auth()}
    )

    if res.get("ok"):
        t_datos = res["tarea"]
        print(f"  Tarea creada con id #{t_datos['id']}.")
    else:
        imprimir_salida(res)


def cmd_eliminar_tarea():
    cmd_ver_tareas()
    try:
        id_ingresado = int(input("  ID de la tarea a eliminar: ").strip())
    except ValueError:
        print("  ID invalido.")
        return

    res = realizar_peticion(
        {"accion": "eliminar_tarea", "id": id_ingresado, **empaquetar_auth()}
    )
    imprimir_salida(res)


def cmd_cerrar_sesion():
    estado_sesion["usuario"] = None
    estado_sesion["contrasena"] = None
    print("  Sesion cerrada.")


LISTA_MENU = [
    ("Registro de usuario", cmd_registrar),
    ("Iniciar sesion", cmd_login),
    ("Ver mis tareas", cmd_ver_tareas),
    ("Crear tarea", cmd_crear_tarea),
    ("Eliminar tarea", cmd_eliminar_tarea),
    ("Cerrar sesion", cmd_cerrar_sesion),
    ("Salir", None),
]


def validacion_sesion(funcion_accion):
    return funcion_accion in (cmd_ver_tareas, cmd_crear_tarea, cmd_eliminar_tarea, cmd_cerrar_sesion)


def ejecucion_principal():
    print("=== Sistema distribuido de gestion de tareas ===")
    print(f"Detalles de servidor: {red_config['host']}:{red_config['port']}")

    while True:
        info_login = (
            f"(Iniciaste sesion como {estado_sesion['usuario']})"
            if estado_sesion["usuario"]
            else "(sin sesion)"
        )
        print(f"\n{info_login}")
        for indice, (texto_opcion, _) in enumerate(LISTA_MENU, 1):
            print(f"  {indice}. {texto_opcion}")

        seleccion = input("Elegi una opcion: ").strip()
        if not seleccion.isdigit() or not (1 <= int(seleccion) <= len(LISTA_MENU)):
            print("  Opcion no valida.")
            continue

        posicion = int(seleccion) - 1
        nombre_opcion, rutina_ejecutar = LISTA_MENU[posicion]

        if rutina_ejecutar is None:
            print("  Adios!")
            break

        if validacion_sesion(rutina_ejecutar) and not estado_sesion["usuario"]:
            print("  Se requiere iniciar sesion primero.")
            continue

        print(f"\n--- {nombre_opcion} ---")
        rutina_ejecutar()


def procesar_argumentos_cli():
    parser = argparse.ArgumentParser(
        description="Cliente TCP para gestion distribuida de tareas."
    )
    parser.add_argument("--host", default=REMOTE_HOST)
    parser.add_argument("--port", type=int, default=REMOTE_PORT)
    return parser.parse_args()


if __name__ == "__main__":
    args_cli = procesar_argumentos_cli()
    red_config["host"] = args_cli.host
    red_config["port"] = args_cli.port
    ejecucion_principal()