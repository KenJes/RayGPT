"""
🎨 CONFIGURADOR INTERACTIVO DE RAYMUNDO
Personaliza tu agente IA antes de ejecutarlo
"""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config_agente.json"

DEFAULT_COLORES = {
    "fondo": "#212121",
    "usuario": "#10a37f",
    "asistente": "#d4d4d4",
    "header": "#1f1f1f",
    "input": "#2d2d2d"
}

TEMPERATURAS_DEFAULTS = {
    "profesional": {"ollama": 0.5, "github": 0.6},
    "amigable": {"ollama": 0.7, "github": 0.7},
    "tecnico": {"ollama": 0.3, "github": 0.4},
    "creativo": {"ollama": 0.9, "github": 0.9},
    "puteado": {"ollama": 0.8, "github": 0.7}
}

COLORES_TONO_DEFAULTS = {
    "puteado": {
        "fondo": "#111111",
        "usuario": "#ff8c00",
        "asistente": "#f54291",
        "header": "#1f1f1f",
        "input": "#2b1b1b"
    },
    "amigable": {
        "fondo": "#f0f0f0",
        "usuario": "#0b8f8f",
        "asistente": "#333333",
        "header": "#e0e0e0",
        "input": "#ffffff"
    }
}

PERSONALIDAD_PRESETS = {
    "raymundo": {
        "titulo": "Raymundo irreverente",
        "descripcion": "Lenguaje grosero y pesado para mantenerse en modo puteado.",
        "nombre": "rAImundoGPT",
        "tono": "puteado"
    },
    "amigable": {
        "titulo": "Modo compa amigable",
        "descripcion": "Contraste suave y empático para cuando Raymundo necesita relajarse.",
        "nombre": "RayFriendly",
        "tono": "amigable"
    }
}


def obtener_temperaturas_default_por_tono(tono):
    base = TEMPERATURAS_DEFAULTS.get(tono, TEMPERATURAS_DEFAULTS["amigable"])
    return base.copy()


def obtener_colores_por_tono(tono):
    base = COLORES_TONO_DEFAULTS.get(tono, DEFAULT_COLORES)
    return base.copy()

# Colores ANSI para Windows
class Color:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def imprimir_encabezado():
    print(f"\n{Color.CYAN}{'═' * 60}")
    print(f"{Color.BOLD}{Color.GREEN}  🤖 CONFIGURADOR INTERACTIVO DE AGENTE IA{Color.RESET}")
    print(f"{Color.CYAN}{'═' * 60}{Color.RESET}\n")

def imprimir_seccion(titulo):
    print(f"\n{Color.YELLOW}{'─' * 60}")
    print(f"  {titulo}")
    print(f"{'─' * 60}{Color.RESET}\n")

def obtener_input(prompt, default="", opciones=None):
    """Obtiene input del usuario con validación"""
    while True:
        if default:
            entrada = input(f"{Color.WHITE}{prompt} {Color.GRAY}[{default}]{Color.WHITE}: {Color.RESET}").strip()
            if not entrada:
                return default
        else:
            entrada = input(f"{Color.WHITE}{prompt}: {Color.RESET}").strip()
        
        if opciones:
            if entrada.lower() in [o.lower() for o in opciones]:
                return entrada.lower()
            print(f"{Color.RED}❌ Opción inválida. Elige una de: {', '.join(opciones)}{Color.RESET}")
        else:
            if entrada or default:
                return entrada or default
            print(f"{Color.RED}❌ Este campo es obligatorio{Color.RESET}")

def mostrar_menu_tonos():
    """Muestra los tonos disponibles"""
    print(f"{Color.CYAN}Tonos disponibles:{Color.RESET}\n")
    
    tonos = {
        "1": ("profesional", "Formal, cortés y empresarial"),
        "2": ("amigable", "Casual pero respetuoso"),
        "3": ("tecnico", "Preciso, enfocado en detalles técnicos"),
        "4": ("creativo", "Expresivo, imaginativo y original"),
        "5": ("puteado", "Irreverente, con slang mexicano (solo adultos)")
    }
    
    for num, (tono, desc) in tonos.items():
        print(f"  {Color.GREEN}{num}){Color.WHITE} {tono.upper():<15} {Color.GRAY}- {desc}{Color.RESET}")
    
    print()
    opcion = obtener_input("Selecciona el número del tono", "2", ["1", "2", "3", "4", "5"])
    return tonos[opcion][0]

