from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.utils import platform
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.metrics import dp, sp
from kivy.factory import Factory 

import cv2
import numpy as np
import os
from datetime import datetime

# --- IMPORTANTE: Lógica de almacenamiento segura para Android ---
if platform == 'android':
    from jnius import autoclass
    # Usamos Environment para obtener rutas estándar de Android si fuera necesario
    Environment = autoclass('android.os.Environment')
    # Contexto actual para pedir rutas específicas de la app
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')

# --- CONFIGURACIÓN PARA PC ---
if platform not in ['android', 'ios']:
    Window.size = (400, 750)

# --- CLASE CÁMARA (LIGERA - SIN MEDIAPIPE) ---
class KivyCamera(Image):
    is_recording = BooleanProperty(False)
    is_paused = BooleanProperty(False)
    video_writer = None
    capture_count = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30

    def start_camera(self):
        # Intentar buscar la cámara en varios índices
        found = False
        # Probamos del índice 0 al 5 (algunos celulares usan el 2 o el 3 para la trasera)
        possible_indices = [0, 1, 2, 3, 4]
        
        for index in possible_indices:
            print(f"Probando cámara índice {index}...")
            temp_cap = cv2.VideoCapture(index)
            
            if temp_cap.isOpened():
                # Leemos un frame de prueba para ver si es real
                ret, frame = temp_cap.read()
                if ret and frame is not None and frame.shape[0] > 0:
                    self.capture = temp_cap
                    self.fps = 30
                    self.error_message = f"Cámara encontrada en índice: {index}"
                    Clock.schedule_interval(self.update, 1.0 / self.fps)
                    found = True
                    break
                else:
                    temp_cap.release()
            
        if not found:
            self.error_message = "ERROR CRÍTICO: Ninguna cámara respondió (0-4)."

    def stop_camera(self):
        Clock.unschedule(self.update)
        self.close_video_file()
        if self.capture:
            self.capture.release()
            self.capture = None

    def update(self, dt):
        if self.capture:
            ret, frame = self.capture.read()
            if ret:
                # Rotación para Android (portrait)
                if platform == 'android':
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

                # GRABAR solo si está REC y NO PAUSADO
                # Nota: Se graba el video "limpio" (sin la silueta superpuesta)
                if self.is_recording and not self.is_paused and self.video_writer:
                    self.video_writer.write(frame)

                # Guardamos el frame limpio para fotos
                self.current_clean_frame = frame

                # Preparar frame para mostrar en pantalla Kivy
                # Redimensionar para mejorar rendimiento en pantalla
                scale_percent = 640 / frame.shape[0]
                width = int(frame.shape[1] * scale_percent)
                height = int(frame.shape[0] * scale_percent)
                dim = (width, height)
                frame_resized = cv2.resize(frame, dim, interpolation = cv2.INTER_LINEAR)

                # Convertir a textura Kivy
                buf = cv2.flip(frame_resized, 0).tobytes()
                texture = Texture.create(size=(frame_resized.shape[1], frame_resized.shape[0]), colorfmt='bgr')
                texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
                self.texture = texture

    # --- LÓGICA DE LOS BOTONES ---

    # FOTO
    def take_photo(self):
        app = App.get_running_app()
        if hasattr(self, 'current_clean_frame'):
            try:
                if not os.path.exists(app.path_puesto):
                    os.makedirs(app.path_puesto, exist_ok=True)
                    
                prefix = app.current_measurement_type[:3]
                filename = f"{app.path_puesto}/{prefix}_Foto_{datetime.now().strftime('%H%M%S')}.jpg"
                cv2.imwrite(filename, self.current_clean_frame)
                self.capture_count += 1
                print(f"Foto guardada: {filename}")
            except Exception as e:
                print(f"Error al guardar foto: {e}")

    # PLAY / STOP
    def toggle_record_stop(self):
        app = App.get_running_app()
        
        if not self.is_recording:
            # INICIAR GRABACIÓN
            try:
                if not os.path.exists(app.path_puesto):
                    os.makedirs(app.path_puesto, exist_ok=True)

                prefix = app.current_measurement_type[:3]
                filename = f"{app.path_puesto}/{prefix}_Video_{datetime.now().strftime('%H%M%S')}.mp4"
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # Ajustar dimensiones si estamos en Android (rotación)
                if platform == 'android':
                    width, height = height, width

                self.video_writer = cv2.VideoWriter(filename, fourcc, 20.0, (width, height))
                
                self.is_recording = True
                self.is_paused = False
                print(f"Grabando: {filename}")
            except Exception as e:
                print(f"Error al iniciar grabación: {e}")
        else:
            # DETENER GRABACIÓN
            self.close_video_file()

    # PAUSA
    def toggle_pause(self):
        if self.is_recording:
            self.is_paused = not self.is_paused

    # FINALIZAR
    def exit_screen(self):
        if self.is_recording:
            self.close_video_file()
        app = App.get_running_app()
        app.root.current = 'review'

    def close_video_file(self):
        if self.is_recording:
            self.is_recording = False
            self.is_paused = False
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.capture_count += 1
            print("Video finalizado.")

