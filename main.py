from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.utils import platform
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.factory import Factory 

import cv2
import numpy as np
import os
import shutil
from datetime import datetime

# --- Lógica de permisos y rutas para Android ---
if platform == 'android':
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    # IMPORTANTE: Definimos esto global para usarlo correctamente
    PythonActivity = autoclass('org.kivy.android.PythonActivity')

# --- CONFIGURACIÓN PARA PC ---
if platform not in ['android', 'ios']:
    Window.size = (400, 750)

# --- CLASE CÁMARA ---
class KivyCamera(Image):
    is_recording = BooleanProperty(False)
    is_paused = BooleanProperty(False)
    video_writer = None
    capture_count = NumericProperty(0)
    error_message = StringProperty("Iniciando...")

    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30

    def start_camera(self):
        # 1. Liberar cámara anterior si existe
        if self.capture:
            self.capture.release()
            self.capture = None

        found = False
        log_intentos = ""
        possible_indices = [0, 1, 2, 3] # Probamos las cámaras más comunes
        
        for i in possible_indices:
            try:
                # INTENTO A: Método nativo de Android (El truco nuevo)
                # cv2.CAP_ANDROID suele ser el valor 700, ayuda a conectar directo al hardware
                temp_cap = cv2.VideoCapture(i, cv2.CAP_ANDROID)
                
                if not temp_cap.isOpened():
                    # INTENTO B: Método Estándar (Por si el A falla)
                    temp_cap = cv2.VideoCapture(i)

                if temp_cap.isOpened():
                    # Leer frame de prueba para confirmar que es real
                    ret, frame = temp_cap.read()
                    if ret and frame is not None and frame.size > 0:
                        self.capture = temp_cap
                        self.error_message = "" # ¡ÉXITO! Borramos el error
                        Clock.schedule_interval(self.update, 1.0 / self.fps)
                        found = True
                        print(f"Cámara encontrada en índice {i}")
                        break
                    else:
                        log_intentos += f"Cam {i}: Abre pero pantalla negra.\n"
                        temp_cap.release()
                else:
                    log_intentos += f"Cam {i}: Bloqueada/No existe.\n"
            
            except Exception as e:
                log_intentos += f"Cam {i} Error: {str(e)}\n"

        if not found:
            self.error_message = f"ERROR FINAL:\n{log_intentos}\nTIP: Reinicia el celular."

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
                if platform == 'android':
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

                if self.is_recording and not self.is_paused and self.video_writer:
                    self.video_writer.write(frame)

                self.current_clean_frame = frame

                scale = 640 / frame.shape[0]
                w = int(frame.shape[1] * scale)
                h = int(frame.shape[0] * scale)
                frame_resized = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)

                buf = cv2.flip(frame_resized, 0).tobytes()
                texture = Texture.create(size=(frame_resized.shape[1], frame_resized.shape[0]), colorfmt='bgr')
                texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
                self.texture = texture

    def take_photo(self):
        if not hasattr(self, 'current_clean_frame') or self.current_clean_frame is None:
            self.error_message = "Error: Cámara no lista"
            return
        app = App.get_running_app()
        try:
            if not os.path.exists(app.path_puesto):
                os.makedirs(app.path_puesto, exist_ok=True)
            prefix = app.current_measurement_type[:3]
            filename = f"{app.path_puesto}/{prefix}_Foto_{datetime.now().strftime('%H%M%S')}.jpg"
            cv2.imwrite(filename, self.current_clean_frame)
            self.capture_count += 1
            self.error_message = "FOTO OK"
        except Exception as e:
            self.error_message = f"Error Foto: {e}"

    def toggle_record_stop(self):
        if self.capture is None:
            self.error_message = "Error: Sin Cámara"
            return
        app = App.get_running_app()
        if not self.is_recording:
            try:
                if not os.path.exists(app.path_puesto):
                    os.makedirs(app.path_puesto, exist_ok=True)
                prefix = app.current_measurement_type[:3]
                filename = f"{app.path_puesto}/{prefix}_Video_{datetime.now().strftime('%H%M%S')}.mp4"
                w_cam = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                h_cam = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if platform == 'android':
                    w_video, h_video = h_cam, w_cam
                else:
                    w_video, h_video = w_cam, h_cam
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                self.video_writer = cv2.VideoWriter(filename, fourcc, 30.0, (w_video, h_video))
                if self.video_writer.isOpened():
                    self.is_recording = True
                    self.is_paused = False
                    self.error_message = "GRABANDO..."
                else:
                    self.error_message = "Error: Falló VideoWriter"
            except Exception as e:
                self.error_message = f"Error Video: {e}"
        else:
            self.close_video_file()

    def toggle_pause(self):
        if self.is_recording:
            self.is_paused = not self.is_paused

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
            self.error_message = "Video Guardado."

Factory.register('KivyCamera', cls=KivyCamera)

