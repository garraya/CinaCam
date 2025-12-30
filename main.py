from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.camera import Camera 
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.utils import platform
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.metrics import dp, sp
from kivy.factory import Factory 
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout

# --- IMPORTACIONES VITALES ---
if platform == 'android':
    try:
        from jnius import autoclass, cast # <--- IMPORTANTE: 'cast' arregla el error de video
    except ImportError:
        autoclass = None
        cast = None
else:
    autoclass = None
    cast = None
    Window.size = (400, 750)

import os
import time
import csv
from datetime import datetime

# --- CLASE CÁMARA NATIVA MEJORADA ---
class KivyCamera(Camera):
    is_recording = BooleanProperty(False)
    is_paused = BooleanProperty(False)
    capture_count = NumericProperty(0)
    status_info = StringProperty("Cámara lista") 
    
    def __init__(self, **kwargs):
        # Resolución FULL HD
        super(KivyCamera, self).__init__(resolution=(1920, 1080), index=0, play=False, **kwargs)
        # Configuración agresiva para llenar pantalla
        self.fit_mode = "cover" 
        self.allow_stretch = True
        self.keep_ratio = False 

    def start_camera(self):
        self.play = True
        self.status_info = ""

    def stop_camera(self):
        self.play = False
        self.status_info = "Cámara Pausada"

    # --- CAMBIO DE LENTES ---
    def cambiar_lente(self, tipo):
        self.play = False 
        
        if tipo == '1x':
            self.index = 0
            self.status_info = "Lente: Principal"
            Clock.schedule_once(lambda dt: self.reactivar(), 0.5)
            
        elif tipo == '0.5x':
            self.status_info = "Buscando Gran Angular..."
            # Intentamos índice 2, si falla probamos otros
            Clock.schedule_once(lambda dt: self.probar_lente_extra(2), 0.5)
            
        elif tipo == 'front':
            self.status_info = "Cámara Frontal"
            Clock.schedule_once(lambda dt: self.probar_lente_extra(1), 0.5)

    def probar_lente_extra(self, indice_nuevo):
        try:
            self.index = indice_nuevo
            self.play = True
            self.status_info = f"Lente ID {indice_nuevo} Activo"
        except Exception as e:
            # Estrategia de búsqueda de cámaras traseras
            if indice_nuevo == 2:
                print("Falló ID 2, probando ID 3...")
                self.probar_lente_extra(3)
            elif indice_nuevo == 3:
                print("Falló ID 3, probando ID 4...")
                self.probar_lente_extra(4)
            else:
                self.status_info = "Lente no disponible"
                self.index = 0
                self.play = True

    def reactivar(self):
        try:
            self.play = True
        except:
            self.index = 0
            self.play = True

    # --- FOTOS ---
    def take_photo(self, es_extintor=False):
        app = App.get_running_app()
        try:
            save_dir = app.path_puesto
            if not os.path.exists(save_dir):
                os.makedirs(save_dir, exist_ok=True)
            
            prefix = "EXT" if es_extintor else app.current_measurement_type[:3]
            timestamp = datetime.now().strftime('%H%M%S')
            filename = f"{save_dir}/{prefix}_Foto_{timestamp}.png"
            
            self.export_to_png(filename)
            
            self.capture_count += 1
            app.temp_photo_path = filename
            print(f"Foto guardada: {filename}")
            
            self.status_info = "¡FOTO GUARDADA!"
            Clock.schedule_once(lambda dt: setattr(self, 'status_info', ''), 2)
            
            if es_extintor:
                app.root.get_screen('extinguisher_form').cargar_imagen(filename)
                app.root.current = 'extinguisher_form'
                
        except Exception as e:
            self.status_info = f"Error: {str(e)}"

    # --- VIDEO NATIVO (CORREGIDO CON CAST) ---
    def toggle_record_stop(self):
        if platform == 'android' and autoclass:
            try:
                # 1. Clases Java
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                Uri = autoclass('android.net.Uri')
                File = autoclass('java.io.File')
                
                # 2. StrictMode Bypass
                StrictMode = autoclass('android.os.StrictMode')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                builder = Builder()
                StrictMode.setVmPolicy(builder.build())

                # 3. Rutas
                app = App.get_running_app()
                save_dir = app.path_puesto
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir, exist_ok=True)
                
                prefix = app.current_measurement_type[:3]
                filename = f"{prefix}_Video_{datetime.now().strftime('%H%M%S')}.mp4"
                file_path = os.path.join(save_dir, filename)
                
                # 4. Crear URI y CASTING (La solución al error)
                video_file = File(file_path)
                video_uri = Uri.fromFile(video_file)
                
                # --- AQUÍ ESTÁ LA MAGIA: Convertimos la URI a Parcelable explícitamente ---
                parcelable_uri = cast('android.os.Parcelable', video_uri)
                # ------------------------------------------------------------------------

                # 5. Intent
                intent = Intent(MediaStore.ACTION_VIDEO_CAPTURE)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, parcelable_uri)
                intent.putExtra(MediaStore.EXTRA_VIDEO_QUALITY, 1) # 1 = High Quality

                current_activity = PythonActivity.mActivity
                current_activity.startActivity(intent)
                
                self.status_info = "Guardando en carpeta..."
                
            except Exception as e:
                self.status_info = f"Error Video: {str(e)}"
                print(f"Error Video Trace: {e}")
        else:
            self.status_info = "Video solo en Android"

    def toggle_pause(self):
        if self.is_recording:
            self.is_paused = not self.is_paused
            if self.is_paused:
                self.play = False 
            else:
                self.play = True

    def exit_screen(self):
        self.stop_camera()
        app = App.get_running_app()
        app.root.current = 'review'

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
    font_size: sp(16)
    padding: [dp(10), dp(10)]
    multiline: False
    background_normal: ''
    background_active: ''
    canvas.after:
        Color:
            rgba: color_gold if self.focus else (0.3, 0.3, 0.3, 1)
        Line:
            width: dp(1.2)
            rectangle: (self.x, self.y, self.width, self.height)

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

