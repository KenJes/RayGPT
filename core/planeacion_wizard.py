"""
core/planeacion_wizard.py

Wizard conversacional para generar Planeaciones Didácticas directamente
en el chat — sin abrir navegador.

Compatible con:
  - RAIGPT GUI (tkinter): botón 🎓 activa el wizard en el chat
  - WhatsApp server: comando /planeacion activa el wizard por usuario

Uso:
    from core.planeacion_wizard import PlaneacionWizard

    def ai_fn(prompt: str) -> str:
        return my_llm_call(prompt, max_tokens=16000)

    wizard = PlaneacionWizard(ai_fn)
    first_msg = wizard.start()           # muestra bienvenida + 1ª pregunta
    resp = wizard.step(user_input)       # avanza el formulario
    if wizard.is_done:
        # wizard terminó, volver al chat normal
        pass

    wizard.cancel()                      # aborta en cualquier momento
"""

import json
import re
from datetime import date, timedelta, datetime
from typing import Callable, Dict, List, Any, Optional

# ── Constantes de estado ───────────────────────────────────────────────────────
IDLE               = "idle"
ASKING_MATERIA     = "asking_materia"
ASKING_DOCENTE     = "asking_docente"
ASKING_SEMESTRE    = "asking_semestre"
ASKING_INICIO      = "asking_inicio"
ASKING_FIN         = "asking_fin"
ASKING_DIAS        = "asking_dias"
ASKING_HORAS       = "asking_horas"
ASKING_PARCIAL1    = "asking_parcial1"
ASKING_PARCIAL2    = "asking_parcial2"
ASKING_SUSPENSIONES       = "asking_suspensiones"
ASKING_TEMARIO_OPCION     = "asking_temario_opcion"
ASKING_TEMARIO_TEXTO      = "asking_temario_texto"
ASKING_UNIDADES_COUNT     = "asking_unidades_count"
ASKING_UNIDAD_NOMBRE      = "asking_unidad_nombre"
ASKING_UNIDAD_OBJETIVO    = "asking_unidad_objetivo"
ASKING_UNIDAD_TEMAS       = "asking_unidad_temas"
CONFIRMING = "confirming"
GENERATING = "generating"
DONE       = "done"

_CANCEL_CMDS = {"/cancelar", "/salir", "/cancel", "/exit", "/stop", "cancelar", "salir"}