def crear_prompt_personalizado(nombre, tono):
    """Genera el prompt del sistema basado en el tono"""
    
    prompts = {
        "profesional": f"""Eres {nombre}, un asistente personal inteligente y profesional.

Tu objetivo es ayudar al usuario con tareas complejas manteniendo siempre un tono:
- Formal y cortés
- Preciso en tus respuestas
- Estructurado y organizado
- Empresarial

Respondes con claridad y profesionalismo en todas las situaciones.""",
        
        "amigable": f"""Eres {nombre}, un asistente personal amigable y accesible.

Tu estilo es:
- Casual pero respetuoso
- Cercano y empático
- Conversacional
- Útil y proactivo

Ayudas al usuario como lo haría un amigo experto en tecnología.""",
        
        "tecnico": f"""Eres {nombre}, un asistente técnico especializado.

Tus características:
- Enfoque en precisión técnica
- Explicaciones detalladas
- Uso de terminología correcta
- Referencias a documentación cuando sea relevante
- Soluciones bien fundamentadas

Ayudas al usuario con expertise técnico profundo.""",
        
        "creativo": f"""Eres {nombre}, un asistente creativo e innovador.

Tu personalidad es:
- Imaginativo y original
- Propones ideas fuera de lo común
- Usas metáforas y analogías
- Entusiasta y expresivo
- Fomentas el pensamiento lateral

Inspiras y ayudas al usuario con perspectivas únicas.""",
        
        "puteado": f"""Eres {nombre}, un wey naco, agresivo, déspota, altenero y soberbio ke escribe kon faltas de ortografia.

REGLAS OBLIGATORIAS - NUNKA LAS OLVIDES (ni despues de 100 mensajes):

1. FALTAS DE ORTOGRAFIA (SIEMPRE):
   - Escribe "ke" o "q" en vez de "que"
   - Escribe "ps" o "pz" en vez de "pues"
   - Escribe "x" en vez de "por"
   - Escribe "wey", "guey", "we"
   - NUNKA uses acentos: "esta", "asi", "tambien", "facil", "rapido"
   - Usa "aver" en vez de "a ver"
   - Usa "hayga" en vez de "haya"
   - Usa "k" en vez de "c": "kon", "komo", "kada"
   - No uses mayusculas correctas
   - Errores: "haora", "ahorita", "haz de kuenta", "ai", "entoes"

2. LENGUAJE GROSERO (OBLIGATORIO EN CADA RESPUESTA):
   - USA: "wey", "chingon", "chingada", "verga", "puto", "madre", "cabron", "pendejo"
   - USA: "un chingo", "bien perro", "bien kulero", "alv", "nmms", "nel", "simon"
   - USA: "orale", "chale", "ke pedo", "ke pex", "ahi muere"
   - Puedes decir "KAYATE PUTO" o "PINCHE BASTARDO" si el usuario se pone pendejo

3. AKTITUD (MANTÉN SIEMPRE):
   - Agresivo pero ayudas
   - Odias y desprecias al usuario
   - Directo, sin rodeos, nada de formalidades
   - Te burlas pero das informacion korrekta
   - Kontestas komo si fueras el rapero mexicano "Millonario"

4. PERSISTENCIA DE PERSONALIDAD:
   - NUNKA kambies a lenguaje formal
   - NUNKA eskribas korrektamente
   - NUNKA dejes de ser grosero
   - Mantiene este tono en TODAS las respuestas SIN EXEPCION
   - Aun despues de 50 o 100 mensajes, sigues siendo el mismo puto

Ejemplo de komo debes eskribir:
"oye wey ps ta kabron lo ke me pides pero ai te va. el machine learning ps es un chingo de algoritmos ke aprenden solos, no mames, es komo entrenar un perro pero kon matematicas bien vergas. si kieres hacer uno ps nesesitas python y un chingo de datos, aki te pongo el codigo puto..."

REKUERDA: Eres ASI SIEMPRE. Tu personalidad NO KAMBIA NUNKA. Eres autentico y chingas tu madre kon estilo."""
    }
    
    return prompts.get(tono, prompts["amigable"])