<BotonCam@Button>:
    background_normal: '' 
    background_color: (0.2, 0.2, 0.2, 1)
    color: color_white
    font_size: sp(13)
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
    ExtinguisherFormScreen:
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
            text: "Relevamiento Inteligente"
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
                    text: "INCENDIOS (Extintores)"
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
                    text: "TERMOGRAFÍA (BETA)"
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
            text: "Ubicación / Sector"
            halign: 'left'
            text_size: self.size
            size_hint_y: None
            height: dp(30)
        TextInput:
            id: puesto_input
            hint_text: "Ej: Hall Central"
            size_hint_y: None
            height: dp(55)
        Widget:
            size_hint_y: 1
        BotonECAM:
            text: "ABRIR CÁMARA"
            on_release: root.iniciar_puesto()

<CameraScreen>:
    name: 'camera'
    on_pre_enter: root.setup_guides()
    FloatLayout:
        # CONTENEDOR ROTADO
        RelativeLayout:
            size_hint: (1, 1)
            canvas.before:
                PushMatrix
                Rotate:
                    angle: app.cam_rotation
                    origin: self.center
            canvas.after:
                PopMatrix
            
            KivyCamera:
                id: qrcam
                size_hint: (1, 1)
                # FORZAMOS EL LLENADO DE PANTALLA
                fit_mode: "cover" 
                allow_stretch: True
                keep_ratio: False
        
        # Mensajes
        Label:
            text: qrcam.status_info
            color: color_red
            font_size: sp(18)
            bold: True
            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
            halign: 'center'

        Image:
            id: guide_overlay
            source: app.current_guide_image
            size_hint: (1, 1)
            allow_stretch: True
            opacity: 0.4 if app.current_guide_image else 0
            fit_mode: "contain"

        # Info Superior
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

        # BOTONES LATERALES DE ZOOM
        BoxLayout:
            orientation: 'vertical'
            size_hint: (None, None)
            width: dp(60)
            height: dp(150)
            pos_hint: {'right': 0.98, 'center_y': 0.6}
            spacing: dp(10)

            BotonCam:
                text: "1x"
                background_color: (0, 0, 0, 0.5)
                on_release: qrcam.cambiar_lente('1x')
            
            BotonCam:
                text: "0.5x"
                background_color: (0, 0, 0, 0.5)
                on_release: qrcam.cambiar_lente('0.5x')

        # Botón Guía
        BotonCam:
            text: "GUÍA"
            size_hint: (None, None)
            size: (dp(60), dp(60))
            pos_hint: {'right': 0.98, 'center_y': 0.4}
            background_color: (0, 0, 0, 0.6)
            color: color_gold
            opacity: 1 if app.current_measurement_type == "ERGONOMIA" else 0
            disabled: True if app.current_measurement_type != "ERGONOMIA" else False
            on_release: app.cycle_guide()

        # Botón Especial EXTINTOR
        Button:
            text: "CARGAR\\nEXTINTOR"
            size_hint: (None, None)
            size: (dp(90), dp(90))
            pos_hint: {'right': 0.95, 'bottom': 0.2}
            background_color: (0.8, 0.1, 0.1, 1)
            bold: True
            font_size: sp(12)
            halign: 'center'
            opacity: 1 if app.current_measurement_type == "INCENDIOS" else 0
            disabled: True if app.current_measurement_type != "INCENDIOS" else False
            on_release: qrcam.take_photo(es_extintor=True)
            canvas.before:
                Color:
                    rgba: (0.8, 0.1, 0.1, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(45)]

        # Barra Inferior
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
                on_release: qrcam.take_photo(es_extintor=False)

            BotonCam:
                text: "GRABAR"
                font_size: sp(14)
                background_color: color_green
                on_release: qrcam.toggle_record_stop()
            
            BotonCam:
                text: "PAUSA"
                font_size: sp(14)
                background_color: color_gold
                disabled: not qrcam.is_recording
                opacity: 1 if qrcam.is_recording else 0.3
                on_release: qrcam.toggle_pause()
            
            BotonCam:
                text: "SALIR"
                color: color_black
                background_color: color_gold
                on_release: qrcam.exit_screen()

