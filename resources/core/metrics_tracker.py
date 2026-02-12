"""
Sistema de Métricas y Monitoreo para Raymundo
Tracking de uso de tokens, requests y estadísticas
"""
import json
from datetime import datetime
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = CORE_DIR.parent
DATA_DIR = RESOURCES_DIR / "data"

class MetricsTracker:
    """Rastreador de métricas de uso del agente"""
    
    def __init__(self, metrics_file='metrics.json'):
        provided_path = Path(metrics_file)
        if provided_path.exists() or provided_path.is_absolute() or provided_path.parent != Path('.'):
            resolved = provided_path
        else:
            resolved = (DATA_DIR / provided_path).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.metrics_file = resolved
        self.metrics = self._load_metrics()
    
    def _load_metrics(self):
        """Carga métricas desde archivo"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        # Métricas por defecto
        return {
            'inicio': datetime.now().isoformat(),
            'total_requests': 0,
            'total_tokens_ollama': 0,
            'total_tokens_gpt4o': 0,
            'total_tokens_groq': 0,  # Nuevo: Groq
            'requests_por_tipo': {
                'chat': 0,
                'presentacion': 0,
                'documento': 0,
                'hoja_calculo': 0,
                'web_scraping': 0,
                'correccion': 0,
                'vision': 0
            },
            'errores': 0,
            'tiempo_promedio_respuesta': 0,
            'usuarios_unicos': 0,
            'ultimo_request': None
        }
    
    def _save_metrics(self):
        """Guarda métricas en archivo"""
        try:
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando métricas: {e}")
    
    def track_request(self, tipo='chat', tokens_used=0, modelo='ollama', tiempo_respuesta=0, user_id=None):
        """Registra un request y actualiza métricas"""
        self.metrics['total_requests'] += 1
        
        # Tokens por modelo
        if modelo == 'ollama':
            self.metrics['total_tokens_ollama'] += tokens_used
        elif modelo == 'gpt4o':
            self.metrics['total_tokens_gpt4o'] += tokens_used
        elif modelo == 'groq':
            self.metrics['total_tokens_groq'] += tokens_used  # Nuevo
        
        # Requests por tipo
        if tipo in self.metrics['requests_por_tipo']:
            self.metrics['requests_por_tipo'][tipo] += 1
        
        # Tiempo promedio
        total = self.metrics['total_requests']
        tiempo_prev = self.metrics['tiempo_promedio_respuesta']
        self.metrics['tiempo_promedio_respuesta'] = ((tiempo_prev * (total - 1)) + tiempo_respuesta) / total
        
        # Último request
        self.metrics['ultimo_request'] = datetime.now().isoformat()
        
        self._save_metrics()
    
    def track_error(self):
        """Registra un error"""
        self.metrics['errores'] += 1
        self._save_metrics()
    
    def get_stats(self):
        """Obtiene estadísticas formateadas"""
        # GitHub Models FREE TIER: 15 RPM, 150 RPD, 150K TPM
        # Ollama: 100% gratuito (local)
        tokens_gpt4o = self.metrics['total_tokens_gpt4o']
        requests = self.metrics['total_requests']
        
        # Rate limits de GitHub Models (Free Tier)
        tpm_limit = 150000  # tokens por minuto
        rpd_limit = 150     # requests por día
        
        return {
            'estado': '✅ Operativo',
            'inicio': self.metrics['inicio'],
            'uptime': self._calcular_uptime(),
            'total_requests': self.metrics['total_requests'],
            'tokens': {
                'ollama_local': self.metrics['total_tokens_ollama'],
                'gpt4o_cloud': self.metrics['total_tokens_gpt4o'],
                'total': self.metrics['total_tokens_ollama'] + self.metrics['total_tokens_gpt4o']
            },
            'requests_por_tipo': self.metrics['requests_por_tipo'],
            'errores': self.metrics['errores'],
            'tasa_exito': self._calcular_tasa_exito(),
            'tiempo_promedio_respuesta': f"{self.metrics['tiempo_promedio_respuesta']:.2f}s",
            'ultimo_request': self.metrics['ultimo_request'],
            'tier': '🆓 Gratuito',
            'rate_limits': {
                'tokens_pm': f"{tokens_gpt4o} / {tpm_limit:,} TPM",
                'requests_dia': f"{requests} / {rpd_limit} RPD",
                'uso_tpm': f"{(tokens_gpt4o / tpm_limit * 100):.1f}%" if tpm_limit > 0 else '0%',
                'uso_rpd': f"{(requests / rpd_limit * 100):.1f}%" if rpd_limit > 0 else '0%'
            }
        }
    
    def get_stats_formatted(self):
        """Obtiene estadísticas formateadas para WhatsApp"""
        stats = self.get_stats()
        
        texto = f"""📊 **ESTADÍSTICAS DE RAYMUNDO**