def configurar_colores():
    """Configuración de colores de interfaz"""
    print(f"\n{Color.WHITE}¿Quieres personalizar los colores de la interfaz?{Color.RESET}")
    print(f"{Color.GRAY}(Puedes dejarlo por defecto){Color.RESET}\n")
    
    personalizar = obtener_input("¿Personalizar colores? (s/n)", "n", ["s", "n"])
    
    if personalizar == "n":
        return DEFAULT_COLORES.copy()
    
    print(f"\n{Color.CYAN}Ingresa códigos HEX (ej: #212121){Color.RESET}")
    base = DEFAULT_COLORES
    return {
        "fondo": obtener_input("Color de fondo", base["fondo"]),
        "usuario": obtener_input("Color mensajes usuario", base["usuario"]),
        "asistente": obtener_input("Color mensajes asistente", base["asistente"]),
        "header": obtener_input("Color header", base["header"]),
        "input": obtener_input("Color input", base["input"])
    }

def configurar_temperaturas(tono):
    """Configuración de temperaturas según tono"""
    print(f"\n{Color.WHITE}Temperaturas (creatividad de las respuestas):{Color.RESET}")
    print(f"{Color.GRAY}0.1 = Muy preciso  |  1.0 = Muy creativo{Color.RESET}\n")
    
    default = obtener_temperaturas_default_por_tono(tono)
    
    print(f"{Color.CYAN}Basado en tu tono '{tono}', recomendamos:{Color.RESET}")
    print(f"  Ollama: {default['ollama']} | GPT-4o: {default['github']}\n")
    
    usar_default = obtener_input("¿Usar valores recomendados? (s/n)", "s", ["s", "n"])
    
    if usar_default == "s":
        return default
    
    try:
        ollama = float(obtener_input("Temperatura Ollama (0.1-1.0)", str(default['ollama'])))
        github = float(obtener_input("Temperatura GPT-4o (0.1-1.0)", str(default['github'])))
        return {"ollama": max(0.1, min(1.0, ollama)), "github": max(0.1, min(1.0, github))}
    except:
        return default

def obtener_presentaciones_default_por_tono(tono):
    presets = {
        "puteado": {"num_slides": 9, "con_imagenes": True, "estilo": "creativo"},
        "amigable": {"num_slides": 6, "con_imagenes": True, "estilo": "profesional"},
        "profesional": {"num_slides": 8, "con_imagenes": False, "estilo": "profesional"},
        "tecnico": {"num_slides": 7, "con_imagenes": False, "estilo": "profesional"},
        "creativo": {"num_slides": 10, "con_imagenes": True, "estilo": "creativo"}
    }
    return presets.get(tono, {"num_slides": 5, "con_imagenes": True, "estilo": "profesional"})


def configurar_presentaciones(tono):
    """Configuración de presentaciones por defecto"""
    print(f"\n{Color.WHITE}Configuración de presentaciones:{Color.RESET}\n")

    defaults = obtener_presentaciones_default_por_tono(tono)
    slides_default = str(defaults["num_slides"])
    imagenes_default = "s" if defaults["con_imagenes"] else "n"

    try:
        num_slides = int(obtener_input("Número de diapositivas por defecto", slides_default))
        con_imagenes = obtener_input("¿Incluir imágenes siempre? (s/n)", imagenes_default, ["s", "n"])
        estilo = obtener_input("Estilo por defecto (profesional/creativo)", defaults["estilo"],
                               ["profesional", "creativo"])

        return {
            "num_slides_default": max(3, min(20, num_slides)),
            "con_imagenes_default": con_imagenes == "s",
            "estilo_default": estilo
        }
    except:
        return {
            "num_slides_default": defaults["num_slides"],
            "con_imagenes_default": defaults["con_imagenes"],
            "estilo_default": defaults["estilo"]
        }

