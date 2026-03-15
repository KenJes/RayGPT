"""
Cliente de Google Workspace - Docs, Drive, Sheets, Calendar
"""
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    import requests
    import io
    from PIL import Image
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

CORE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = CORE_DIR.parent
DATA_DIR = RESOURCES_DIR / "data"


def _resolve_data_file(path_like):
    """Resolve files relocated into resources/data while preserving overrides."""
    candidate = Path(path_like)
    if candidate.exists():
        return candidate
    if candidate.is_absolute():
        return candidate
    fallback = DATA_DIR / (candidate if candidate.parent == Path('.') else candidate.name)
    if fallback.exists():
        return fallback
    return fallback

class GoogleWorkspaceClient:
    """Cliente para interactuar con Google Workspace APIs"""
    
    # Scopes necesarios para todas las operaciones
    SCOPES = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/presentations',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/youtube.readonly',
    ]
    
    def __init__(self, service_account_file):
        """
        Inicializa cliente con OAuth (preferido) o Service Account (fallback)
        
        Args:
            service_account_file: Ruta al archivo JSON de credenciales (opcional si existe token.json)
        """
        self.credentials = None
        self.docs_service = None
        self.drive_service = None
        self.sheets_service = None
        self.calendar_service = None
        self.slides_service = None
        self.youtube_service = None
        self.auth_type = None
        self.pexels_api_key = os.environ.get('PEXELS_API_KEY')
        
        if not GOOGLE_AVAILABLE:
            print("⚠️ Google APIs no instaladas. Ejecuta: pip install -r requirements.txt")
            return
        
        # PRIORIDAD 1: OAuth token.json (para Gmail personal)
        token_path = _resolve_data_file('token.json')
        if token_path.exists():
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    str(token_path),
                    self.SCOPES
                )
                
                # Auto-refresh si el token expiró
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    print("🔄 Token OAuth expirado, refrescando automáticamente...")
                    self.credentials.refresh(GoogleAuthRequest())
                    # Guardar token actualizado
                    with open(str(token_path), 'w') as f:
                        f.write(self.credentials.to_json())
                    print("✅ Token OAuth refrescado y guardado")
                
                self.auth_type = 'oauth'
                print("✅ Usando autenticación OAuth (Gmail personal)")
            except Exception as e:
                print(f"⚠️ Error al cargar/refrescar token OAuth: {e}")
                print("   Ejecuta: python resources/scripts/autorizar_google.py para re-autorizar")
                self.credentials = None
        
        # PRIORIDAD 2: Service Account (para Google Workspace)
        if self.credentials is None:
            creds_path = _resolve_data_file(service_account_file)
            if not creds_path.exists():
                print(f"⚠️ No se encontró token.json ni {creds_path}")
                print("   Ejecuta: python autorizar_google.py")
                return
            
            try:
                self.credentials = service_account.Credentials.from_service_account_file(
                    str(creds_path),
                    scopes=self.SCOPES
                )
                self.auth_type = 'service_account'
                print("✅ Usando Service Account (Google Workspace)")
            except Exception as e:
                print(f"❌ Error al cargar credenciales: {e}")
                return
        
        # Inicializar servicios de Google
        try:
            self.docs_service = build('docs', 'v1', credentials=self.credentials)
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
            self.slides_service = build('slides', 'v1', credentials=self.credentials)
            self.calendar_service = build('calendar', 'v3', credentials=self.credentials)
            self.youtube_service = build('youtube', 'v3', credentials=self.credentials)
            
            print("✅ Google Workspace y YouTube conectados correctamente")
            
        except Exception as e:
            print(f"❌ Error al inicializar servicios de Google: {e}")
    
    def is_available(self):
        """Verifica si el cliente está disponible"""
        return self.credentials is not None
    
    # ═══════════════════════════════════════════════════════════════
    # GOOGLE DOCS
    # ═══════════════════════════════════════════════════════════════
    
    def crear_documento(self, titulo, contenido=""):
        """
        Crea un documento de Google Docs
        
        Args:
            titulo: Título del documento
            contenido: Contenido inicial (opcional)
        
        Returns:
            dict: {'id': doc_id, 'url': doc_url}
        """
        if not self.is_available():
            return None
        
        try:
            # Crear documento vacío
            doc = self.docs_service.documents().create(
                body={'title': titulo}
            ).execute()
            
            doc_id = doc.get('documentId')
            
            # Añadir contenido si se proporciona
            if contenido:
                requests = [
                    {
                        'insertText': {
                            'location': {'index': 1},
                            'text': contenido
                        }
                    }
                ]
                
                self.docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
            
            url = f"https://docs.google.com/document/d/{doc_id}/edit"
            
            return {
                'id': doc_id,
                'url': url,
                'titulo': titulo
            }
            
        except HttpError as e:
            print(f"❌ Error al crear documento: {e}")
            return None
    
    def leer_documento(self, doc_id):
        """
        Lee el contenido de un documento
        
        Args:
            doc_id: ID del documento
        
        Returns:
            str: Contenido del documento
        """
        if not self.is_available():
            return None
        
        try:
            doc = self.docs_service.documents().get(documentId=doc_id).execute()
            
            # Extraer texto
            content = doc.get('body', {}).get('content', [])
            text = ''
            
            for element in content:
                if 'paragraph' in element:
                    for text_run in element['paragraph']['elements']:
                        if 'textRun' in text_run:
                            text += text_run['textRun']['content']
            
            return text
            
        except HttpError as e:
            print(f"❌ Error al leer documento: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════
    # GOOGLE DRIVE
    # ═══════════════════════════════════════════════════════════════
    
    def listar_archivos(self, query='', max_results=10):
        """
        Lista archivos en Google Drive
        
        Args:
            query: Consulta de búsqueda (opcional)
            max_results: Número máximo de resultados
        
        Returns:
            list: Lista de archivos
        """
        if not self.is_available():
            return []
        
        try:
            results = self.drive_service.files().list(
                q=query,
                pageSize=max_results,
                fields="files(id, name, mimeType, createdTime, modifiedTime)"
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as e:
            print(f"❌ Error al listar archivos: {e}")
            return []
    
    def compartir_archivo(self, file_id, email, role='reader'):
        """
        Comparte un archivo con un usuario
        
        Args:
            file_id: ID del archivo
            email: Email del usuario
            role: Rol ('reader', 'writer', 'owner')
        
        Returns:
            bool: True si se compartió correctamente
        """
        if not self.is_available():
            return False
        
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            
            self.drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"❌ Error al compartir archivo: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # GOOGLE SHEETS
    # ═══════════════════════════════════════════════════════════════
    
    def crear_hoja_calculo(self, titulo):
        """
        Crea una hoja de cálculo
        
        Args:
            titulo: Título de la hoja
        
        Returns:
            dict: {'id': sheet_id, 'url': sheet_url}
        """
        if not self.is_available():
            return None
        
        try:
            spreadsheet = {
                'properties': {
                    'title': titulo
                }
            }
            
            sheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId'
            ).execute()
            
            sheet_id = sheet.get('spreadsheetId')
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
            
            return {
                'id': sheet_id,
                'url': url,
                'titulo': titulo
            }
            
        except HttpError as e:
            print(f"❌ Error al crear hoja: {e}")
            return None
    
    def escribir_datos(self, sheet_id, range_name, values):
        """
        Escribe datos en una hoja
        
        Args:
            sheet_id: ID de la hoja
            range_name: Rango (ej: 'Sheet1!A1:C3')
            values: Lista de listas con los datos
        
        Returns:
            bool: True si se escribió correctamente
        """
        if not self.is_available():
            return False
        
        try:
            body = {
                'values': values
            }
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"❌ Error al escribir datos: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # GOOGLE CALENDAR
    # ═══════════════════════════════════════════════════════════════
    
    def crear_evento(self, titulo, fecha_inicio, fecha_fin, descripcion="", ubicacion="", recordatorio_minutos=30):
        """
        Crea un evento en el calendario con alarma/recordatorio

        Args:
            titulo: Título del evento
            fecha_inicio: datetime del inicio
            fecha_fin: datetime del fin
            descripcion: Descripción (opcional)
            ubicacion: Ubicación (opcional)
            recordatorio_minutos: Minutos antes del evento para la alarma (default 30)

        Returns:
            dict: Información del evento creado
        """
        if not self.is_available() or not self.calendar_service:
            print("⚠️ Google Calendar no está disponible o no ha sido inicializado.")
            return None

        try:
            event = {
                'summary': titulo,
                'location': ubicacion,
                'description': descripcion,
                'start': {
                    'dateTime': fecha_inicio.isoformat(),
                    'timeZone': 'America/Mexico_City',
                },
                'end': {
                    'dateTime': fecha_fin.isoformat(),
                    'timeZone': 'America/Mexico_City',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup',  'minutes': recordatorio_minutos},
                        {'method': 'email',  'minutes': recordatorio_minutos},
                    ],
                },
            }
            
            print(f"📅 Llamando API de Calendar para insertar evento: {titulo}")
            print(f"   Inicio: {fecha_inicio.isoformat()}")
            print(f"   Fin: {fecha_fin.isoformat()}")
            
            event_result = self.calendar_service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            event_id = event_result.get('id')
            print(f"✅ Evento guardado exitosamente en Google Calendar")
            print(f"   ID del evento: {event_id}")
            print(f"   URL: {event_result.get('htmlLink')}")
            
            return {
                'id': event_id,
                'url': event_result.get('htmlLink'),
                'titulo': titulo
            }
            
        except Exception as e:
            print(f"❌ Error al crear evento en Google Calendar: {type(e).__name__}: {e}")
            return None
    
    def listar_eventos_proximos(self, max_results=10):
        """
        Lista los próximos eventos del calendario
        
        Args:
            max_results: Número máximo de resultados
        
        Returns:
            list: Lista de eventos
        """
        if not self.is_available():
            return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
            
        except HttpError as e:
            print(f"❌ Error al listar eventos: {e}")
            return []
    
    def exportar_presentacion_pptx(self, presentation_id, output_path):
        """
        Exporta una presentación de Google Slides a formato PPTX
        
        Args:
            presentation_id: ID de la presentación en Google Slides
            output_path: Ruta donde guardar el archivo .pptx
        
        Returns:
            str: Ruta del archivo guardado o None si hay error
        """
        if not self.is_available():
            return None
        
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            # Exportar presentación como PPTX
            request = self.drive_service.files().export_media(
                fileId=presentation_id,
                mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation'
            )
            
            # Descargar a memoria
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    print(f"⬇️ Descargando... {int(status.progress() * 100)}%")
            
            # Guardar archivo
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            print(f"✅ Presentación exportada: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error al exportar presentación: {e}")
            return None
    
    def exportar_documento_docx(self, document_id, output_path):
        """
        Exporta un documento de Google Docs a formato DOCX
        
        Args:
            document_id: ID del documento en Google Docs
            output_path: Ruta donde guardar el archivo .docx
        
        Returns:
            str: Ruta del archivo guardado o None si hay error
        """
        if not self.is_available():
            return None
        
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            request = self.drive_service.files().export_media(
                fileId=document_id,
                mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    print(f"⬇️ Descargando... {int(status.progress() * 100)}%")
            
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            print(f"✅ Documento exportado: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error al exportar documento: {e}")
            return None
    
    def exportar_hoja_calculo_xlsx(self, spreadsheet_id, output_path):
        """
        Exporta una hoja de cálculo de Google Sheets a formato XLSX
        
        Args:
            spreadsheet_id: ID de la hoja de cálculo en Google Sheets
            output_path: Ruta donde guardar el archivo .xlsx
        
        Returns:
            str: Ruta del archivo guardado o None si hay error
        """
        if not self.is_available():
            return None
        
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            request = self.drive_service.files().export_media(
                fileId=spreadsheet_id,
                mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    print(f"⬇️ Descargando... {int(status.progress() * 100)}%")
            
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            print(f"✅ Hoja de cálculo exportada: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error al exportar hoja de cálculo: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════
    # GOOGLE SLIDES (PRESENTACIONES)
    # ═══════════════════════════════════════════════════════════════
    
    def crear_presentacion(self, titulo, diapositivas=None, tema_visual=None):
        """
        Crea una presentación con contenido usando batch requests optimizados.
        Solo hace ~4 llamadas API sin importar la cantidad de diapositivas.
        
        Args:
            titulo: Título de la presentación
            diapositivas: Lista de dicts con estructura:
                [{
                    'tipo': 'portada|contenido|conclusion',
                    'titulo': 'Título de la diapositiva',
                    'subtitulo': 'Subtítulo (solo para portada)',
                    'contenido': 'Texto del contenido',
                    'imagen_url': 'URL de imagen (opcional)'
                }]
        
        Returns:
            dict: {'id': presentation_id, 'url': presentation_url, 'titulo': titulo}
        """
        if not self.is_available():
            return None
        
        try:
            # ── PASO 1: Crear presentación base (1 API call) ──
            presentation = self.slides_service.presentations().create(
                body={'title': titulo}
            ).execute()
            
            presentation_id = presentation.get('presentationId')
            primera_slide_id = presentation['slides'][0]['objectId']
            
            if not diapositivas:
                url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
                return {'id': presentation_id, 'url': url, 'titulo': titulo}
            
            print(f"📄 Creando {len(diapositivas)} diapositivas en modo batch...")
            
            # ── PASO 2: Crear todas las diapositivas de golpe (1 API call) ──
            from uuid import uuid4
            slide_ids = []
            create_requests = []
            
            for idx, diapositiva in enumerate(diapositivas):
                tipo_slide = diapositiva.get('tipo', 'contenido')
                slide_id = f'slide_{uuid4().hex[:10]}'
                slide_ids.append(slide_id)

                # BLANK para slides con imagen (control total de posición)
                tiene_imagen = bool(diapositiva.get('imagen_url'))
                if tipo_slide == 'portada':
                    layout = 'TITLE'
                elif tiene_imagen:
                    layout = 'BLANK'
                else:
                    layout = 'TITLE_AND_BODY'
                
                create_requests.append({
                    'createSlide': {
                        'objectId': slide_id,
                        'insertionIndex': idx,
                        'slideLayoutReference': {
                            'predefinedLayout': layout
                        }
                    }
                })
            
            # Crear todas las slides + eliminar la slide vacía inicial
            create_requests.append({
                'deleteObject': {'objectId': primera_slide_id}
            })
            
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': create_requests}
            ).execute()
            
            print(f"   ✅ {len(diapositivas)} diapositivas creadas")
            
            # ── PASO 3: Leer placeholders de todas las slides (1 API call) ──
            full_pres = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()
            
            # Mapear slide_id → {title_placeholder_id, body_placeholder_id}
            placeholder_map = {}
            for slide in full_pres.get('slides', []):
                sid = slide.get('objectId')
                placeholders = {'title': None, 'body': None}
                for element in slide.get('pageElements', []):
                    shape = element.get('shape', {})
                    ph = shape.get('placeholder', {})
                    ph_type = ph.get('type', '')
                    if ph_type == 'TITLE' or ph_type == 'CENTERED_TITLE':
                        placeholders['title'] = element.get('objectId')
                    elif ph_type in ('BODY', 'SUBTITLE'):
                        placeholders['body'] = element.get('objectId')
                placeholder_map[sid] = placeholders
            
            # ── PASO 4: Insertar TODO el contenido de golpe (1 API call) ──
            content_requests = []
            # Paleta de fondos: varia sutilmente por slide
            BG_COLORS = [
                {'red': 0.08,  'green': 0.08,  'blue': 0.10},   # 0: portada (más oscuro)
                {'red': 0.11,  'green': 0.14,  'blue': 0.13},   # 1: verde oscuro
                {'red': 0.10,  'green': 0.11,  'blue': 0.17},   # 2: azul oscuro
                {'red': 0.13,  'green': 0.11,  'blue': 0.11},   # 3: rojizo oscuro
                {'red': 0.09,  'green': 0.13,  'blue': 0.15},   # 4: teal oscuro
                {'red': 0.12,  'green': 0.10,  'blue': 0.14},   # 5: púrpura oscuro
            ]
            ACCENT = {'red': 0.24, 'green': 0.82, 'blue': 0.64}   # verde Axoloit
            FG     = {'red': 0.93, 'green': 0.93, 'blue': 0.93}   # texto claro
            FG_DIM = {'red': 0.70, 'green': 0.70, 'blue': 0.70}   # texto atenuado

            image_count = 0  # para alternar izquierda/derecha

            for idx, diapositiva in enumerate(diapositivas):
                sid        = slide_ids[idx]
                tipo_slide = diapositiva.get('tipo', 'contenido')
                phs        = placeholder_map.get(sid, {})
                titulo_text = diapositiva.get('titulo', '')
                imagen_url  = diapositiva.get('imagen_url')
                is_blank    = bool(imagen_url) and tipo_slide == 'contenido'

                print(f"   📝 Preparando slide {idx+1}/{len(diapositivas)} ({tipo_slide}): {titulo_text[:40]}...")

                # ── Fondo variado por slide ──
                bg = BG_COLORS[0] if tipo_slide == 'portada' else BG_COLORS[(idx % (len(BG_COLORS) - 1)) + 1]
                content_requests.append({
                    'updatePageProperties': {
                        'objectId': sid,
                        'pageProperties': {
                            'pageBackgroundFill': {
                                'solidFill': {'color': {'rgbColor': bg}}
                            }
                        },
                        'fields': 'pageBackgroundFill.solidFill.color'
                    }
                })

                if is_blank:
                    # ══ BLANK layout: posicionamiento manual texto + imagen lado a lado ══
                    # Página 16:9 = 720pt × 405pt
                    # Título: franja superior 62pt
                    # Contenido: y=70, h=322
                    image_on_right = (image_count % 2 == 0)
                    image_count += 1

                    if image_on_right:
                        txt_x, txt_w = 18,  320
                        img_x, img_w = 354, 348
                    else:
                        img_x, img_w = 12,  330
                        txt_x, txt_w = 360, 348

                    # Caja de título (ancho completo)
                    tid = f'ttl_{uuid4().hex[:8]}'
                    content_requests += [
                        {'createShape': {
                            'objectId': tid, 'shapeType': 'TEXT_BOX',
                            'elementProperties': {
                                'pageObjectId': sid,
                                'size': {
                                    'width':  {'magnitude': 684, 'unit': 'PT'},
                                    'height': {'magnitude': 56,  'unit': 'PT'}
                                },
                                'transform': {'scaleX': 1, 'scaleY': 1,
                                              'translateX': 18, 'translateY': 8, 'unit': 'PT'}
                            }
                        }},
                    ]
                    if titulo_text:
                        content_requests += [
                            {'insertText': {'objectId': tid, 'text': titulo_text, 'insertionIndex': 0}},
                            {'updateTextStyle': {
                                'objectId': tid, 'textRange': {'type': 'ALL'},
                                'style': {
                                    'bold': True,
                                    'fontSize': {'magnitude': 22, 'unit': 'PT'},
                                    'foregroundColor': {'opaqueColor': {'rgbColor': ACCENT}}
                                },
                                'fields': 'bold,fontSize,foregroundColor'
                            }},
                        ]

                    # Caja de contenido de texto
                    bid = f'bdy_{uuid4().hex[:8]}'
                    contenido = diapositiva.get('contenido', '')
                    content_requests.append({'createShape': {
                        'objectId': bid, 'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': sid,
                            'size': {
                                'width':  {'magnitude': txt_w, 'unit': 'PT'},
                                'height': {'magnitude': 322,   'unit': 'PT'}
                            },
                            'transform': {'scaleX': 1, 'scaleY': 1,
                                          'translateX': txt_x, 'translateY': 72, 'unit': 'PT'}
                        }
                    }})
                    if contenido:
                        content_requests += [
                            {'insertText': {'objectId': bid, 'text': contenido, 'insertionIndex': 0}},
                            {'updateTextStyle': {
                                'objectId': bid, 'textRange': {'type': 'ALL'},
                                'style': {
                                    'fontSize': {'magnitude': 13, 'unit': 'PT'},
                                    'foregroundColor': {'opaqueColor': {'rgbColor': FG}}
                                },
                                'fields': 'fontSize,foregroundColor'
                            }},
                            # Auto-ajuste de texto si es largo
                            {'updateShapeProperties': {
                                'objectId': bid,
                                'shapeProperties': {
                                    'autofit': {'autofitType': 'TEXT_AUTOFIT'}
                                },
                                'fields': 'autofit'
                            }},
                        ]

                    # Imagen (con margen)
                    iid = f'img_{uuid4().hex[:8]}'
                    content_requests.append({
                        'createImage': {
                            'objectId': iid, 'url': imagen_url,
                            'elementProperties': {
                                'pageObjectId': sid,
                                'size': {
                                    'width':  {'magnitude': img_w - 12, 'unit': 'PT'},
                                    'height': {'magnitude': 310,         'unit': 'PT'}
                                },
                                'transform': {'scaleX': 1, 'scaleY': 1,
                                              'translateX': img_x + 6, 'translateY': 76, 'unit': 'PT'}
                            }
                        }
                    })

                else:
                    # ══ Layout estándar: TITLE / TITLE_AND_BODY con placeholders ══
                    title_ph = phs.get('title')
                    if titulo_text and title_ph:
                        content_requests.append({
                            'insertText': {'objectId': title_ph, 'text': titulo_text, 'insertionIndex': 0}
                        })
                        content_requests.append({
                            'updateTextStyle': {
                                'objectId': title_ph, 'textRange': {'type': 'ALL'},
                                'style': {
                                    'bold': True,
                                    'foregroundColor': {'opaqueColor': {'rgbColor': ACCENT}}
                                },
                                'fields': 'bold,foregroundColor'
                            }
                        })

                    body_ph = phs.get('body')
                    if tipo_slide == 'portada':
                        subtitulo = diapositiva.get('subtitulo', '')
                        if subtitulo and body_ph:
                            content_requests.append({
                                'insertText': {'objectId': body_ph, 'text': subtitulo, 'insertionIndex': 0}
                            })
                            content_requests.append({
                                'updateTextStyle': {
                                    'objectId': body_ph, 'textRange': {'type': 'ALL'},
                                    'style': {
                                        'fontSize': {'magnitude': 20, 'unit': 'PT'},
                                        'foregroundColor': {'opaqueColor': {'rgbColor': FG_DIM}}
                                    },
                                    'fields': 'fontSize,foregroundColor'
                                }
                            })
                    else:
                        contenido = diapositiva.get('contenido', '')
                        if contenido and body_ph:
                            content_requests.append({
                                'insertText': {'objectId': body_ph, 'text': contenido, 'insertionIndex': 0}
                            })
                            content_requests.append({
                                'updateTextStyle': {
                                    'objectId': body_ph, 'textRange': {'type': 'ALL'},
                                    'style': {
                                        'fontSize': {'magnitude': 15, 'unit': 'PT'},
                                        'foregroundColor': {'opaqueColor': {'rgbColor': FG}}
                                    },
                                    'fields': 'fontSize,foregroundColor'
                                }
                            })
                            content_requests.append({
                                'updateShapeProperties': {
                                    'objectId': body_ph,
                                    'shapeProperties': {
                                        'autofit': {'autofitType': 'TEXT_AUTOFIT'}
                                    },
                                    'fields': 'autofit'
                                }
                            })
            
            # Enviar TODO el contenido en una sola llamada
            if content_requests:
                print(f"   🚀 Enviando {len(content_requests)} operaciones en batch...")
                try:
                    self.slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={'requests': content_requests}
                    ).execute()
                except HttpError as e:
                    if e.resp.status == 429:
                        # Rate limit: esperar y reintentar UNA vez
                        import time
                        print("   ⏳ Rate limit alcanzado, esperando 60s y reintentando...")
                        time.sleep(60)
                        self.slides_service.presentations().batchUpdate(
                            presentationId=presentation_id,
                            body={'requests': content_requests}
                        ).execute()
                    elif 'image' in str(e).lower() or 'url' in str(e).lower():
                        # Si falla por una imagen, reintentar sin imágenes
                        print("   ⚠️ Error con imágenes, reintentando solo texto...")
                        text_only = [r for r in content_requests if 'createImage' not in r]
                        if text_only:
                            self.slides_service.presentations().batchUpdate(
                                presentationId=presentation_id,
                                body={'requests': text_only}
                            ).execute()
                    else:
                        raise
            
            print("✅ Contenido agregado correctamente")
            
            url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
            
            return {
                'id': presentation_id,
                'url': url,
                'titulo': titulo
            }
            
        except HttpError as e:
            error_reason = e.reason if hasattr(e, 'reason') else str(e)
            
            if e.resp.status == 403:
                error_msg = str(e)
                sa_email = getattr(self.credentials, 'service_account_email', 'tu-service-account')
                project_id = getattr(self.credentials, 'project_id', 'trace-cf294') or 'trace-cf294'
                
                # Google devuelve PERMISSION_DENIED tanto si la API no está habilitada
                # como si faltan permisos IAM. Analizamos el mensaje para distinguir.
                if 'has not been used' in error_msg or 'is disabled' in error_msg:
                    # API no habilitada (mensaje explícito de Google)
                    print(f"❌ Error 403: Google Slides API no habilitada")
                    print(f"")
                    print(f"📋 SOLUCIÓN: Habilita la API en:")
                    print(f"   https://console.cloud.google.com/apis/library/slides.googleapis.com?project={project_id}")
                    return {
                        'error': 'API_NOT_ENABLED',
                        'message': 'Google Slides API no habilitada en el proyecto.',
                        'instrucciones': f'Habilita Google Slides API en Google Cloud Console',
                        'link': f'https://console.cloud.google.com/apis/library/slides.googleapis.com?project={project_id}'
                    }
                else:
                    # PERMISSION_DENIED genérico - probablemente la API no está habilitada
                    # (Google a menudo no incluye "has not been used" en el mensaje)
                    print(f"❌ Error 403: {error_reason}")
                    print(f"")
                    print(f"📋 CAUSA MÁS PROBABLE: Google Slides API no está habilitada")
                    print(f"")
                    print(f"🔧 SOLUCIÓN (habilitar APIs):")
                    print(f"   1. Slides: https://console.cloud.google.com/apis/library/slides.googleapis.com?project={project_id}")
                    print(f"   2. Docs:   https://console.cloud.google.com/apis/library/docs.googleapis.com?project={project_id}")
                    print(f"   3. Sheets: https://console.cloud.google.com/apis/library/sheets.googleapis.com?project={project_id}")
                    print(f"   Haz click en 'ENABLE' en cada una.")
                    print(f"")
                    print(f"   Service Account: {sa_email}")
                    print(f"   Detalle: {error_reason}")
                    return {
                        'error': 'API_NOT_ENABLED',
                        'message': f'Error 403: Probablemente Google Slides API no está habilitada. Habilítala en Google Cloud Console.',
                        'instrucciones': f'Habilita las APIs de Google Workspace (Slides, Docs, Sheets) en tu proyecto {project_id}',
                        'link': f'https://console.cloud.google.com/apis/library/slides.googleapis.com?project={project_id}'
                    }
            else:
                print(f"❌ Error al crear presentación: {e}")
                return None
    
    def agregar_diapositiva(self, presentation_id, layout='TITLE_AND_BODY'):
        """
        Agrega una diapositiva a la presentación
        
        Args:
            presentation_id: ID de la presentación
            layout: Tipo de layout ('BLANK', 'TITLE_AND_BODY', 'TITLE_ONLY', etc.)
        
        Returns:
            str: ID de la diapositiva creada
        """
        if not self.is_available():
            return None
        
        try:
            # Obtener layout ID
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()
            
            # Buscar el layout apropiado
            layouts = presentation.get('layouts', [])
            layout_id = None
            
            for l in layouts:
                if layout in l.get('layoutProperties', {}).get('name', ''):
                    layout_id = l.get('objectId')
                    break
            
            # Si no se encuentra, usar el primer layout disponible
            if not layout_id and layouts:
                layout_id = layouts[0].get('objectId')
            
            # Crear la diapositiva
            requests = [
                {
                    'createSlide': {
                        'slideLayoutReference': {
                            'predefinedLayout': layout
                        }
                    }
                }
            ]
            
            response = self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()
            
            slide_id = response.get('replies', [{}])[0].get('createSlide', {}).get('objectId')
            return slide_id
            
        except HttpError as e:
            print(f"❌ Error al agregar diapositiva: {e}")
            return None
    
    def agregar_texto_diapositiva(self, presentation_id, slide_id, texto, es_titulo=False, estilos_texto=None):
        """
        Agrega texto a una diapositiva
        
        Args:
            presentation_id: ID de la presentación
            slide_id: ID de la diapositiva
            texto: Texto a agregar
            es_titulo: Si es True, lo agrega al placeholder de título
        
        Returns:
            bool: True si se agregó correctamente
        """
        if not self.is_available():
            return False
        
        try:
            # Obtener información de la diapositiva
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()
            
            # Buscar la diapositiva
            slide = None
            for s in presentation.get('slides', []):
                if s.get('objectId') == slide_id:
                    slide = s
                    break
            
            if not slide:
                return False
            
            # Buscar el elemento de texto apropiado
            page_elements = slide.get('pageElements', [])
            text_box_id = None
            
            for element in page_elements:
                shape = element.get('shape', {})
                placeholder = shape.get('placeholder', {})
                
                if es_titulo and placeholder.get('type') == 'TITLE':
                    text_box_id = element.get('objectId')
                    break
                elif not es_titulo and placeholder.get('type') in ['BODY', 'SUBTITLE']:
                    text_box_id = element.get('objectId')
                    break
            
            if not text_box_id:
                # Si no hay placeholder, crear un text box
                return self._crear_text_box(presentation_id, slide_id, texto)
            
            # Insertar texto
            requests = [
                {
                    'insertText': {
                        'objectId': text_box_id,
                        'text': texto,
                        'insertionIndex': 0
                    }
                }
            ]
            
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()
            
            if estilos_texto:
                self._aplicar_estilos_texto(presentation_id, text_box_id, estilos_texto)
            
            return True
            
        except HttpError as e:
            print(f"❌ Error al agregar texto: {e}")
            return False
    
    def _crear_text_box(self, presentation_id, slide_id, texto):
        """
        Crea un text box en una diapositiva
        
        Args:
            presentation_id: ID de la presentación
            slide_id: ID de la diapositiva
            texto: Texto a agregar
        
        Returns:
            bool: True si se creó correctamente
        """
        try:
            # Generar ID único
            from uuid import uuid4
            text_box_id = f'TextBox_{uuid4().hex[:8]}'
            
            requests = [
                {
                    'createShape': {
                        'objectId': text_box_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 300, 'unit': 'PT'},
                                'height': {'magnitude': 200, 'unit': 'PT'}
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 50,
                                'translateY': 100,
                                'unit': 'PT'
                            }
                        }
                    }
                },
                {
                    'insertText': {
                        'objectId': text_box_id,
                        'text': texto
                    }
                }
            ]
            
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"❌ Error al crear text box: {e}")
            return False

    def _aplicar_estilo_diapositiva(self, presentation_id, slide_id, tema_visual):
        """Actualiza el fondo de una diapositiva según el tema visual"""
        if not tema_visual:
            return
        color = tema_visual.get('color_fondo')
        if not color:
            return
        try:
            requests = [{
                'updatePageProperties': {
                    'objectId': slide_id,
                    'pageProperties': {
                        'pageBackgroundFill': {
                            'solidFill': {
                                'color': {'rgbColor': color}
                            }
                        }
                    },
                    'fields': 'pageBackgroundFill.solidFill.color'
                }
            }]
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()
        except HttpError as e:
            print(f"⚠️ No se pudo aplicar fondo personalizado: {e}")

    def _build_text_style_request(self, object_id, estilos):
        """Construye un request de estilo de texto para incluir en batch (sin llamar a la API)"""
        if not estilos:
            return None
        style = {}
        fields = []
        color = estilos.get('color')
        font = estilos.get('fuente')
        size = estilos.get('tamano')
        bold = estilos.get('bold', False)
        if color:
            style['foregroundColor'] = {'opaqueColor': {'rgbColor': color}}
            fields.append('foregroundColor')
        if font:
            style['fontFamily'] = font
            fields.append('fontFamily')
        if size:
            style['fontSize'] = {'magnitude': size, 'unit': 'PT'}
            fields.append('fontSize')
        if bold:
            style['bold'] = True
            fields.append('bold')
        if not fields:
            return None
        return {
            'updateTextStyle': {
                'objectId': object_id,
                'textRange': {'type': 'ALL'},
                'style': style,
                'fields': ','.join(fields)
            }
        }

    def _aplicar_estilos_texto(self, presentation_id, object_id, estilos):
        """Aplica colores y fuentes al texto de un shape"""
        style = {}
        fields = []
        color = estilos.get('color') if estilos else None
        font = estilos.get('fuente') if estilos else None
        size = estilos.get('tamano') if estilos else None
        bold = estilos.get('bold') if estilos else False
        if color:
            style['foregroundColor'] = {
                'opaqueColor': {
                    'rgbColor': color
                }
            }
            fields.append('foregroundColor')
        if font:
            style['fontFamily'] = font
            fields.append('fontFamily')
        if size:
            style['fontSize'] = {'magnitude': size, 'unit': 'PT'}
            fields.append('fontSize')
        if bold:
            style['bold'] = True
            fields.append('bold')
        if not fields:
            return
        try:
            request = {
                'updateTextStyle': {
                    'objectId': object_id,
                    'textRange': {'type': 'ALL'},
                    'style': style,
                    'fields': ','.join(fields)
                }
            }
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [request]}
            ).execute()
        except HttpError as e:
            print(f"⚠️ No se pudieron aplicar estilos de texto: {e}")
    
    def agregar_imagen_diapositiva(self, presentation_id, slide_id, image_url, posicion=None):
        """
        Agrega una imagen a una diapositiva
        
        Args:
            presentation_id: ID de la presentación
            slide_id: ID de la diapositiva
            image_url: URL de la imagen
        
        Returns:
            bool: True si se agregó correctamente
        """
        if not self.is_available():
            return False
        
        try:
            from uuid import uuid4
            image_id = f'Image_{uuid4().hex[:8]}'
            
            posicion = posicion or {}
            width = posicion.get('width', 380)
            height = posicion.get('height', 280)
            translate_x = posicion.get('translateX', 360)
            translate_y = posicion.get('translateY', 140)
            requests = [{
                'createImage': {
                    'objectId': image_id,
                    'url': image_url,
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {
                            'width': {'magnitude': width, 'unit': 'PT'},
                            'height': {'magnitude': height, 'unit': 'PT'}
                        },
                        'transform': {
                            'scaleX': 1,
                            'scaleY': 1,
                            'translateX': translate_x,
                            'translateY': translate_y,
                            'unit': 'PT'
                        }
                    }
                }
            }]
            
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"❌ Error al agregar imagen: {e}")
            return False
    
    def aplicar_tema_presentacion(self, presentation_id, color_primario='#4285F4'):
        """
        Aplica un tema de color a la presentación
        
        Args:
            presentation_id: ID de la presentación
            color_primario: Color principal en formato hex
        
        Returns:
            bool: True si se aplicó correctamente
        """
        if not self.is_available():
            return False
        
        try:
            # Obtener todas las diapositivas
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()
            
            requests = []
            
            # Aplicar color de fondo a cada diapositiva
            for slide in presentation.get('slides', []):
                slide_id = slide.get('objectId')
                
                requests.append({
                    'updatePageProperties': {
                        'objectId': slide_id,
                        'pageProperties': {
                            'pageBackgroundFill': {
                                'solidFill': {
                                    'color': {
                                        'rgbColor': self._hex_to_rgb(color_primario)
                                    },
                                    'alpha': 0.1
                                }
                            }
                        },
                        'fields': 'pageBackgroundFill'
                    }
                })
            
            if requests:
                self.slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ).execute()
            
            return True
            
        except HttpError as e:
            print(f"❌ Error al aplicar tema: {e}")
            return False
    
    def _hex_to_rgb(self, hex_color):
        """
        Convierte color hex a RGB para Google Slides
        
        Args:
            hex_color: Color en formato #RRGGBB
        
        Returns:
            dict: {'red': float, 'green': float, 'blue': float}
        """
        hex_color = hex_color.lstrip('#')
        return {
            'red': int(hex_color[0:2], 16) / 255.0,
            'green': int(hex_color[2:4], 16) / 255.0,
            'blue': int(hex_color[4:6], 16) / 255.0
        }
    
    def _eliminar_diapositiva(self, presentation_id, slide_id):
        """
        Elimina una diapositiva de la presentación
        
        Args:
            presentation_id: ID de la presentación
            slide_id: ID de la diapositiva a eliminar
        
        Returns:
            bool: True si se eliminó correctamente
        """
        if not self.is_available():
            return False
        
        try:
            requests = [{
                'deleteObject': {
                    'objectId': slide_id
                }
            }]
            
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"⚠️ No se pudo eliminar diapositiva: {e}")
            return False
    
    def buscar_imagen_web(self, query, tipo='relevant'):
        """
        Busca una imagen en la web usando la API de Pexels
        
        Args:
            query: Término de búsqueda
            tipo: 'relevant' o 'latest'
        
        Returns:
            str: URL directa de la imagen
        """
        if not self.pexels_api_key:
            print("⚠️ PEXELS_API_KEY no configurada. Usando placeholder.")
            return f"https://via.placeholder.com/800x600/4285F4/FFFFFF?text={query.replace(' ', '+')}"
        try:
            headers = {'Authorization': self.pexels_api_key}
            params = {
                'query': query,
                'per_page': 1,
                'orientation': 'landscape'
            }
            response = requests.get(
                'https://api.pexels.com/v1/search',
                headers=headers,
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                photos = data.get('photos', [])
                if photos:
                    foto = photos[0]
                    src = foto.get('src', {})
                    return src.get('large2x') or src.get('large') or src.get('original')
                print(f"⚠️ Pexels no retornó resultados para '{query}'")
            else:
                print(f"⚠️ Pexels respondió {response.status_code}: {response.text[:120]}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ No se pudo buscar imagen para '{query}' (error de red): {e}")
        except Exception as e:
            print(f"⚠️ Error inesperado con Pexels para '{query}': {e}")
        return f"https://via.placeholder.com/800x600/4285F4/FFFFFF?text={query.replace(' ', '+')}"

    # ═══════════════════════════════════════════════════════════════
    # YOUTUBE
    # ═══════════════════════════════════════════════════════════════

    def buscar_video_youtube(self, query, max_results=3):
        """
        Busca videos en YouTube
        
        Args:
            query: Término de búsqueda
            max_results: Número máximo de resultados (default 3)
            
        Returns:
            list: Lista de diccionarios con la información del video
        """
        if not self.is_available() or not self.youtube_service:
            print("⚠️ YouTube no está disponible o no tiene credenciales.")
            return []
            
        try:
            request = self.youtube_service.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=max_results,
                relevanceLanguage="es",
                regionCode="MX"
            )
            response = request.execute()
            
            videos = []
            for item in response.get("items", []):
                video_id = item["id"]["videoId"]
                videos.append({
                    "id": video_id,
                    "titulo": item["snippet"]["title"],
                    "canal": item["snippet"]["channelTitle"],
                    "descripcion": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
            
            return videos
            
        except HttpError as e:
            print(f"❌ Error al buscar en YouTube: {e}")
            return []