# ── Mapa días de semana ────────────────────────────────────────────────────────
_DIA_MAP: Dict[str, int] = {
    "lunes": 0, "lun": 0, "lu": 0,
    "martes": 1, "mar": 1, "ma": 1,
    "miercoles": 2, "miércoles": 2, "mie": 2, "mié": 2, "mi": 2,
    "jueves": 3, "jue": 3, "ju": 3,
    "viernes": 4, "vie": 4, "vi": 4,
    "sabado": 5, "sábado": 5, "sab": 5,
    "domingo": 6, "dom": 6,
}
_DIA_NOMBRE = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# ── Variedad Bloom + tipos de actividad ───────────────────────────────────────
_BLOOM = ["Recordar", "Comprender", "Aplicar", "Analizar", "Evaluar", "Crear"]
_TIPOS = [
    "Clase expositiva",
    "Taller práctico",
    "Trabajo colaborativo",
    "Estudio de caso",
    "Debate y discusión",
    "Proyecto",
    "Laboratorio",
    "Aprendizaje basado en problemas",
    "Flipped classroom",
    "Gamificación",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Clase principal
# ═══════════════════════════════════════════════════════════════════════════════

class PlaneacionWizard:
    """
    Wizard conversacional para recopilar datos y generar una planeación
    didáctica semestral.

    Parámetros
    ----------
    ai_fn : Callable[[str], str]
        Función que recibe un prompt y devuelve la respuesta del LLM.
        Debe soportar prompts largos (max_tokens ≥ 8000) ya que la
        generación del plan puede ser extensa (30+ sesiones).
    """

    def __init__(self, ai_fn: Callable[[str], str]):
        self.ai_fn = ai_fn
        self._reset()

    # ── Estado público ─────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.estado not in (IDLE, DONE)

    @property
    def is_done(self) -> bool:
        return self.estado == DONE

    # ── API pública ────────────────────────────────────────────────────────────

    def start(self) -> str:
        """Inicia el wizard y devuelve el primer mensaje."""
        self._reset()
        self.estado = ASKING_MATERIA
        return (
            "🎓 *Generador de Planeación Didáctica*\n\n"
            "Te voy a ayudar a crear tu planeación semestral "
            "paso a paso — solo responde mis preguntas.\n"
            "Escribe */cancelar* en cualquier momento para salir.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📚 *Pregunta 1 de 10*\n"
            "¿Cuál es el nombre de la materia?"
        )

    def step(self, respuesta: str) -> str:
        """Procesa la respuesta del usuario y devuelve el siguiente mensaje."""
        r = respuesta.strip()

        if r.lower() in _CANCEL_CMDS:
            self._reset()
            return (
                "❌ Planeación cancelada.\n"
                "Puedes iniciar una nueva usando el botón 🎓 o el comando /planeacion."
            )

        _handlers = {
            ASKING_MATERIA:          self._handle_materia,
            ASKING_DOCENTE:          self._handle_docente,
            ASKING_SEMESTRE:         self._handle_semestre,
            ASKING_INICIO:           self._handle_inicio,
            ASKING_FIN:              self._handle_fin,
            ASKING_DIAS:             self._handle_dias,
            ASKING_HORAS:            self._handle_horas,
            ASKING_PARCIAL1:         self._handle_parcial1,
            ASKING_PARCIAL2:         self._handle_parcial2,
            ASKING_SUSPENSIONES:     self._handle_suspensiones,
            ASKING_TEMARIO_OPCION:   self._handle_temario_opcion,
            ASKING_TEMARIO_TEXTO:    self._handle_temario_texto,
            ASKING_UNIDADES_COUNT:   self._handle_unidades_count,
            ASKING_UNIDAD_NOMBRE:    self._handle_unidad_nombre,
            ASKING_UNIDAD_OBJETIVO:  self._handle_unidad_objetivo,
            ASKING_UNIDAD_TEMAS:     self._handle_unidad_temas,
            CONFIRMING:              self._handle_confirming,
        }
        handler = _handlers.get(self.estado)
        if handler:
            return handler(r)
        return "⚠️ Estado inesperado. Escribe /cancelar para reiniciar."

    def cancel(self) -> str:
        self._reset()
        return "❌ Planeación cancelada."

    # ── Reset interno ──────────────────────────────────────────────────────────

    def _reset(self):
        self.estado = IDLE
        self.datos: Dict[str, Any] = {}
        self._unidades_temp: List[Dict] = []
        self._n_unidades = 0
        self._current_unidad_idx = 0

    # ══════════════════════════════════════════════════════════════════════════
    # Handlers por estado
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_materia(self, r: str) -> str:
        if len(r) < 3:
            return "⚠️ El nombre es muy corto. ¿Cuál es el nombre de la materia?"
        self.datos["materia"] = r
        self.estado = ASKING_DOCENTE
        return (
            f"✅ Materia: *{r}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 *Pregunta 2 de 10*\n"
            "¿Cuál es tu nombre completo (docente)?"
        )

    def _handle_docente(self, r: str) -> str:
        if len(r) < 2:
            return "⚠️ Por favor escribe tu nombre. ¿Cuál es tu nombre?"
        self.datos["docente"] = r
        self.estado = ASKING_SEMESTRE
        return (
            f"✅ Docente: *{r}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *Pregunta 3 de 10*\n"
            "¿Cuál es el semestre?\n"
            "(ej: Agosto-Enero 2026-2027)"
        )

    def _handle_semestre(self, r: str) -> str:
        if len(r) < 4:
            return "⚠️ Escribe el semestre. Ej: Agosto-Enero 2026-2027"
        self.datos["semestre"] = r
        self.estado = ASKING_INICIO
        return (
            f"✅ Semestre: *{r}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *Pregunta 4 de 10*\n"
            "¿Cuál es la fecha de *inicio* de clases?\n"
            "Formato: dd/mm/yyyy  (ej: 04/08/2026)"
        )

    def _handle_inicio(self, r: str) -> str:
        fecha = _parse_fecha(r)
        if not fecha:
            return "⚠️ No reconocí la fecha. Usa el formato dd/mm/yyyy (ej: 04/08/2026):"
        self.datos["inicio"] = fecha
        self.estado = ASKING_FIN
        return (
            f"✅ Inicio: *{fecha.strftime('%d/%m/%Y')}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *Pregunta 5 de 10*\n"
            "¿Cuál es la fecha de *fin* de clases?\n"
            "Formato: dd/mm/yyyy  (ej: 20/01/2027)"
        )

    def _handle_fin(self, r: str) -> str:
        fecha = _parse_fecha(r)
        inicio = self.datos.get("inicio")
        if not fecha:
            return "⚠️ No reconocí la fecha. Usa el formato dd/mm/yyyy:"
        if inicio and fecha <= inicio:
            return (
                f"⚠️ La fecha de fin debe ser posterior al inicio "
                f"({inicio.strftime('%d/%m/%Y')}). Intenta de nuevo:"
            )
        self.datos["fin"] = fecha
        self.estado = ASKING_DIAS
        return (
            f"✅ Fin: *{fecha.strftime('%d/%m/%Y')}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *Pregunta 6 de 10*\n"
            "¿Qué días tienes clase? Escríbelos separados por comas.\n"
            "Ej: *Lunes, Miércoles, Viernes*   o   *Martes, Jueves*"
        )

    def _handle_dias(self, r: str) -> str:
        dias = _parse_dias(r)
        if not dias:
            return (
                "⚠️ No reconocí los días. Escríbelos separados por comas.\n"
                "Ej: Lunes, Miércoles, Viernes"
            )
        self.datos["dias_semana"] = dias
        nombres = ", ".join(_DIA_NOMBRE[d] for d in dias)
        self.estado = ASKING_HORAS
        return (
            f"✅ Días de clase: *{nombres}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏱️ *Pregunta 7 de 10*\n"
            "¿Cuántas horas dura cada sesión de clase?\n"
            "(ej: 2  o  1.5)"
        )

    def _handle_horas(self, r: str) -> str:
        try:
            h = float(r.replace(",", "."))
            if h <= 0 or h > 8:
                raise ValueError
        except ValueError:
            return "⚠️ Escribe un número válido de horas (ej: 2  o  1.5):"
        self.datos["horas"] = h
        self.estado = ASKING_PARCIAL1
        return (
            f"✅ Horas por sesión: *{h}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📝 *Pregunta 8 de 10*\n"
            "¿Cuándo es aproximadamente el *primer examen parcial*?\n"
            "Formato: dd/mm/yyyy  (ej: 09/10/2026)"
        )

    def _handle_parcial1(self, r: str) -> str:
        fecha = _parse_fecha(r)
        inicio = self.datos.get("inicio")
        if not fecha:
            return "⚠️ Formato no válido. Usa dd/mm/yyyy (ej: 09/10/2026):"
        if inicio and fecha < inicio:
            return f"⚠️ El parcial 1 debe ser después del inicio ({inicio.strftime('%d/%m/%Y')}):"
        self.datos["parcial1"] = fecha
        self.estado = ASKING_PARCIAL2
        return (
            f"✅ Primer parcial: *{fecha.strftime('%d/%m/%Y')}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📝 *Pregunta 9 de 10*\n"
            "¿Cuándo es aproximadamente el *segundo examen parcial*?\n"
            "Formato: dd/mm/yyyy  (ej: 11/12/2026)"
        )

    def _handle_parcial2(self, r: str) -> str:
        fecha = _parse_fecha(r)
        p1 = self.datos.get("parcial1")
        if not fecha:
            return "⚠️ Formato no válido. Usa dd/mm/yyyy:"
        if p1 and fecha <= p1:
            return f"⚠️ El parcial 2 debe ser después del parcial 1 ({p1.strftime('%d/%m/%Y')}):"
        self.datos["parcial2"] = fecha
        self.estado = ASKING_SUSPENSIONES
        return (
            f"✅ Segundo parcial: *{fecha.strftime('%d/%m/%Y')}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚫 *Pregunta 10 de 10*\n"
            "¿Hay días sin clase (suspensiones o festivos)?\n\n"
            "• Si hay, escribe las fechas separadas por comas (dd/mm/yyyy)\n"
            "  Ej: 02/11/2026, 18/11/2026\n\n"
            "• Si no hay, escribe *ninguna*"
        )

    def _handle_suspensiones(self, r: str) -> str:
        if r.lower().strip() in ("ninguna", "no", "n/a", "no hay", "0", "sin suspensiones"):
            self.datos["suspensiones"] = []
        else:
            partes = re.split(r"[,;\n]+", r)
            fechas = []
            for p in partes:
                f = _parse_fecha(p.strip())
                if f:
                    fechas.append(f)
            self.datos["suspensiones"] = fechas

        n_susp = len(self.datos["suspensiones"])
        susp_txt = f"{n_susp} día(s) sin clase" if n_susp else "Ninguna"
        self.estado = ASKING_TEMARIO_OPCION
        return (
            f"✅ Suspensiones: *{susp_txt}*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📖 *Temario del curso*\n\n"
            "¿Cómo quieres ingresar el contenido del curso?\n\n"
            "  *pegar*  — Pegas el texto de tu programa de estudios\n"
            "            (la IA extrae las unidades automáticamente)\n\n"
            "  *manual* — Ingresas las unidades paso a paso\n\n"
            "Responde: *pegar* o *manual*"
        )

    def _handle_temario_opcion(self, r: str) -> str:
        rl = r.lower()
        if "peg" in rl or "paste" in rl or "text" in rl or "cop" in rl:
            self.estado = ASKING_TEMARIO_TEXTO
            return (
                "📋 De acuerdo. Pega a continuación el texto completo de tu "
                "programa de estudios (puedes copiar directamente del PDF):"
            )
        if "man" in rl or "unit" in rl or "paso" in rl:
            self.estado = ASKING_UNIDADES_COUNT
            return (
                "📝 Ingreso manual.\n\n"
                "¿Cuántas unidades temáticas tiene el curso?\n"
                "(ej: 4)"
            )
        return "⚠️ Por favor responde *pegar* o *manual*:"

    def _handle_temario_texto(self, r: str) -> str:
        if r.strip().lower() in ("manual", "man"):
            self.estado = ASKING_UNIDADES_COUNT
            return "¿Cuántas unidades temáticas tiene el curso? (ej: 4)"

        if len(r) < 100:
            return (
                "⚠️ El texto parece muy corto. Asegúrate de pegar el programa "
                "de estudios completo.\n"
                "O escribe *manual* para ingresar las unidades paso a paso:"
            )

        # Extraer unidades con IA
        try:
            unidades = _extraer_unidades_ia(r, self.ai_fn)
            if unidades and len(unidades) > 0:
                self.datos["unidades"] = unidades
                self.estado = CONFIRMING
                n = len(unidades)
                lista = "\n".join(
                    f"  • U{u['numero']}: {u['nombre']} ({len(u.get('temas', []))} temas)"
                    for u in unidades
                )
                return (
                    f"✅ Extraje *{n} unidades* del programa:\n{lista}\n\n"
                    + self._resumen_y_pregunta()
                )
        except Exception:
            pass

        # Fallback a manual
        self.estado = ASKING_UNIDADES_COUNT
        return (
            "⚠️ No pude extraer las unidades automáticamente.\n"
            "Continuamos en modo manual.\n\n"
            "¿Cuántas unidades temáticas tiene el curso? (ej: 4)"
        )

    def _handle_unidades_count(self, r: str) -> str:
        try:
            n = int(r.strip())
            if n < 1 or n > 12:
                raise ValueError
        except ValueError:
            return "⚠️ Escribe un número entre 1 y 12:"
        self._n_unidades = n
        self._current_unidad_idx = 1
        self._unidades_temp = []
        self.estado = ASKING_UNIDAD_NOMBRE
        return (
            f"✅ *{n} unidades*. Empecemos.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📚 *Unidad 1 de {n}*\n"
            "¿Cuál es el *nombre* de la Unidad 1?\n"
            "(ej: Fundamentos de Programación Orientada a Objetos)"
        )

    def _handle_unidad_nombre(self, r: str) -> str:
        if len(r) < 3:
            return (
                f"⚠️ El nombre es muy corto. "
                f"¿Nombre de la Unidad {self._current_unidad_idx}?"
            )
        self._unidades_temp.append({
            "numero": self._current_unidad_idx,
            "nombre": r,
            "objetivo": "",
            "temas": [],
        })
        self.estado = ASKING_UNIDAD_OBJETIVO
        return (
            f"✅ Nombre: *{r}*\n\n"
            f"¿Cuál es el *objetivo* de la Unidad {self._current_unidad_idx}?\n"
            "(ej: El estudiante aplicará los principios de POO para resolver problemas...)"
        )

    def _handle_unidad_objetivo(self, r: str) -> str:
        self._unidades_temp[-1]["objetivo"] = r
        self.estado = ASKING_UNIDAD_TEMAS
        idx = self._current_unidad_idx
        return (
            "✅ Objetivo registrado.\n\n"
            f"¿Cuáles son los *temas* de la Unidad {idx}?\n"
            "Escríbelos separados por comas o líneas:\n"
            "(ej: Clases y objetos, Herencia, Polimorfismo, Encapsulamiento)"
        )

    def _handle_unidad_temas(self, r: str) -> str:
        temas = [t.strip() for t in re.split(r"[,\n;]+", r) if t.strip()]
        if not temas:
            return "⚠️ Escribe al menos un tema:"
        self._unidades_temp[-1]["temas"] = temas
        idx = self._current_unidad_idx
        n = self._n_unidades

        if idx < n:
            self._current_unidad_idx += 1
            self.estado = ASKING_UNIDAD_NOMBRE
            return (
                f"✅ Unidad {idx} lista ({len(temas)} temas).\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 *Unidad {idx + 1} de {n}*\n"
                f"¿Cuál es el *nombre* de la Unidad {idx + 1}?"
            )

        # Todas las unidades capturadas
        self.datos["unidades"] = self._unidades_temp
        self.estado = CONFIRMING
        return self._resumen_y_pregunta()

    def _handle_confirming(self, r: str) -> str:
        rl = r.lower().strip()
        if rl in ("sí", "si", "yes", "s", "ok", "generar", "dale", "adelante",
                  "confirmar", "1", "continuar"):
            self.estado = GENERATING
            return self._generar_plan()
        if rl in ("no", "cancelar", "n"):
            self._reset()
            return (
                "❌ Planeación cancelada.\n"
                "Puedes iniciar de nuevo usando el botón 🎓 o /planeacion."
            )
        return (
            "Por favor responde *sí* para generar o *no* para cancelar.\n\n"
            + self._resumen_y_pregunta()
        )

    # ── Resumen antes de generar ───────────────────────────────────────────────

    def _resumen_y_pregunta(self) -> str:
        d = self.datos
        inicio: Optional[date] = d.get("inicio")
        fin: Optional[date] = d.get("fin")
        dias: List[int] = d.get("dias_semana", [])
        suspensiones: List[date] = d.get("suspensiones", [])
        unidades: List[Dict] = d.get("unidades", [])

        fechas = (
            _calcular_sesiones(inicio, fin, dias, suspensiones)
            if inicio and fin and dias else []
        )
        n_sesiones = len(fechas)

        nombres_dias = ", ".join(_DIA_NOMBRE[d_] for d_ in dias) if dias else "—"
        n_susp = len(suspensiones)

        u_txt = (
            "\n".join(
                f"  • U{u['numero']}: {u['nombre']} "
                f"({len(u.get('temas', []))} temas)"
                for u in unidades
            )
            if unidades else "  (sin unidades)"
        )

        return (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 *RESUMEN*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📚 Materia:     {d.get('materia', '—')}\n"
            f"👤 Docente:     {d.get('docente', '—')}\n"
            f"📅 Semestre:    {d.get('semestre', '—')}\n"
            f"🗓️  Inicio:      {inicio.strftime('%d/%m/%Y') if inicio else '—'}\n"
            f"🗓️  Fin:         {fin.strftime('%d/%m/%Y') if fin else '—'}\n"
            f"📆 Días:        {nombres_dias}\n"
            f"⏱️  Hrs/sesión:  {d.get('horas', '—')}\n"
            f"📝 Parcial 1:   {d['parcial1'].strftime('%d/%m/%Y') if d.get('parcial1') else '—'}\n"
            f"📝 Parcial 2:   {d['parcial2'].strftime('%d/%m/%Y') if d.get('parcial2') else '—'}\n"
            f"🚫 Suspens.:    {n_susp} día(s)\n"
            f"📖 Unidades:\n{u_txt}\n"
            f"📊 Sesiones estimadas: *{n_sesiones}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "¿Generamos la planeación? Responde *sí* o *no*."
        )

    # ── Generación del plan (llamada al LLM) ──────────────────────────────────

    def _generar_plan(self) -> str:
        d = self.datos
        try:
            inicio: date       = d["inicio"]
            fin: date          = d["fin"]
            dias: List[int]    = d["dias_semana"]
            suspensiones       = d.get("suspensiones", [])
            unidades           = d.get("unidades", [])
            parcial1           = d.get("parcial1")
            parcial2           = d.get("parcial2")

            fechas_sesiones = _calcular_sesiones(inicio, fin, dias, suspensiones)
            n_sesiones = len(fechas_sesiones)

            if n_sesiones < 2:
                self.estado = DONE
                return (
                    "⚠️ El período de clases tiene muy pocas sesiones "
                    f"({n_sesiones}). Verifica las fechas.\n"
                    "Usa el botón 🎓 o /planeacion para reiniciar."
                )

            distribucion = _distribuir_sesiones(fechas_sesiones, parcial1, parcial2)
            plan_variedad = _generar_plan_variedad(n_sesiones)
            prompt = _construir_prompt(
                d["materia"], unidades, n_sesiones, distribucion, plan_variedad
            )

            respuesta_ia = self.ai_fn(prompt)
            sesiones_json = _extraer_json_array(respuesta_ia)

            if not sesiones_json or not isinstance(sesiones_json, list):
                self.estado = DONE
                return (
                    "❌ La IA no devolvió un JSON válido para la planeación.\n"
                    "Verifica que Ollama esté corriendo y vuelve a intentarlo."
                )

            texto = _formatear_plan_texto(sesiones_json, fechas_sesiones, d)
            self.estado = DONE
            return texto

        except Exception as e:
            self.estado = DONE
            return (
                f"❌ Error al generar la planeación: {e}\n"
                "Usa el botón 🎓 o /planeacion para reiniciar."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers de calendario
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_fecha(s: str) -> Optional[date]:
    """Parsea una cadena de fecha en múltiples formatos. Devuelve date o None."""
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_dias(s: str) -> List[int]:
    """'Lunes, Miércoles, Viernes' → [0, 2, 4] (sorted, no duplicates)."""
    def _norm(t: str) -> str:
        return (
            t.lower()
            .replace("á", "a").replace("é", "e")
            .replace("í", "i").replace("ó", "o")
            .replace("ú", "u").replace("ü", "u")
            .strip()
        )

    partes = re.split(r"[,\s/]+", s)
    dias: List[int] = []
    for p in partes:
        n = _norm(p)
        if n in _DIA_MAP and _DIA_MAP[n] not in dias:
            dias.append(_DIA_MAP[n])
    return sorted(dias)


def _calcular_sesiones(
    inicio: date,
    fin: date,
    dias_semana: List[int],
    suspensiones: List[date],
) -> List[date]:
    """Genera lista de fechas de sesiones evitando suspensiones y fines de semana."""
    susp = set(suspensiones)
    fechas: List[date] = []
    d = inicio
    while d <= fin:
        if d.weekday() in dias_semana and d not in susp:
            fechas.append(d)
        d += timedelta(days=1)
    return fechas


def _distribuir_sesiones(
    fechas: List[date],
    parcial1: Optional[date],
    parcial2: Optional[date],
) -> Dict[str, int]:
    """Calcula cuántas sesiones hay antes y después del primer parcial."""
    if not parcial1:
        mid = len(fechas) // 2
        return {"primerParcial": max(mid, 1), "segundoParcial": max(len(fechas) - mid, 1)}
    primer = sum(1 for f in fechas if f <= parcial1)
    segundo = len(fechas) - primer
    return {
        "primerParcial": max(primer, 1),
        "segundoParcial": max(segundo, 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Plan de variedad (Bloom + tipos de actividad)
# ═══════════════════════════════════════════════════════════════════════════════

def _generar_plan_variedad(n_sesiones: int) -> List[Dict]:
    """Genera un plan de variedad de actividades y niveles Bloom para N sesiones."""
    plan: List[Dict] = []
    tipo_shift = 0
    for i in range(n_sesiones):
        progreso = i / max(n_sesiones - 1, 1)
        idx_bloom = min(int(progreso * len(_BLOOM)), len(_BLOOM) - 1)

        tipo_idx = (i + tipo_shift) % len(_TIPOS)
        if plan and _TIPOS[tipo_idx] == plan[-1]["tipo_actividad"]:
            tipo_shift += 1
            tipo_idx = (i + tipo_shift) % len(_TIPOS)

        plan.append({
            "sesion": i + 1,
            "tipo_actividad": _TIPOS[tipo_idx],
            "nivel_bloom": _BLOOM[idx_bloom],
        })
    return plan


# ═══════════════════════════════════════════════════════════════════════════════
# Extracción de unidades desde texto pegado
# ═══════════════════════════════════════════════════════════════════════════════

def _extraer_unidades_ia(texto: str, ai_fn: Callable[[str], str]) -> List[Dict]:
    """Llama al LLM para extraer unidades temáticas de un texto de programa de estudios."""
    texto = texto[:10000]
    prompt = f"""Analiza este programa de estudios universitario y extrae las UNIDADES TEMÁTICAS.

Responde ÚNICAMENTE con un objeto JSON válido (sin markdown, sin texto adicional).

TEXTO DEL PROGRAMA:
{texto}

INSTRUCCIONES:
1. Identifica las UNIDADES TEMÁTICAS (generalmente 2-6 unidades).
2. Para CADA unidad extrae: número, nombre completo, objetivo específico, lista de temas.
3. Si no hay unidades claras, agrupa los temas en bloques como unidades.

FORMATO JSON EXACTO (sin texto antes ni después):
{{
  "unidades": [
    {{
      "numero": 1,
      "nombre": "Nombre completo de la unidad",
      "objetivo": "Objetivo específico y medible",
      "temas": ["Tema 1", "Tema 2", "Tema 3"]
    }}
  ]
}}"""

    respuesta = (ai_fn(prompt) or "").strip()

    # Limpiar markdown
    respuesta = re.sub(r"```(?:json)?\s*", "", respuesta)
    respuesta = re.sub(r"```\s*", "", respuesta)

    ini = respuesta.find("{")
    fin = respuesta.rfind("}")
    if ini == -1 or fin <= ini:
        raise ValueError("No se encontró JSON en la respuesta")

    datos = json.loads(respuesta[ini:fin + 1])
    unidades = datos.get("unidades", [])
    if not unidades:
        raise ValueError("No se encontraron unidades en el JSON")
    return unidades


# ═══════════════════════════════════════════════════════════════════════════════
# Construcción del prompt para generar la planeación
# ═══════════════════════════════════════════════════════════════════════════════

def _construir_prompt(
    materia: str,
    unidades: List[Dict],
    n_sesiones: int,
    distribucion: Dict,
    plan_variedad: List[Dict],
) -> str:
    """Construye el prompt completo para que el LLM genere la planeación."""
    corte = max(1, len(unidades) // 2)
    unidades_p1 = unidades[:corte]
    unidades_p2 = unidades[corte:]

    plan_txt = "\n".join(
        f"Sesión {p['sesion']}: tipo_actividad=\"{p['tipo_actividad']}\", "
        f"nivel_bloom=\"{p['nivel_bloom']}\""
        for p in plan_variedad
    )

    unidades_txt = ""
    for u in unidades:
        parcial = "PRIMER" if u["numero"] <= corte else "SEGUNDO"
        temas = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(u.get("temas", [])))
        unidades_txt += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"UNIDAD {u['numero']}: {u['nombre']} [{parcial} PARCIAL]\n"
            f"Objetivo: {u.get('objetivo', '')}\n"
            f"Temas ({len(u.get('temas', []))}):\n{temas}\n"
        )

    ses_rep1 = distribucion["primerParcial"]
    ses_rep2 = n_sesiones

    return f"""Eres un experto pedagogo universitario. Genera una planeación didáctica semestral DETALLADA y VARIADA para la materia "{materia}" de la Universidad Autónoma del Estado de México (UAEMex).

CONTEXTO:
- Nivel: Educación Superior (Pregrado)
- Modalidad: Presencial
- Total de sesiones: {n_sesiones}
- Unidades: {len(unidades)}

DISTRIBUCIÓN POR PARCIAL:
- PRIMER PARCIAL: {distribucion['primerParcial']} sesiones
  Unidades: {', '.join(str(u['numero']) for u in unidades_p1) or '(ninguna)'}
- SEGUNDO PARCIAL: {distribucion['segundoParcial']} sesiones
  Unidades: {', '.join(str(u['numero']) for u in unidades_p2) or '(ninguna)'}

PLAN DE VARIEDAD (OBLIGATORIO — respétalo EXACTAMENTE):
{plan_txt}

UNIDADES DEL CURSO:
{unidades_txt}

REGLAS OBLIGATORIAS:
1. NO repitas tipo_actividad en sesiones consecutivas.
2. Evita frases genéricas: "el docente explicará", "revisar el tema", "comprender los conceptos".
3. Cada sesión debe tener: 2+ preguntas socráticas, actividades Inicio/Desarrollo/Cierre con tiempos.
4. La competencia debe ser medible: verbo Bloom + objeto + criterio específico.
5. Sesión 1: Introducción y encuadre (unidad=0).
6. Sesión {ses_rep1}: Repaso integrador primer parcial (unidad=0).
7. Sesión {ses_rep2}: Repaso integrador segundo parcial (unidad=0).

FORMATO DE RESPUESTA (JSON ESTRICTO — SOLO el array, sin texto antes ni después):
[
  {{
    "sesion": 1,
    "tema": "título específico y concreto",
    "unidad": 0,
    "tipo_actividad": "debe coincidir EXACTAMENTE con el plan",
    "nivel_bloom": "debe coincidir EXACTAMENTE con el plan",
    "competencia": "Los estudiantes [verbo Bloom] ... (medible y específica)",
    "preguntas_socraticas": ["¿pregunta 1?", "¿pregunta 2?"],
    "actividades": [
      {{"momento": "Inicio",      "duracion_min": 15, "descripcion": "...", "evidencia": "..."}},
      {{"momento": "Desarrollo",  "duracion_min": 60, "descripcion": "...", "evidencia": "..."}},
      {{"momento": "Cierre",      "duracion_min": 15, "descripcion": "...", "evidencia": "..."}}
    ],
    "evaluacion_formativa": "breve descripción de cómo retroalimentas"
  }}
]

GENERA EXACTAMENTE {n_sesiones} OBJETOS EN EL ARRAY:"""


# ═══════════════════════════════════════════════════════════════════════════════
# Extracción de JSON array de la respuesta IA
# ═══════════════════════════════════════════════════════════════════════════════

def _extraer_json_array(texto: str) -> Optional[List]:
    """Extrae y parsea un array JSON de la respuesta del LLM."""
    if not texto:
        return None

    texto = re.sub(r"```(?:json)?\s*", "", texto)
    texto = re.sub(r"```\s*", "", texto)
    texto = texto.strip()

    ini = texto.find("[")
    fin = texto.rfind("]")
    if ini == -1 or fin <= ini:
        return None

    fragmento = texto[ini:fin + 1]

    try:
        parsed = json.loads(fragmento)
        return parsed if isinstance(parsed, list) else None
    except json.JSONDecodeError:
        try:
            fragmento = re.sub(r",(\s*[}\]])", r"\1", fragmento)   # trailing commas
            fragmento = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", fragmento)  # ctrl chars
            parsed = json.loads(fragmento)
            return parsed if isinstance(parsed, list) else None
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# Formateo del plan como texto para el chat
# ═══════════════════════════════════════════════════════════════════════════════

def _formatear_plan_texto(
    sesiones: List[Dict],
    fechas: List[date],
    datos: Dict,
) -> str:
    """Convierte el JSON del plan en texto formateado para el chat."""
    materia  = datos.get("materia",  "—")
    docente  = datos.get("docente",  "—")
    semestre = datos.get("semestre", "—")
    n = len(sesiones)

    lineas = [
        "┌──────────────────────────────────────────────┐",
        "│  📋  PLANEACIÓN DIDÁCTICA — UAEMex           │",
        f"│  {materia[:44]:<44}  │",
        f"│  Docente:  {docente[:35]:<35}  │",
        f"│  Semestre: {semestre[:34]:<34}  │",
        f"│  Total de sesiones: {n:<26}│",
        "└──────────────────────────────────────────────┘",
        "",
    ]

    for i, ses in enumerate(sesiones):
        fecha_str = fechas[i].strftime("%d/%m/%Y") if i < len(fechas) else "—"
        num       = ses.get("sesion", i + 1)
        tema      = ses.get("tema", "—")
        tipo      = ses.get("tipo_actividad", "—")
        bloom     = ses.get("nivel_bloom", "—")
        comp      = ses.get("competencia", "—")
        eval_f    = ses.get("evaluacion_formativa", "")

        preguntas = ses.get("preguntas_socraticas", [])
        pregs_txt = "\n".join(
            f"   {j+1}. {p}" for j, p in enumerate(preguntas[:3])
        )

        acts = ses.get("actividades", [])
        acts_txt = "  →  ".join(
            f"{a.get('momento','?')} ({a.get('duracion_min','?')} min)"
            for a in acts
        )

        lineas += [
            f"━━━  Sesión {num}  |  {fecha_str}  ━━━━━━━━━━━━━━━━━━━━━",
            f"📌  Tema: {tema}",
            f"🎯  {tipo}  |  Bloom: {bloom}",
            f"✅  Competencia:",
            f"    {comp}",
        ]
        if acts_txt:
            lineas.append(f"⏱️   {acts_txt}")
        if pregs_txt:
            lineas.append(f"❓  Preguntas socráticas:\n{pregs_txt}")
        if eval_f:
            lineas.append(f"📊  Eval. formativa: {eval_f}")
        lineas.append("")

    lineas += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "✅  Planeación lista. Puedes copiar este texto a Word.",
        "    Para nueva planeación: botón 🎓  o  /planeacion",
    ]

    return "\n".join(lineas)