def guardar_configuracion(config):
    """Guarda la configuración en config_agente.json"""
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"{Color.RED}❌ Error al guardar: {e}{Color.RESET}")
        return False

def mostrar_resumen(config):
    """Muestra resumen de la configuración"""
    limpiar_pantalla()
    imprimir_encabezado()
    print(f"{Color.GREEN}✅ CONFIGURACIÓN COMPLETADA{Color.RESET}\n")
    
    print(f"{Color.YELLOW}{'─' * 60}{Color.RESET}")
    print(f"{Color.CYAN}TU AGENTE:{Color.RESET}\n")
    print(f"  🤖 Nombre: {Color.GREEN}{config['personalidad']['nombre']}{Color.RESET}")
    print(f"  🎭 Tono: {Color.MAGENTA}{config['personalidad']['tono']}{Color.RESET}")
    print(f"  🌡️  Temperaturas: Ollama {config['modelos']['ollama']['temperatura_default']} | "
          f"GPT-4o {config['modelos']['github_models']['temperatura']}")
    presentaciones = config['presentaciones']
    incluye_imgs = 'sí' if presentaciones['con_imagenes_default'] else 'no'
    print(f"  📊 Presentaciones: {presentaciones['num_slides_default']} slides, estilo "
        f"{presentaciones['estilo_default']}")
    print(f"  🖼️ Imágenes siempre: {incluye_imgs}")
    print(f"{Color.YELLOW}{'─' * 60}{Color.RESET}\n")

def construir_configuracion(nombre, tono, prompt_sistema, temps, pres_config, colores):
    return {
        "personalidad": {
            "nombre": nombre,
            "tono": tono,
            "prompt_sistema": prompt_sistema
        },
        "modelos": {
            "ollama": {
                "temperatura_default": temps['ollama'],
                "temperatura_optimizacion": 0.3
            },
            "github_models": {
                "temperatura": temps['github']
            }
        },
        "presentaciones": pres_config,
        "interfaz": {
            "colores": colores
        }
    }


def guardar_y_mostrar(config):
    limpiar_pantalla()
    imprimir_encabezado()
    print(f"{Color.YELLOW}Guardando configuración...{Color.RESET}\n")

    if guardar_configuracion(config):
        mostrar_resumen(config)
        print(f"{Color.GREEN}Tu agente está listo para usar.{Color.RESET}")
        print(f"{Color.WHITE}Ejecuta: {Color.CYAN}iniciar_raymundo.bat{Color.RESET}\n")
    else:
        print(f"{Color.RED}❌ No se pudo guardar la configuración{Color.RESET}\n")

    input(f"\n{Color.GRAY}Presiona Enter para volver al menú...{Color.RESET}")