🟢 **Estado:** {stats['estado']}
⏰ **Uptime:** {stats['uptime']}
{stats['tier']} **Plan:** GitHub Models Free + Ollama Local

📈 **Uso General:**
• Total requests: {stats['total_requests']}
• Errores: {stats['errores']}
• Tasa de éxito: {stats['tasa_exito']}
• Tiempo promedio: {stats['tiempo_promedio_respuesta']}

🤖 **Tokens Consumidos:**
• Ollama (local): {stats['tokens']['ollama_local']:,} 🆓
• GPT-4o (cloud): {stats['tokens']['gpt4o_cloud']:,} 🆓
• **Total**: {stats['tokens']['total']:,}

📊 **Rate Limits (GitHub Models Free):**
• Tokens/Minuto: {stats['rate_limits']['tokens_pm']} ({stats['rate_limits']['uso_tpm']})
• Requests/Día: {stats['rate_limits']['requests_dia']} ({stats['rate_limits']['uso_rpd']})

📋 **Requests por Tipo:**
• Chat: {stats['requests_por_tipo']['chat']}
• Presentaciones: {stats['requests_por_tipo']['presentacion']}
• Documentos: {stats['requests_por_tipo']['documento']}
• Hojas de cálculo: {stats['requests_por_tipo']['hoja_calculo']}
• Web scraping: {stats['requests_por_tipo']['web_scraping']}
• Correcciones: {stats['requests_por_tipo']['correccion']}
• Visión/Imágenes: {stats['requests_por_tipo']['vision']}

🕐 **Último request:** {stats['ultimo_request'] or 'Nunca'}

💡 **Nota:** Todo el uso es gratuito dentro de los límites del Free Tier
"""
        return texto
    
    def _calcular_uptime(self):
        """Calcula el tiempo de funcionamiento"""
        inicio = datetime.fromisoformat(self.metrics['inicio'])
        ahora = datetime.now()
        delta = ahora - inicio
        
        dias = delta.days
        horas = delta.seconds // 3600
        minutos = (delta.seconds % 3600) // 60
        
        if dias > 0:
            return f"{dias}d {horas}h {minutos}m"
        elif horas > 0:
            return f"{horas}h {minutos}m"
        else:
            return f"{minutos}m"
    
    def _calcular_tasa_exito(self):
        """Calcula porcentaje de éxito"""
        total = self.metrics['total_requests']
        if total == 0:
            return "100%"
        
        errores = self.metrics['errores']
        exito = ((total - errores) / total) * 100
        return f"{exito:.1f}%"
    
    def reset_metrics(self):
        """Reinicia todas las métricas"""
        self.metrics = {
            'inicio': datetime.now().isoformat(),
            'total_requests': 0,
            'total_tokens_ollama': 0,
            'total_tokens_gpt4o': 0,
            'requests_por_tipo': {
                'chat': 0,
                'presentacion': 0,
                'documento': 0,
                'hoja_calculo': 0,
                'web_scraping': 0,
                'correccion': 0,
                'vision': 0
            },
            'errores': 0,
            'tiempo_promedio_respuesta': 0,
            'usuarios_unicos': 0,
            'ultimo_request': None
        }
        self._save_metrics()
