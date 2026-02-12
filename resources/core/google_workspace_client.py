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
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/presentations',
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
                self.auth_type = 'oauth'
                print("✅ Usando autenticación OAuth (Gmail personal)")
            except Exception as e:
                print(f"⚠️ Error al cargar token OAuth: {e}")
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
            
            print("✅ Google Workspace conectado correctamente")
            
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
    
    def crear_evento(self, titulo, fecha_inicio, fecha_fin, descripcion="", ubicacion=""):
        """
        Crea un evento en el calendario
        
        Args:
            titulo: Título del evento
            fecha_inicio: datetime del inicio
            fecha_fin: datetime del fin
            descripcion: Descripción (opcional)
            ubicacion: Ubicación (opcional)
        
        Returns:
            dict: Información del evento creado
        """
        if not self.is_available():
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
            }
            
            event_result = self.calendar_service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            return {
                'id': event_result.get('id'),
                'url': event_result.get('htmlLink'),
                'titulo': titulo
            }
            
        except HttpError as e:
            print(f"❌ Error al crear evento: {e}")
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
        Crea una presentación con contenido mejorado
        
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
            # Crear presentación base
            presentation = {
                'title': titulo
            }
            
            slides = self.slides_service.presentations().create(
                body=presentation
            ).execute()
            
            presentation_id = slides.get('presentationId')
            
            # Agregar contenido si se proporcionó
            if diapositivas:
                print(f"📄 Agregando {len(diapositivas)} diapositivas con contenido...")
                
                # Eliminar la diapositiva inicial vacía
                primera_slide_id = slides['slides'][0]['objectId']
                
                for idx, diapositiva in enumerate(diapositivas, 1):
                    tipo_slide = diapositiva.get('tipo', 'contenido')
                    print(f"   📝 Diapositiva {idx}/{len(diapositivas)} ({tipo_slide}): {diapositiva.get('titulo', 'Sin título')[:40]}...")
                    
                    # Seleccionar layout según el tipo de slide
                    if tipo_slide == 'portada':
                        layout = 'TITLE'
                        slide_id = self.agregar_diapositiva(presentation_id, layout)
                        
                        if slide_id:
                            if tema_visual:
                                self._aplicar_estilo_diapositiva(presentation_id, slide_id, tema_visual)
                            
                            # Portada: Solo título y subtítulo centrados
                            if diapositiva.get('titulo'):
                                self.agregar_texto_diapositiva(
                                    presentation_id, 
                                    slide_id, 
                                    diapositiva['titulo'], 
                                    es_titulo=True,
                                    estilos_texto=tema_visual.get('estilos_titulo') if tema_visual else None
                                )
                            
                            if diapositiva.get('subtitulo'):
                                self.agregar_texto_diapositiva(
                                    presentation_id,
                                    slide_id,
                                    diapositiva['subtitulo'],
                                    es_titulo=False,
                                    estilos_texto=tema_visual.get('estilos_contenido') if tema_visual else None
                                )
                    
                    elif tipo_slide == 'conclusion':
                        # Conclusión: Layout con espacio para texto y posible imagen
                        layout = 'TITLE_AND_BODY'
                        slide_id = self.agregar_diapositiva(presentation_id, layout)
                        
                        if slide_id:
                            if tema_visual:
                                self._aplicar_estilo_diapositiva(presentation_id, slide_id, tema_visual)
                            
                            # Agregar título
                            if diapositiva.get('titulo'):
                                self.agregar_texto_diapositiva(
                                    presentation_id, 
                                    slide_id, 
                                    diapositiva['titulo'], 
                                    es_titulo=True,
                                    estilos_texto=tema_visual.get('estilos_titulo') if tema_visual else None
                                )
                            
                            # Agregar contenido de conclusión
                            if diapositiva.get('contenido'):
                                self.agregar_texto_diapositiva(
                                    presentation_id,
                                    slide_id,
                                    diapositiva['contenido'],
                                    es_titulo=False,
                                    estilos_texto=tema_visual.get('estilos_contenido') if tema_visual else None
                                )
                            
                            # Imagen pequeña en esquina inferior derecha (no invasiva)
                            if diapositiva.get('imagen_url'):
                                print(f"      🖼️  Agregando imagen decorativa...")
                                posicion_imagen = {
                                    'width': 200,
                                    'height': 150,
                                    'translateX': 500,
                                    'translateY': 320
                                }
                                self.agregar_imagen_diapositiva(
                                    presentation_id,
                                    slide_id,
                                    diapositiva['imagen_url'],
                                    posicion=posicion_imagen
                                )
                    
                    else:  # tipo_slide == 'contenido'
                        # Contenido: Detectar si tiene imagen para elegir layout
                        tiene_imagen = diapositiva.get('imagen_url') is not None
                        
                        if tiene_imagen:
                            # Layout con dos columnas: texto a la izquierda, imagen a la derecha
                            layout = 'TITLE_AND_TWO_COLUMNS'
                        else:
                            # Layout simple: título y cuerpo (más espacio para texto)
                            layout = 'TITLE_AND_BODY'
                        
                        slide_id = self.agregar_diapositiva(presentation_id, layout)
                        
                        if slide_id:
                            if tema_visual:
                                self._aplicar_estilo_diapositiva(presentation_id, slide_id, tema_visual)
                            
                            # Agregar título
                            if diapositiva.get('titulo'):
                                self.agregar_texto_diapositiva(
                                    presentation_id, 
                                    slide_id, 
                                    diapositiva['titulo'], 
                                    es_titulo=True,
                                    estilos_texto=tema_visual.get('estilos_titulo') if tema_visual else None
                                )
                            
                            # Agregar contenido
                            if diapositiva.get('contenido'):
                                self.agregar_texto_diapositiva(
                                    presentation_id,
                                    slide_id,
                                    diapositiva['contenido'],
                                    es_titulo=False,
                                    estilos_texto=tema_visual.get('estilos_contenido') if tema_visual else None
                                )
                            
                            # Agregar imagen en posición que no choque con texto
                            if tiene_imagen:
                                print(f"      🖼️  Agregando imagen...")
                                # Imagen en el lado derecho, no sobre el texto
                                posicion_imagen = {
                                    'width': 280,
                                    'height': 210,
                                    'translateX': 420,
                                    'translateY': 150
                                }
                                self.agregar_imagen_diapositiva(
                                    presentation_id,
                                    slide_id,
                                    diapositiva['imagen_url'],
                                    posicion=posicion_imagen
                                    )
                
                # Eliminar primera diapositiva vacía
                self._eliminar_diapositiva(presentation_id, primera_slide_id)
                
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
                # Intentar determinar si es problema de API o de permisos IAM
                error_msg = str(e)
                
                if 'PERMISSION_DENIED' in error_msg or 'does not have permission' in error_msg:
                    print(f"❌ Error 403: Service Account sin permisos IAM")
                    print("")
                    print("📋 SOLUCIÓN - Da permisos al Service Account:")
                    print("")
                    print("1. Ve a: https://console.cloud.google.com/iam-admin/iam")
                    print("2. Busca: trace-cf294@appspot.gserviceaccount.com")
                    print("3. Haz click en 'Edit' (ícono de lápiz)")
                    print("4. Agrega rol: 'Editor' o 'Google Workspace Admin'")
                    print("5. Haz click en 'Save'")
                    print("")
                    print(f"   Detalle técnico: {error_reason}")
                    return {
                        'error': 'PERMISSION_DENIED',
                        'message': 'Service Account sin permisos. Necesitas darle permisos IAM en Google Cloud Console.',
                        'instrucciones': 'Ve a IAM & Admin, busca trace-cf294@appspot.gserviceaccount.com y dale rol de Editor',
                        'link': 'https://console.cloud.google.com/iam-admin/iam?project=trace-cf294'
                    }
                else:
                    print(f"❌ Error 403: Google Slides API no habilitada")
                    print("")
                    print("📋 SOLUCIÓN - Habilita Google Slides API:")
                    print("")
                    print("1. Ve a: https://console.cloud.google.com/apis/library/slides.googleapis.com")
                    print("2. Selecciona tu proyecto: trace-cf294")
                    print("3. Haz click en 'ENABLE' (Habilitar)")
                    print("4. Espera 1-2 minutos y vuelve a intentar")
                    print("")
                    return {
                        'error': 'API_NOT_ENABLED',
                        'message': 'Google Slides API no habilitada.',
                        'instrucciones': 'Accede al link, selecciona tu proyecto y haz click en ENABLE',
                        'link': 'https://console.cloud.google.com/apis/library/slides.googleapis.com?project=trace-cf294'
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