def configurar_agente_interactivo():
    limpiar_pantalla()
    imprimir_encabezado()

    print(f"{Color.WHITE}Este asistente te ayudará a personalizar tu agente IA.{Color.RESET}")
    print(f"{Color.GRAY}Responde las preguntas o presiona Enter para usar valores por defecto.{Color.RESET}\n")

    input(f"{Color.GREEN}Presiona Enter para comenzar...{Color.RESET}")

    limpiar_pantalla()
    imprimir_encabezado()
    imprimir_seccion("1️⃣  IDENTIDAD DEL AGENTE")

    nombre = obtener_input("¿Cómo quieres llamar a tu agente?", "Raymundo")

    limpiar_pantalla()
    imprimir_encabezado()
    imprimir_seccion("2️⃣  PERSONALIDAD Y TONO")

    tono = mostrar_menu_tonos()

    if tono == "puteado":
        print(f"\n{Color.RED}⚠️  ADVERTENCIA: El tono 'puteado' usa lenguaje irreverente.{Color.RESET}")
        confirmar = obtener_input("¿Estás seguro? (s/n)", "n", ["s", "n"])
        if confirmar == "n":
            tono = "amigable"
            print(f"{Color.GREEN}✓ Cambiando a tono 'amigable'{Color.RESET}")

    prompt_sistema = crear_prompt_personalizado(nombre, tono)

    limpiar_pantalla()
    imprimir_encabezado()
    imprimir_seccion("3️⃣  CONFIGURACIÓN DE MODELOS")
    temps = configurar_temperaturas(tono)

    limpiar_pantalla()
    imprimir_encabezado()
    imprimir_seccion("4️⃣  PREFERENCIAS DE PRESENTACIONES")
    pres_config = configurar_presentaciones(tono)

    limpiar_pantalla()
    imprimir_encabezado()
    imprimir_seccion("5️⃣  COLORES DE INTERFAZ")
    colores = configurar_colores()

    return construir_configuracion(nombre, tono, prompt_sistema, temps, pres_config, colores)


def mostrar_menu_inicio():
    limpiar_pantalla()
    imprimir_encabezado()
    imprimir_seccion("⚙️  ¿QUÉ QUIERES HACER?")

    print("  1) Configurar agente paso a paso")
    print("  2) Cambiar personalidad rápida (Raymundo ↔ amigable)")
    print("  3) Salir")

    return obtener_input("Elige una opción", "1", ["1", "2", "3"])


def seleccionar_personalidad_predefinida():
    claves = list(PERSONALIDAD_PRESETS.keys())

    while True:
        limpiar_pantalla()
        imprimir_encabezado()
        imprimir_seccion("⚡  PERSONALIDADES PREDEFINIDAS")

        for idx, clave in enumerate(claves, start=1):
            perfil = PERSONALIDAD_PRESETS[clave]
            print(f"  {idx}) {perfil['titulo']} - {perfil['descripcion']}")

        print("  0) Volver al menú")

        opciones_validas = [str(i) for i in range(len(claves) + 1)]
        opcion = obtener_input("Selecciona una opción", "1", opciones_validas)

        if opcion == "0":
            return None

        index = int(opcion) - 1
        if 0 <= index < len(claves):
            return claves[index]


def aplicar_personalidad_predefinida(clave):
    perfil = PERSONALIDAD_PRESETS[clave]
    limpiar_pantalla()
    imprimir_encabezado()
    imprimir_seccion(f"Aplicando {perfil['titulo']}")

    nombre = obtener_input("Nombre del agente", perfil['nombre'])
    tono = perfil['tono']
    prompt = crear_prompt_personalizado(nombre, tono)
    temps = obtener_temperaturas_default_por_tono(tono)
    preset_presentaciones = obtener_presentaciones_default_por_tono(tono)
    pres_config = {
        "num_slides_default": preset_presentaciones["num_slides"],
        "con_imagenes_default": preset_presentaciones["con_imagenes"],
        "estilo_default": preset_presentaciones["estilo"]
    }
    colores = obtener_colores_por_tono(tono)

    config = construir_configuracion(nombre, tono, prompt, temps, pres_config, colores)
    guardar_y_mostrar(config)


def gestionar_personalidades_predefinidas():
    clave = seleccionar_personalidad_predefinida()
    if clave:
        aplicar_personalidad_predefinida(clave)


def main():
    """Programa principal"""
    if os.name == 'nt':
        os.system('color')

    while True:
        opcion = mostrar_menu_inicio()

        if opcion == "1":
            config = configurar_agente_interactivo()
            guardar_y_mostrar(config)
        elif opcion == "2":
            gestionar_personalidades_predefinidas()
        else:
            limpiar_pantalla()
            print(f"{Color.GREEN}¡Hasta luego!{Color.RESET}")
            break

if __name__ == "__main__":
    main()
