# Sistema de Gestión de Tareas Distribuido

Este proyecto consiste en un **Sistema Distribuido de Gestión de Tareas** basado en una arquitectura Cliente-Servidor utilizando Sockets TCP. El servidor procesa peticiones concurrentes a través de un pool de hilos (`ThreadPoolExecutor`) y persiste la información en una base de datos relacional SQLite con soporte de concurrencia y seguridad criptográfica.

---

## Arquitectura y Funcionamiento Básico

El sistema opera bajo un modelo de comunicación síncrona por flujo de bytes a través de Sockets TCP, utilizando un protocolo de aplicación basado en tramas de texto formateadas en **JSON** finalizadas por un salto de línea (`\n`).

### Componentes Principales

1. **Servidor (`servidor.py`)**:
   * **Socket de Escucha**: Se enlaza a un puerto TCP y acepta conexiones entrantes de manera continua.
   * **Manejo de Concurrencia**: Por cada cliente conectado, se delega el flujo de entrada y salida a un hilo independiente (`daemon=True`). Las peticiones internas de lógica de negocio se procesan mediante un pool de trabajadores (`ThreadPoolExecutor`) para optimizar el rendimiento general.
   * **Capa de Persistencia**: Utiliza SQLite. Cuenta con un mecanismo de exclusión mutua (`threading.Lock`) para asegurar que las escrituras concurrentes a la base de datos no generen colisiones ni errores de bloqueo (bloqueo de base de datos).
   * **Seguridad**: Las contraseñas no se almacenan en texto plano. Se implementa una derivación de claves mediante `PBKDF2-HMAC-SHA256` combinada con una semilla aleatoria (`salt`) única por usuario para mitigar ataques de diccionario y tablas de búsqueda precomputadas. La verificación utiliza una comparación protegida (`hmac.compare_digest`) para prevenir ataques de tiempo.

2. **Cliente (`cliente.py`)**:
   * **Interfaz de Consola**: Proporciona un menú interactivo en español para guiar al usuario.
   * **Ciclo de Vida de Conexión**: Adopta una estrategia de conexiones cortas: abre el socket, envía la acción estructurada en JSON junto con las credenciales de la sesión activa, recibe la respuesta del servidor y cierra el socket de inmediato.

---

## Requisitos Previos

El sistema fue desarrollado utilizando únicamente la **librería estándar de Python 3**, por lo que **no requiere la instalación de dependencias externas**.

* Python 3.8 o superior instalado.
* SQLite integrado nativamente en el entorno de Python.

---

## Instrucciones de Ejecución

Para desplegar y probar el sistema localmente, seguí estos pasos desde tu terminal:

### 1. Inicializar el Servidor

Abrí una terminal en la raíz del proyecto y ejecutá el servidor. Por defecto, escuchará en la dirección `127.0.0.1:5001` con un pool de 4 hilos.

```bash
python servidor.py
```

### 1. Inicializar el Servidor

Abrí una terminal en la raíz del proyecto y ejecutá el archivo del cliente.

```bash
python cliente.py

```

### Diagrama

<img width="927" height="822" alt="image" src="https://github.com/user-attachments/assets/d7c7b60e-6166-4046-b3eb-6642adb0e9c1" />

