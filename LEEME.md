# AURA · Asistente visual

Aplicación de escritorio para Windows con interfaz renovada, logo propio, interruptor para activar/desactivar el atajo global `Ctrl + Q`, notificaciones de respuesta y visualización del análisis dentro de la aplicación. El análisis usa instrucciones especializadas para matemáticas, física, química, ciencias, humanidades, política y otras áreas.

## Crear el ejecutable

1. Instala Python 3.10 o posterior.
2. Haz doble clic en `crear_exe.bat` y espera a que termine la compilación.
3. El ejecutable queda en `dist\AURA.exe`.
4. Abre AURA, entra en **Ajustes**, agrega tu clave API de Groq y pulsa **Guardar clave**.
5. Regresa a **Inicio**, activa el interruptor y pulsa `Ctrl + Q` desde la ventana que quieras analizar.
6. Al cerrar la ventana con la X, AURA queda activa en el área de notificaciones, sin ocupar un botón en la barra de tareas. Desde el icono puedes volver a abrirla, activar/desactivar el atajo o elegir **Salir de AURA**. También puedes terminar el proceso desde el Administrador de tareas.

La captura completa se envía a Groq para producir el análisis. AURA no se oculta ni reaparece al usar el atajo. La respuesta se presenta en la aplicación y en una notificación de Windows; si la ventana está en el área de notificaciones, la respuesta queda disponible al volver a abrirla. El historial se guarda en `%APPDATA%\AuraAsistente\historial.txt` y la clave se almacena en el perfil de Windows del usuario.

## Desarrollo

```powershell
python -m pip install -r requirements.txt
python asistente_local.py
```

## Subir el código a Git

La clave API no está escrita en este código. AURA la lee del perfil de Windows (`GROQ_API_KEY`) y no debe publicarse en Git. El archivo `.gitignore` excluye ejecutables, compilaciones, historiales y archivos locales. Sube solo los archivos de código y recursos del proyecto; nunca pegues la clave en el código ni en un commit.