# --- PANTALLA MANUAL DE EXTINTORES ---
<ExtinguisherFormScreen>:
    name: 'extinguisher_form'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: color_black
            Rectangle:
                pos: self.pos
                size: self.size
        
        Label:
            text: "DATOS DEL EXTINTOR"
            font_size: sp(18)
            color: color_gold
            bold: True
            size_hint_y: None
            height: dp(30)

        Image:
            id: img_preview
            source: ''
            size_hint_y: 0.25
            allow_stretch: True

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
                
                TextInput:
                    id: ext_marca
                    hint_text: "Marca"
                    size_hint_y: None
                    height: dp(45)
                TextInput:
                    id: ext_tipo
                    hint_text: "Tipo (ABC, CO2, etc)"
                    size_hint_y: None
                    height: dp(45)
                TextInput:
                    id: ext_capacidad
                    hint_text: "Capacidad (kg)"
                    size_hint_y: None
                    height: dp(45)
                TextInput:
                    id: ext_fab
                    hint_text: "N° Fabricación"
                    size_hint_y: None
                    height: dp(45)
                TextInput:
                    id: ext_venc
                    hint_text: "Vencimiento Carga"
                    size_hint_y: None
                    height: dp(45)
                TextInput:
                    id: ext_ph
                    hint_text: "Vencimiento PH"
                    size_hint_y: None
                    height: dp(45)
                TextInput:
                    id: ext_empresa
                    hint_text: "Empresa Mantenedora"
                    size_hint_y: None
                    height: dp(45)

        BoxLayout:
            size_hint_y: None
            height: dp(50)
            spacing: dp(10)
            
            Button:
                text: "DESCARTAR"
                background_color: color_red
                on_release: root.cancelar()
            
            Button:
                text: "GUARDAR DATOS"
                background_color: color_green
                on_release: root.guardar_datos()

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
            hint_text: "Observaciones generales..."
            multiline: True
            size_hint_y: 1
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            spacing: dp(20)
            Button:
                text: "DESCARTAR"
                background_color: (0.5, 0.2, 0.2, 1)
                on_release: root.finalizar(guardar=False)
            Button:
                text: "GUARDAR"
                background_color: color_gold
                on_release: root.finalizar(guardar=True)