Factory.register('KivyCamera', cls=KivyCamera)

# --- DISEÑO KV ---
KV = '''
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set color_gold (0.72, 0.54, 0.15, 1)
#:set color_dark (0.1, 0.1, 0.1, 1)
#:set color_black (0.05, 0.05, 0.05, 1)
#:set color_white (0.95, 0.95, 0.95, 1)
#:set color_red (0.8, 0.1, 0.1, 1)
#:set color_green (0.1, 0.7, 0.1, 1)

<Label>:
    font_size: sp(16)
    color: color_white

<TextInput>:
    background_color: (0.15, 0.15, 0.15, 1)
    foreground_color: color_white
    cursor_color: color_gold
    font_size: sp(18)
    padding: [dp(15), dp(15)]
    multiline: False
    background_normal: ''
    background_active: ''
    canvas.after:
        Color:
            rgba: color_gold if self.focus else (0.3, 0.3, 0.3, 1)
        Line:
            width: dp(1.2)
            rectangle: (self.x, self.y, self.width, self.height)

# Botón Genérico
<BotonECAM@Button>:
    background_normal: ''
    background_down: ''
    background_color: color_gold
    color: color_white
    font_size: sp(18)
    bold: True
    size_hint: (None, None)
    width: dp(280)
    height: dp(60)
    pos_hint: {'center_x': 0.5}
    canvas.before:
        Color:
            rgba: self.background_color if self.state == 'normal' else (0.6, 0.45, 0.1, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(30)]

# Estilo Botones Cámara
<BotonCam@Button>:
    background_normal: '' 
    background_color: (0.2, 0.2, 0.2, 1)
    color: color_white
    font_size: sp(14)
    bold: True
    size_hint: (None, None)
    size: (dp(65), dp(65))
    pos_hint: {'center_y': 0.5}
    canvas.before:
        Color:
            rgba: self.background_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(15)]

ScreenManager:
    WelcomeScreen:
    ProjectScreen:
    MeasurementScreen:
    JobScreen:
    CameraScreen:
    ReviewScreen:

<WelcomeScreen>:
    name: 'welcome'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(40)
        spacing: dp(20)
        canvas.before:
            Color:
                rgba: color_black
            Rectangle:
                pos: self.pos
                size: self.size

        Image:
            source: 'logo.png'
            size_hint_y: 0.5
            allow_stretch: True
        
        Label:
            text: "CIMA CAM"
            font_size: sp(36)
            bold: True
            color: color_gold
            size_hint_y: 0.1

        Label:
            text: "Releva tus datos de forma inteligente"
            color: (0.6, 0.6, 0.6, 1)
            size_hint_y: 0.1

        Widget:
            size_hint_y: 0.2

        BotonECAM:
            text: "INICIAR PROYECTO"
            on_release: app.root.current = 'project'

<ProjectScreen>:
    name: 'project'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(30)
        spacing: dp(20)
        canvas.before:
            Color:
                rgba: color_black
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "Nuevo Proyecto"
            font_size: sp(24)
            color: color_gold
            bold: True
            size_hint_y: None
            height: dp(60)

        TextInput:
            id: empresa_input
            hint_text: "Cliente / Empresa"
            size_hint_y: None
            height: dp(55)

        TextInput:
            id: fecha_input
            text: root.get_date()
            readonly: True
            size_hint_y: None
            height: dp(55)
            foreground_color: (0.6, 0.6, 0.6, 1)

        Widget:
            size_hint_y: 1

        BotonECAM:
            text: "SIGUIENTE"
            on_release: root.crear_proyecto()

<MeasurementScreen>:
    name: 'measurement'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(15)
        canvas.before:
            Color:
                rgba: color_black
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "¿Qué vamos a medir?"
            font_size: sp(22)
            color: color_gold
            bold: True
            size_hint_y: None
            height: dp(50)

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(15)
                padding: [0, dp(10)]

                BotonECAM:
                    text: "ERGONOMÍA"
                    on_release: root.select_type("ERGONOMIA")

                BotonECAM:
                    text: "INCENDIOS (Carga Fuego)"
                    on_release: root.select_type("INCENDIOS")

                BotonECAM:
                    text: "RUIDO LABORAL"
                    on_release: root.select_type("RUIDO")

                BotonECAM:
                    text: "ILUMINACIÓN"
                    on_release: root.select_type("ILUMINACION")

                BotonECAM:
                    text: "PUESTA A TIERRA"
                    on_release: root.select_type("PAT")

                BotonECAM:
                    text: "TERMOGRAFÍA"
                    on_release: root.select_type("TERMOGRAFIA")

<JobScreen>:
    name: 'job'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(30)
        spacing: dp(20)
        canvas.before:
            Color:
                rgba: color_black
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: app.current_company
            font_size: sp(18)
            color: (0.5, 0.5, 0.5, 1)
            size_hint_y: None
            height: dp(30)

        Label:
            text: app.current_measurement_type
            font_size: sp(26)
            bold: True
            color: color_gold
            size_hint_y: None
            height: dp(50)

        Label:
            text: "Ubicación / Sector / Equipo"
            halign: 'left'
            text_size: self.size
            size_hint_y: None
            height: dp(30)

        TextInput:
            id: puesto_input
            hint_text: "Ej: Nave Principal - Tablero 4"
            size_hint_y: None
            height: dp(55)

        Widget:
            size_hint_y: 1

        BotonECAM:
            text: "ABRIR CÁMARA"
            on_release: root.iniciar_puesto()

<CameraScreen>:
    name: 'camera'
    FloatLayout:
        # CÁMARA
        KivyCamera:
            id: qrcam
            size_hint: (1, 1)
            fit_mode: "cover"

        # --- CAPA GUÍA (SILUETA) ---
        Image:
            source: app.current_guide_image
            size_hint: (1, 1)
            allow_stretch: True
            opacity: 0.4 if app.current_guide_image else 0
            fit_mode: "contain"

        # --- INFO SUPERIOR ---
        BoxLayout:
            size_hint: (1, None)
            height: dp(60)
            pos_hint: {'top': 1}
            padding: dp(15)
            canvas.before:
                Color:
                    rgba: (0, 0, 0, 0.5)
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            Label:
                text: app.current_measurement_type
                bold: True
                color: color_gold
                halign: 'left'
                text_size: self.size
                font_size: sp(14)
            
            Label:
                text: str(qrcam.capture_count)
                halign: 'right'
                text_size: self.size
                bold: True

        # --- AVISO DE ESTADO ---
        Label:
            text: "● PAUSA" if (qrcam.is_recording and qrcam.is_paused) else ("● GRABANDO" if qrcam.is_recording else "")
            color: color_gold if qrcam.is_paused else color_red
            font_size: sp(24)
            bold: True
            pos_hint: {'center_x': 0.5, 'center_y': 0.85}
            opacity: 1 if qrcam.is_recording else 0

        # --- BOTÓN FLOTANTE PARA CAMBIAR GUÍA ---
        BotonCam:
            text: "GUÍA"
            size_hint: (None, None)
            size: (dp(60), dp(60))
            pos_hint: {'right': 0.98, 'center_y': 0.5}
            background_color: (0, 0, 0, 0.6)
            color: color_gold
            font_size: sp(12)
            on_release: app.cycle_guide()

        # --- CONTROLES INFERIORES (4 BOTONES) ---
        BoxLayout:
            size_hint: (1, None)
            height: dp(120)
            pos_hint: {'bottom': 1}
            padding: [dp(10), dp(10)]
            spacing: dp(10)
            canvas.before:
                Color:
                    rgba: (0, 0, 0, 0.7)
                Rectangle:
                    pos: self.pos
                    size: self.size

            # BOTON 1: FOTO
            BotonCam:
                text: "FOTO"
                background_color: (0.3, 0.3, 0.3, 1)
                on_release: qrcam.take_photo()

            # BOTON 2: PLAY / STOP (Cuadrado)
            BotonCam:
                text: "■" if qrcam.is_recording else "▶"
                font_size: sp(30)
                background_color: color_red if qrcam.is_recording else color_green
                on_release: qrcam.toggle_record_stop()

            # BOTON 3: PAUSA
            BotonCam:
                text: "II"
                font_size: sp(22)
                background_color: color_gold
                disabled: not qrcam.is_recording
                opacity: 1 if qrcam.is_recording else 0.3
                on_release: qrcam.toggle_pause()

            # BOTON 4: FINALIZAR (Salir)
            BotonCam:
                text: "FIN"
                color: color_black
                background_color: color_gold
                on_release: qrcam.exit_screen()

<ReviewScreen>:
    name: 'review'
    on_pre_enter: root.actualizar_hint()
    BoxLayout:
        orientation: 'vertical'
        padding: dp(30)
        spacing: dp(15)
        canvas.before:
            Color:
                rgba: color_black
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "Finalizar Relevamiento"
            font_size: sp(22)
            color: color_gold
            bold: True
            size_hint_y: None
            height: dp(50)

        TextInput:
            id: notas_input
            hint_text: "Observaciones técnicas..."
            multiline: True
            size_hint_y: 1

        BoxLayout:
            size_hint_y: None
            height: dp(60)
            spacing: dp(20)
            
            Button:
                text: "DESCARTAR"
                background_normal: ''
                background_color: (0.5, 0.2, 0.2, 1)
                bold: True
                on_release: root.finalizar(guardar=False)
            
            Button:
                text: "GUARDAR"
                background_normal: ''
                background_color: color_gold
                bold: True
                on_release: root.finalizar(guardar=True)
'''