# --- DISEÑO KV ---
KV = '''
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set color_gold (0.72, 0.54, 0.15, 1)
#:set color_black (0.05, 0.05, 0.05, 1)
#:set color_white (0.95, 0.95, 0.95, 1)
#:set color_red (0.8, 0.1, 0.1, 1)
#:set color_green (0.1, 0.7, 0.1, 1)

<Label>:
    font_size: sp(16)
    color: color_white

<BotonECAM@Button>:
    background_normal: ''
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
            text: "Gestión Inteligente v0.5"
            color: (0.6, 0.6, 0.6, 1)
            size_hint_y: 0.1

        Widget:
            size_hint_y: 0.2

        BotonECAM:
            text: "INICIAR"
            on_release: app.root.current = 'project'

<ProjectScreen>:
    name: 'project'
    on_enter: root.cargar_carpetas()
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
            height: dp(50)

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

        BotonECAM:
            text: "CREAR / SIGUIENTE"
            on_release: root.crear_proyecto()
        
        Label:
            text: "Historial de Carpetas"
            color: (0.5, 0.5, 0.5, 1)
            font_size: sp(14)
            size_hint_y: None
            height: dp(30)
            
        ScrollView:
            BoxLayout:
                id: folder_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)

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
                    text: "INCENDIOS"
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
        KivyCamera:
            id: qrcam
            size_hint: (1, 1)
            fit_mode: "cover"

        Image:
            source: app.current_guide_image
            size_hint: (1, 1)
            allow_stretch: True
            opacity: 0.4 if app.current_guide_image else 0
            fit_mode: "contain"

        Label:
            text: qrcam.error_message
            color: color_red if "NO" in self.text or "Err" in self.text else color_gold
            bold: True
            font_size: sp(14)
            size_hint_y: None
            height: dp(100)
            text_size: self.size
            halign: 'center'
            valign: 'center'
            pos_hint: {'center_x': 0.5, 'top': 0.8}
            canvas.before:
                Color:
                    rgba: (0,0,0,0.6) if self.text else (0,0,0,0)
                Rectangle:
                    pos: self.pos
                    size: self.size

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

        Label:
            text: "● PAUSA" if (qrcam.is_recording and qrcam.is_paused) else ("● GRABANDO" if qrcam.is_recording else "")
            color: color_gold if qrcam.is_paused else color_red
            font_size: sp(24)
            bold: True
            pos_hint: {'center_x': 0.5, 'center_y': 0.85}
            opacity: 1 if qrcam.is_recording else 0

        BotonCam:
            text: "GUÍA"
            size_hint: (None, None)
            size: (dp(60), dp(60))
            pos_hint: {'right': 0.98, 'center_y': 0.5}
            background_color: (0, 0, 0, 0.6)
            color: color_gold
            font_size: sp(12)
            on_release: app.cycle_guide()

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

            BotonCam:
                text: "FOTO"
                background_color: (0.3, 0.3, 0.3, 1)
                on_release: qrcam.take_photo()

            BotonCam:
                text: "REC" if not qrcam.is_recording else "STOP"
                font_size: sp(18)
                background_color: color_red if qrcam.is_recording else color_green
                on_release: qrcam.toggle_record_stop()

            BotonCam:
                text: "II"
                font_size: sp(22)
                background_color: color_gold
                disabled: not qrcam.is_recording
                opacity: 1 if qrcam.is_recording else 0.3
                on_release: qrcam.toggle_pause()

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
            base = app.get_storage_path()
            if base:
                app.path_empresa = os.path.join(base, empresa)
                if not os.path.exists(app.path_empresa):
                    os.makedirs(app.path_empresa, exist_ok=True)
            app.root.current = 'measurement'

    def cargar_carpetas(self):
        # PROTECCION CONTRA CRASH: Usamos try/except
        try:
            app = App.get_running_app()
            path = app.get_storage_path()
            lista = self.ids.folder_list
            lista.clear_widgets()

            if path and os.path.exists(path):
                try:
                    # Leemos carpetas
                    carpetas = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
                    for c in carpetas:
                        btn = Button(
                            text=c,
                            size_hint_y=None, 
                            height=dp(50),
                            background_color=(0.2, 0.2, 0.2, 1)
                        )
                        btn.bind(on_release=lambda x, nom=c: self.mostrar_opciones(nom))
                        lista.add_widget(btn)
                except Exception as e:
                    # Si falla leer, mostramos error pero NO cerramos la app
                    err_lbl = Label(text=f"Error leyendo carpetas: {str(e)}", color=(1,0,0,1), size_hint_y=None, height=dp(30))
                    lista.add_widget(err_lbl)
        except Exception as e_global:
            print(f"Error fatal cargar_carpetas: {e_global}")

    def mostrar_opciones(self, nombre_carpeta):
        try:
            app = App.get_running_app()
            ruta = os.path.join(app.get_storage_path(), nombre_carpeta)
            
            contenido = ""
            try:
                archs = os.listdir(ruta)
                contenido = "\n".join(archs[:10])
                if len(archs) > 10: contenido += "\n..."
            except: contenido = "Vacia o ilegible"

            layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
            lbl = Label(text=f"{nombre_carpeta}\n\n{contenido}")
            
            btn_borrar = Button(text="ELIMINAR", background_color=(0.8, 0, 0, 1), size_hint_y=None, height=dp(50))
            btn_cerrar = Button(text="Cerrar", size_hint_y=None, height=dp(50))

            layout.add_widget(lbl)
            layout.add_widget(btn_borrar)
            layout.add_widget(btn_cerrar)

            popup = Popup(title="Gestionar", content=layout, size_hint=(0.9, 0.7))
            
            def eliminar(inst):
                try:
                    shutil.rmtree(ruta)
                    popup.dismiss()
                    self.cargar_carpetas()
                except Exception as e:
                    lbl.text = f"Error borrando: {e}"

            btn_borrar.bind(on_release=eliminar)
            btn_cerrar.bind(on_release=popup.dismiss)
            popup.open()
        except Exception as e:
            print(f"Error popup: {e}")

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
            
            # Crear nombre carpeta
            folder = f"{app.current_measurement_type}_{puesto}_{datetime.now().strftime('%H%M')}"
            
            base = app.path_empresa
            # Fallback si path_empresa esta vacio
            if not base:
                storage = app.get_storage_path()
                base = os.path.join(storage, app.current_company) if storage else "/sdcard"

            app.path_puesto = os.path.join(base, folder)
            try:
                if not os.path.exists(app.path_puesto):
                    os.makedirs(app.path_puesto, exist_ok=True)
            except: pass

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
        if m == "ERGONOMIA": w.hint_text = "Carga, Frecuencia, Posturas..."
        elif m == "INCENDIOS": w.hint_text = "Matafuegos, Luces..."
        elif m == "RUIDO": w.hint_text = "dBA, Fuente..."
        else: w.hint_text = "Observaciones..."

    def finalizar(self, guardar=True):
        app = App.get_running_app()
        if guardar:
            txt = self.ids.notas_input.text
            if txt:
                fname = f"{app.path_puesto}/Informe_{datetime.now().strftime('%H%M%S')}.txt"
                try:
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(f"CLIENTE: {app.current_company}\n")
                        f.write(f"TIPO: {app.current_measurement_type}\n")
                        f.write(f"PUESTO: {app.current_post}\n")
                        f.write(f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                        f.write(txt)
                except Exception as e:
                    print(f"Error txt: {e}")
        self.ids.notas_input.text = ""
        app.root.current = 'measurement'

class CimaCamApp(App):
    current_company = StringProperty("")
    current_post = StringProperty("")
    current_measurement_type = StringProperty("ERGONOMIA")
    path_empresa = ""
    path_puesto = ""
    
    guide_list = ListProperty(['guia_frente.png', 'guia_perfil.png', 'guia_admin_perfil.png', 'guia_admin_frente.png', 'guia_levantamiento.png', ''])
    current_guide_index = NumericProperty(0)
    current_guide_image = StringProperty('guia_frente.png')

    def cycle_guide(self):
        self.current_guide_index = (self.current_guide_index + 1) % len(self.guide_list)
        self.current_guide_image = self.guide_list[self.current_guide_index]

    def build(self):
        Window.bind(on_keyboard=self.on_key)
        return Builder.load_string(KV)

    # --- MÉTODO CORREGIDO DE ALMACENAMIENTO ---
    def get_storage_path(self):
        if platform == 'android':
            try:
                # CORRECCIÓN CLAVE: Usamos la actividad, no la clase Context
                context = PythonActivity.mActivity 
                external_file = context.getExternalFilesDir(None)
                if external_file:
                    return os.path.join(external_file.getAbsolutePath(), "CimaCam_Datos")
            except Exception as e:
                print(f"Error get_storage_path: {e}")
            return "/sdcard/CimaCam_Datos"
        else:
            return os.path.join(os.getcwd(), "CimaCam_Datos")

    def on_start(self):
        base = self.get_storage_path()
        if base and not os.path.exists(base):
            try: os.makedirs(base, exist_ok=True)
            except: pass

        if platform == 'android':
            try:
                request_permissions([
                    Permission.CAMERA,
                    Permission.RECORD_AUDIO,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ])
            except: pass

    def on_key(self, window, key, *args):
        if key == 27:
            sm = self.root
            if sm.current == 'camera':
                try: sm.get_screen('camera').ids.qrcam.stop_camera()
                except: pass
                sm.current = 'job'
                return True
            elif sm.current == 'welcome': return False
            else:
                sm.current = 'welcome'
                return True
            return True

if __name__ == '__main__':
    try:
        CimaCamApp().run()
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        try:
            if platform == 'android':
                # Re-definimos por si acaso crash ocurre antes de importar
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity
                external_file = context.getExternalFilesDir(None)
                if external_file:
                    path = os.path.join(external_file.getAbsolutePath(), "CimaCam_Datos", "CRASH_LOG.txt")
                    folder = os.path.dirname(path)
                    if not os.path.exists(folder):
                        os.makedirs(folder, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(f"--- ERROR {datetime.now()} ---\n{error_trace}")
        except: pass