'''

class WelcomeScreen(Screen):
    pass

class ProjectScreen(Screen):
    def get_date(self):
        return datetime.now().strftime("%d/%m/%Y")
    
    def crear_proyecto(self):
        app = App.get_running_app()
        empresa = self.ids.empresa_input.text.strip()
        if empresa:
            app.current_company = empresa
            if platform == 'android':
                # GUARDA EN DESCARGAS
                from android.storage import primary_external_storage_path
                base_dir = primary_external_storage_path()
                app.path_empresa = os.path.join(base_dir, "Download", "CimaCam_Datos", empresa)
            else:
                base_dir = os.getcwd()
                app.path_empresa = os.path.join(base_dir, "CimaCam_Datos", empresa)
            
            if not os.path.exists(app.path_empresa):
                os.makedirs(app.path_empresa, exist_ok=True)
                
            app.mostrar_aviso("Carpeta Creada", f"Ruta: {app.path_empresa}")
            app.root.current = 'measurement'

class MeasurementScreen(Screen):
    def select_type(self, m_type):
        app = App.get_running_app()
        app.current_measurement_type = m_type
        app.root.current = 'job'

class JobScreen(Screen):
    def iniciar_puesto(self):
        app = App.get_running_app()
        puesto = self.ids.puesto_input.text.strip()
        if puesto:
            app.current_post = puesto
            folder = f"{app.current_measurement_type}_{puesto}_{datetime.now().strftime('%H%M')}"
            app.path_puesto = os.path.join(app.path_empresa, folder)
            if not os.path.exists(app.path_puesto):
                os.makedirs(app.path_puesto, exist_ok=True)
            
            cam = app.root.get_screen('camera').ids.qrcam
            cam.start_camera()
            app.root.current = 'camera'

class CameraScreen(Screen):
    def setup_guides(self):
        app = App.get_running_app()
        if app.current_measurement_type == "ERGONOMIA":
            app.current_guide_image = 'guia_frente.png'
        else:
            app.current_guide_image = ''

class ExtinguisherFormScreen(Screen):
    def cargar_imagen(self, path):
        self.ids.img_preview.source = path
        self.ids.ext_marca.text = ""
        self.ids.ext_tipo.text = ""
        self.ids.ext_capacidad.text = ""
        self.ids.ext_fab.text = ""
        self.ids.ext_venc.text = ""
        self.ids.ext_ph.text = ""
        self.ids.ext_empresa.text = ""

    def cancelar(self):
        app = App.get_running_app()
        app.root.current = 'camera'

    def guardar_datos(self):
        app = App.get_running_app()
        datos = [
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            app.current_post,
            os.path.basename(app.temp_photo_path),
            self.ids.ext_marca.text,
            self.ids.ext_tipo.text,
            self.ids.ext_capacidad.text,
            self.ids.ext_fab.text,
            self.ids.ext_venc.text,
            self.ids.ext_ph.text,
            self.ids.ext_empresa.text
        ]
        csv_file = os.path.join(app.path_empresa, f"Relevamiento_Extintores_{app.current_company}.csv")
        encabezados = ["Fecha", "Sector", "Foto", "Marca", "Tipo", "Capacidad", "N_Fab", "Venc_Carga", "Venc_PH", "Empresa"]
        es_nuevo = not os.path.exists(csv_file)
        try:
            with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                if es_nuevo: writer.writerow(encabezados)
                writer.writerow(datos)
            app.mostrar_aviso("Guardado", f"Datos en:\n{csv_file}")
        except Exception as e:
            print(f"Error CSV: {e}")
            app.mostrar_aviso("Error", str(e))
        app.root.current = 'camera'

class ReviewScreen(Screen):
    def actualizar_hint(self):
        app = App.get_running_app()
        m = app.current_measurement_type
        w = self.ids.notas_input
        if m == "ERGONOMIA": w.hint_text = "Carga (kg), Frecuencia, Posturas..."
        elif m == "RUIDO": w.hint_text = "Nivel dBA, Fuente de ruido..."
        elif m == "TERMOGRAFIA": w.hint_text = "Componente (Tablero/Cable), Temp Max..."
        else: w.hint_text = "Observaciones generales..."

    def finalizar(self, guardar=True):
        app = App.get_running_app()
        cam_screen = app.root.get_screen('camera')
        if hasattr(cam_screen.ids, 'qrcam'):
            cam_screen.ids.qrcam.stop_camera()
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
                app.mostrar_aviso("Informe Guardado", f"Archivo:\n{fname}")
        self.ids.notas_input.text = ""
        app.root.current = 'measurement'

class CimaCamApp(App):
    current_company = StringProperty("")
    current_post = StringProperty("")
    current_measurement_type = StringProperty("ERGONOMIA")
    path_empresa = ""
    path_puesto = ""
    temp_photo_path = "" 
    guide_list = ListProperty(['guia_frente.png', 'guia_perfil.png', 'guia_admin_perfil.png', 'guia_admin_frente.png', 'guia_levantamiento.png'])
    current_guide_index = NumericProperty(0)
    current_guide_image = StringProperty('')
    
    # --- VARIABLE DE ROTACIÓN ---
    cam_rotation = NumericProperty(0) 

    def cycle_guide(self):
        if self.current_measurement_type == "ERGONOMIA":
            self.current_guide_index = (self.current_guide_index + 1) % len(self.guide_list)
            self.current_guide_image = self.guide_list[self.current_guide_index]

    def mostrar_aviso(self, titulo, mensaje):
        content = BoxLayout(orientation='vertical', padding=10)
        content.add_widget(Label(text=mensaje, font_size='14sp', halign='center'))
        btn = Factory.BotonECAM(text="OK", size_hint=(1, 0.3))
        content.add_widget(btn)
        popup = Popup(title=titulo, content=content, size_hint=(0.8, 0.4))
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def build(self):
        Window.bind(on_keyboard=self.on_key)
        
        # --- ROTACIÓN AJUSTADA A 270 GRADOS ---
        if platform == 'android':
            self.cam_rotation = 270
        else:
            self.cam_rotation = 0

        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.RECORD_AUDIO,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])
        return Builder.load_string(KV)

    def on_key(self, window, key, *args):
        if key == 27:
            sm = self.root
            if sm.current == 'extinguisher_form':
                sm.current = 'camera'
                return True
            elif sm.current == 'camera':
                sm.get_screen('camera').ids.qrcam.stop_camera()
                sm.current = 'job'
                return True
            elif sm.current == 'job':
                sm.current = 'measurement'
                return True
            elif sm.current == 'measurement':
                sm.current = 'project'
                return True
            return False

if __name__ == '__main__':
    CimaCamApp().run()