class WelcomeScreen(Screen):
    pass

class ProjectScreen(Screen):
    def get_date(self):
        return datetime.now().strftime("%d/%m/%Y")
    
    def crear_proyecto(self):
        app = App.get_running_app()
        empresa = self.ids.empresa_input.text
        if empresa:
            app.current_company = empresa
            
            # --- RUTA SEGURA CORREGIDA ---
            if platform == 'android':
                # Esto obtiene: /storage/emulated/0/Android/data/ar.com.cimahys/files/CimaCam_Datos
                # Esta ruta SIEMPRE tiene permiso de escritura y es visible vía USB.
                context = PythonActivity.mActivity
                external_file_path = context.getExternalFilesDir(None).getAbsolutePath()
                base = os.path.join(external_file_path, "CimaCam_Datos")
            else:
                base = os.path.join(os.getcwd(), "CimaCam_Datos")
            
            app.path_empresa = os.path.join(base, empresa)
            if not os.path.exists(app.path_empresa):
                os.makedirs(app.path_empresa, exist_ok=True)
            app.root.current = 'measurement'

class MeasurementScreen(Screen):
    def select_type(self, m_type):
        app = App.get_running_app()
        app.current_measurement_type = m_type
        app.root.current = 'job'

class JobScreen(Screen):
    def iniciar_puesto(self):
        app = App.get_running_app()
        puesto = self.ids.puesto_input.text
        if puesto:
            app.current_post = puesto
            folder = f"{app.current_measurement_type}_{puesto}_{datetime.now().strftime('%H%M')}"
            app.path_puesto = os.path.join(app.path_empresa, folder)
            if not os.path.exists(app.path_puesto):
                os.makedirs(app.path_puesto, exist_ok=True)
            
            cam = app.root.get_screen('camera').ids.qrcam
            cam.capture_count = 0 
            cam.is_recording = False
            cam.is_paused = False
            cam.start_camera()
            app.root.current = 'camera'

class CameraScreen(Screen):
    pass

class ReviewScreen(Screen):
    def actualizar_hint(self):
        app = App.get_running_app()
        m = app.current_measurement_type
        w = self.ids.notas_input
        # Hints simplificados
        if m == "ERGONOMIA": w.hint_text = "Carga (kg), Frecuencia, Posturas..."
        elif m == "INCENDIOS": w.hint_text = "Matafuegos, Luces, Salidas..."
        elif m == "RUIDO": w.hint_text = "dBA, Fuente..."
        else: w.hint_text = "Observaciones generales..."

    def finalizar(self, guardar=True):
        app = App.get_running_app()
        if guardar:
            txt = self.ids.notas_input.text
            if txt:
                fname = f"{app.path_puesto}/Informe_{datetime.now().strftime('%H%M%S')}.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"CLIENTE: {app.current_company}\n")
                    f.write(f"TIPO: {app.current_measurement_type}\n")
                    f.write(f"PUESTO: {app.current_post}\n")
                    f.write(f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                    f.write("="*30 + "\n")
                    f.write(txt)
        self.ids.notas_input.text = ""
        app.root.current = 'measurement'

class CimaCamApp(App):
    current_company = StringProperty("")
    current_post = StringProperty("")
    current_measurement_type = StringProperty("ERGONOMIA")
    path_empresa = ""
    path_puesto = ""
    
    # --- LOGICA DE GUIAS ---
    # Nombres de las imágenes que debes subir. El string vacío '' es "sin guía".
    # Lista ampliada de guías
    guide_list = ListProperty([
        'guia_frente.png',
        'guia_perfil.png',
        'guia_admin_perfil.png',
        'guia_admin_frente.png',
        'guia_levantamiento.png',
        '' # El último vacío es para la opción "sin guía"
    ])
    current_guide_index = NumericProperty(0)
    current_guide_image = StringProperty('guia_frente.png')

    def cycle_guide(self):
        self.current_guide_index = (self.current_guide_index + 1) % len(self.guide_list)
        self.current_guide_image = self.guide_list[self.current_guide_index]

    def build(self):
        Window.bind(on_keyboard=self.on_key)
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.RECORD_AUDIO,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE
            ])
        return Builder.load_string(KV)

    def on_key(self, window, key, *args):
        # 27 es el código del botón 'Atrás' en Android
        if key == 27:
            sm = self.root # Tu ScreenManager
            current_screen = sm.current
            
            # Lógica de navegación: "Si estoy en X, vuelvo a Y"
            if current_screen == 'welcome':
                return False # Cierra la App
            elif current_screen == 'project':
                sm.current = 'welcome'
                return True # Bloquea el cierre y vuelve atrás
            elif current_screen == 'measurement':
                sm.current = 'project'
                return True
            elif current_screen == 'job':
                sm.current = 'measurement'
                return True
            elif current_screen == 'camera':
                # Si estás en la cámara, intenta detenerla antes de salir
                try:
                    screen = sm.get_screen('camera')
                    if hasattr(screen.ids, 'qrcam'):
                        screen.ids.qrcam.stop_camera()
                except:
                    pass
                sm.current = 'job'
                return True
            
            return True # Por defecto no cerrar si no es 'welcome'

if __name__ == '__main__':

    CimaCamApp().run()
