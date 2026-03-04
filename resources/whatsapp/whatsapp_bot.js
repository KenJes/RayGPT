'use strict';

const path = require('path');
const fs = require('fs');
const axios = require('axios');
const qrcode = require('qrcode-terminal');
const { randomUUID } = require('crypto');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');

// ═══ ID único de esta instancia del bot (detectar procesos duplicados) ═══
const BOT_INSTANCE_ID = randomUUID().slice(0, 8);
console.log(`🆔 Bot instance ID: ${BOT_INSTANCE_ID} (PID: ${process.pid})`);

const API_BASE_URL = process.env.RAIMUNDO_API_URL || 'http://127.0.0.1:5000';
const CHAT_ENDPOINT = `${API_BASE_URL}/chat`;
const HEALTH_ENDPOINT = `${API_BASE_URL}/health`;
const AUDIO_STT_ENDPOINT = `${API_BASE_URL}/audio/stt`;
const AUDIO_TTS_ENDPOINT = `${API_BASE_URL}/audio/tts`;
const AUDIO_CHAT_ENDPOINT = `${API_BASE_URL}/audio/chat`;

const DATA_PATH = path.join(__dirname, '.wwebjs_cache');
if (!fs.existsSync(DATA_PATH)) {
  fs.mkdirSync(DATA_PATH, { recursive: true });
}

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: DATA_PATH }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  }
});

client.on('qr', qr => {
  console.clear();
  console.log('📱 Escanea este código QR para enlazar WhatsApp:');
  qrcode.generate(qr, { small: true });
});

client.on('ready', async () => {
  console.log(`✅ [${BOT_INSTANCE_ID}] Bot de WhatsApp listo. Verificando servidor Flask...`);

  // Reintentar conexión hasta 3 veces
  let intentos = 0;
  const maxIntentos = 3;

  while (intentos < maxIntentos) {
    try {
      const { data } = await axios.get(HEALTH_ENDPOINT, { timeout: 5000 });
      console.log(`🌐 Servidor Flask OK | Personalidad: ${data.personality}`);
      return;
    } catch (error) {
      intentos++;
      if (intentos < maxIntentos) {
        console.log(`⏳ Intento ${intentos}/${maxIntentos} - Esperando servidor Flask...`);
        await new Promise(resolve => setTimeout(resolve, 3000));
      } else {
        console.error('⚠️  No se pudo contactar al servidor Flask después de varios intentos.');
        console.error('   Asegúrate de que el servidor está ejecutándose: python whatsapp_server.py');
      }
    }
  }
});

client.on('auth_failure', msg => {
  console.error('❌ Error de autenticación en WhatsApp:', msg);
});

async function enviarMensajeAlServidor(texto, userId) {
  const payload = {
    mensaje: texto,
    user_id: userId
  };

  const { data } = await axios.post(CHAT_ENDPOINT, payload, {
    timeout: 60_000,
    headers: { 'Content-Type': 'application/json' }
  });

  return data;
}

async function enviarArchivoSiExiste(chatId, rutaArchivo, caption) {
  if (!rutaArchivo || !fs.existsSync(rutaArchivo)) {
    return false;
  }

  try {
    const media = MessageMedia.fromFilePath(rutaArchivo);
    await client.sendMessage(chatId, media, caption ? { caption } : {});
    return true;
  } catch (error) {
    console.error('⚠️  No pude enviar el archivo adjunto:', error.message);
    return false;
  }
}

// Usar 'message_create' en lugar de 'message' para capturar TODOS los mensajes
// incluyendo los que el usuario envía desde su propio dispositivo
client.on('message_create', async message => {
  // Ignorar mensajes de estados (status)
  if (message.isStatus) {
    return;
  }

  // Detectar si es un mensaje de voz
  if (message.type === 'ptt' || message.type === 'audio') {
    console.log(`🎤 Mensaje de voz recibido - fromMe: ${message.fromMe}, from: ${message.from}`);
    console.log(`⚠️  Mensaje de voz ignorado (usa comandos de texto para activar el bot)`);
    return;
  }

  if (!message.body || !message.body.trim()) {
    return;
  }

  const texto = message.body.trim();

  // Determinar el chat correcto para responder
  const chatId = message.fromMe ? message.to : message.from;
  const userId = message.from;

  // Logging detallado para debug
  console.log(`💬 [${BOT_INSTANCE_ID}] Mensaje recibido:`);
  console.log(`   - From: ${userId}`);
  console.log(`   - fromMe: ${message.fromMe}`);
  console.log(`   - Chat destino: ${chatId}`);
  console.log(`   - Texto: ${texto.substring(0, 80)}`);

  // Comandos que siempre funcionan
  if (texto.toLowerCase() === '/ping') {
    await message.reply('🏓 Pong!');
    return;
  }

  if (texto.toLowerCase() === '/health') {
    try {
      const { data } = await axios.get(HEALTH_ENDPOINT, { timeout: 4000 });
      await message.reply(`✅ Servidor activo | Personalidad: ${data.personality}`);
    } catch (error) {
      await message.reply('⚠️  No pude contactar al servidor Flask.');
    }
    return;
  }

  // FILTRO PRINCIPAL: Solo procesar si comienza con comandos específicos
  const comandosPermitidos = ['/raymundo', '/rai', '/amigable', '/puteado', '/ray', '/putedo', '/friendly'];
  const tieneComando = comandosPermitidos.some(cmd => texto.toLowerCase().startsWith(cmd));

  if (!tieneComando) {
    console.log(`⚠️  Mensaje ignorado (sin comando): ${texto.substring(0, 30)}...`);
    return;
  }

  console.log(`✅ [${BOT_INSTANCE_ID}] Mensaje con comando detectado, procesando...`);

  // Detectar si el mensaje solicita respuesta con audio
  const solicitaAudio = detectarSolicitudAudio(texto);

  if (solicitaAudio) {
    await manejarComandoAudio(message, texto, chatId);
    return;
  }

  try {
    await message.reply('🤖 Procesando tu mensaje, dame un momento...');
    const respuesta = await enviarMensajeAlServidor(texto, userId);

    if (respuesta.respuesta) {
      await client.sendMessage(chatId, respuesta.respuesta);
    }

    if (respuesta.archivo) {
      const enviado = await enviarArchivoSiExiste(chatId, respuesta.archivo, respuesta.tipo_archivo);
      if (!enviado) {
        await client.sendMessage(chatId, '⚠️  No pude enviar el archivo generado, revisa el servidor.');
      }
    }
  } catch (error) {
    console.error(`❌ [${BOT_INSTANCE_ID}] Error procesando mensaje:`, error.message);
    console.error('   Stack:', error.stack?.split('\n').slice(0, 3).join(' | '));
    if (error.code) console.error('   Code:', error.code);
    if (error.response) {
      console.error('   Response status:', error.response.status);
      const respData = error.response.data;
      if (Buffer.isBuffer(respData)) {
        console.error('   Response (buffer):', respData.toString('utf-8').substring(0, 200));
      } else {
        console.error('   Response data:', JSON.stringify(respData)?.substring(0, 200));
      }
    }
    const detalle = error.response?.data?.error || error.message;
    await client.sendMessage(chatId, `🚨 Ocurrió un error: ${detalle}`);
  }
});

function detectarSolicitudAudio(texto) {
  /**
   * Detecta si el usuario solicita una respuesta con audio
   * Soporta español e inglés
   */
  const textoLower = texto.toLowerCase();

  const patronesAudio = [
    // Español
    'en un audio',
    'en audio',
    'con un audio',
    'con audio',
    'manda un audio',
    'manda audio',
    'envia un audio',
    'envía un audio',
    'envia audio',
    'envía audio',
    'responde con audio',
    'responde en audio',
    'contestame con audio',
    'contéstame con audio',
    'contestame en audio',
    'contéstame en audio',
    'hazme un audio',
    'házmelo en audio',
    'mandame audio',
    'mándame audio',
    'grabame un audio',
    'grábame un audio',
    // English
    'send me an audio',
    'send an audio',
    'send audio',
    'in an audio',
    'in audio',
    'with an audio',
    'with audio',
    'audio message',
    'voice message',
    'record an audio',
    'record audio',
    'make an audio',
    'make audio',
    'give me an audio',
    'give me audio'
  ];

  return patronesAudio.some(patron => textoLower.includes(patron));
}

// ═══════════════════════════════════════════════════════════════
// AUDIO: Limpiar frases de solicitud para extraer solo el TEMA
// ═══════════════════════════════════════════════════════════════
function limpiarMensajeParaAudio(mensaje) {
  let limpio = mensaje;

  // Regex para remover frases de solicitud de audio (EN + ES)
  const patronesRemover = [
    // English
    /send\s+(?:me\s+)?(?:an?\s+)?audio\s*/gi,
    /(?:in|with)\s+(?:an?\s+)?audio\s*/gi,
    /audio\s+message\s*/gi,
    /voice\s+message\s*/gi,
    /record\s+(?:me\s+)?(?:an?\s+)?audio\s*/gi,
    /make\s+(?:me\s+)?(?:an?\s+)?audio\s*/gi,
    /give\s+(?:me\s+)?(?:an?\s+)?audio\s*/gi,
    /can\s+you\s+/gi,
    // Spanish
    /(?:en|con)\s+(?:un\s+)?audio\s*/gi,
    /manda(?:me)?\s+(?:un\s+)?audio\s*/gi,
    /env[ií]a(?:me)?\s+(?:un\s+)?audio\s*/gi,
    /hazme\s+(?:un\s+)?audio\s*/gi,
    /gr[aá]bame\s+(?:un\s+)?audio\s*/gi,
  ];

  for (const patron of patronesRemover) {
    limpio = limpio.replace(patron, ' ');
  }

  // Limpiar preposiciones y saludos sueltos al inicio
  limpio = limpio.replace(/^\s*(speaking|talking)\s+(about|on)\s+/i, '');
  limpio = limpio.replace(/^\s*(about|on|regarding)\s+/i, '');
  limpio = limpio.replace(/^\s*(hi|hello|hey)\s+/i, '');
  limpio = limpio.replace(/\s+/g, ' ').trim();

  return limpio;
}

async function manejarComandoAudio(message, textoCompleto, chatId) {
  console.log(`🎙️ [${BOT_INSTANCE_ID}] Audio solicitado para chat ${chatId}`);

  try {
    // 1. Limpiar comandos del bot (/ray, /raymundo, etc.)
    let mensaje = textoCompleto;
    const comandos = ['/raymundo', '/rai', '/puteado', '/amigable', '/friendly', '/ray', '/putedo'];

    for (const comando of comandos) {
      if (mensaje.toLowerCase().startsWith(comando)) {
        mensaje = mensaje.substring(comando.length).trim();
        break;
      }
    }

    if (!mensaje) {
      await message.reply('⚠️  Debes proporcionar un mensaje\n\nEjemplo: /raymundo dile a Kenneth en un audio que es la IA');
      return;
    }

    // 2. Limpiar frases de audio → extraer solo el TEMA
    //    "send me an audio Speaking about tokenization in LLM"
    //    → "tokenization in LLM"
    const tema = limpiarMensajeParaAudio(mensaje);

    // Si queda muy corto, usar el mensaje original (sin las frases de audio)
    const mensajeParaIA = tema.length >= 5 ? tema : mensaje;

    console.log(`🎯 [${BOT_INSTANCE_ID}] Tema extraído para audio: "${mensajeParaIA}"`);

    // NO enviar mensaje de estado — solo enviaremos el audio + transcripción al final

    // 3. Enviar TEMA LIMPIO al agente — UNA SOLA llamada al LLM
    const respuestaChat = await enviarMensajeAlServidor(mensajeParaIA, chatId);

    if (!respuestaChat.respuesta) {
      await message.reply('⚠️  No pude obtener una respuesta del agente.');
      return;
    }

    const textoRespuesta = respuestaChat.respuesta;
    console.log(`💬 [${BOT_INSTANCE_ID}] Respuesta del agente (${textoRespuesta.length} chars): ${textoRespuesta.substring(0, 80)}...`);

    // 4. Convertir respuesta a audio via /audio/tts
    const response = await axios.post(`${API_BASE_URL}/audio/tts`, {
      texto: textoRespuesta,
      user_id: chatId
    }, {
      timeout: 90_000,
      responseType: 'arraybuffer'
    });

    // Verificar que recibimos datos de audio válidos
    if (!response.data || response.data.length < 100) {
      console.error(`❌ [${BOT_INSTANCE_ID}] Audio recibido está vacío o muy pequeño:`, response.data?.length);
      // Fallback: enviar solo el texto
      await client.sendMessage(chatId, `⚠️ No pude generar el audio, aquí va la respuesta en texto:\n\n${textoRespuesta}`);
      return;
    }

    // Detectar extensión del archivo basándose en Content-Type
    const contentType = response.headers['content-type'] || 'audio/wav';
    const extension = contentType.includes('mp3') ? 'mp3' : 'wav';

    // Guardar audio temporalmente
    const tempDir = path.join(__dirname, 'whatsapp_temp');
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }

    const audioPath = path.join(tempDir, `raymundo_${Date.now()}.${extension}`);
    fs.writeFileSync(audioPath, response.data);

    console.log(`🔊 [${BOT_INSTANCE_ID}] Audio guardado: ${audioPath} (${response.data.length} bytes)`);

    // 5. Enviar SOLO el audio como mensaje de voz
    const media = MessageMedia.fromFilePath(audioPath);
    await client.sendMessage(chatId, media, {
      sendAudioAsVoice: true
    });

    // 6. Enviar transcripción del audio como texto (solo este mensaje)
    await client.sendMessage(chatId, `📝 *Transcripción:*\n${textoRespuesta}`);

    console.log(`✅ [${BOT_INSTANCE_ID}] Audio + transcripción enviados a ${chatId}`);

    // Limpiar archivo temporal
    setTimeout(() => {
      try {
        fs.unlinkSync(audioPath);
      } catch (e) {
        console.warn('No se pudo eliminar archivo temporal:', e.message);
      }
    }, 5000);

  } catch (error) {
    console.error(`❌ [${BOT_INSTANCE_ID}] Error generando audio:`, error.message);
    console.error('   Stack:', error.stack?.split('\n').slice(0, 3).join(' | '));
    if (error.code) console.error('   Code:', error.code);
    if (error.response) {
      console.error('   Status:', error.response.status);
      const respData = error.response.data;
      if (Buffer.isBuffer(respData)) {
        console.error('   Response (buffer):', respData.toString('utf-8').substring(0, 300));
      } else {
        console.error('   Response data:', JSON.stringify(respData)?.substring(0, 300));
      }
    }
    let mensajeError = '⚠️  No pude generar el audio.';

    if (error.response?.status === 500) {
      mensajeError += '\n\n💡 Asegúrate de que las dependencias de audio están instaladas en el servidor.';
    } else if (error.code === 'ECONNREFUSED') {
      mensajeError += '\n\n💡 El servidor Flask no está respondiendo.';
    } else if (error.code === 'ECONNABORTED') {
      mensajeError += '\n\n💡 El servidor tardó demasiado en responder (timeout).';
    }

    await client.sendMessage(chatId, mensajeError);
  }
}

async function manejarMensajeVoz(message) {
  const userId = message.from;

  console.log(`🎙️ Mensaje de voz recibido de ${userId}`);

  try {
    await message.reply('🎙️ Procesando tu mensaje de voz...');

    // Descargar el audio
    const media = await message.downloadMedia();

    if (!media) {
      await message.reply('⚠️  No pude descargar el audio.');
      return;
    }

    // Guardar audio temporalmente
    const tempDir = path.join(__dirname, 'whatsapp_temp');
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }

    const audioPath = path.join(tempDir, `audio_${Date.now()}.ogg`);
    const buffer = Buffer.from(media.data, 'base64');
    fs.writeFileSync(audioPath, buffer);

    console.log(`💾 Audio guardado en: ${audioPath}`);

    // Enviar audio al servidor para transcripción y respuesta
    const FormData = require('form-data');
    const form = new FormData();
    form.append('audio', fs.createReadStream(audioPath));
    form.append('user_id', userId);

    const { data } = await axios.post(AUDIO_CHAT_ENDPOINT, form, {
      headers: form.getHeaders(),
      timeout: 120_000,
      responseType: 'arraybuffer'
    });

    // Limpiar archivo temporal
    try {
      fs.unlinkSync(audioPath);
    } catch (e) {
      console.warn('No se pudo eliminar archivo temporal:', e.message);
    }

    // Guardar audio de respuesta
    const respuestaPath = path.join(tempDir, `respuesta_${Date.now()}.wav`);
    fs.writeFileSync(respuestaPath, data);

    console.log(`🔊 Audio de respuesta guardado: ${respuestaPath}`);

    // Enviar audio de respuesta
    const mediaRespuesta = MessageMedia.fromFilePath(respuestaPath);
    await client.sendMessage(userId, mediaRespuesta, {
      sendAudioAsVoice: true
    });

    console.log(`✅ Respuesta de audio enviada a ${userId}`);

    // Limpiar archivo de respuesta
    setTimeout(() => {
      try {
        fs.unlinkSync(respuestaPath);
      } catch (e) {
        console.warn('No se pudo eliminar archivo de respuesta:', e.message);
      }
    }, 5000);

  } catch (error) {
    console.error(`❌ [${BOT_INSTANCE_ID}] Error procesando mensaje de voz:`, error.message);
    console.error('   Stack:', error.stack?.split('\n').slice(0, 3).join(' | '));
    if (error.code) console.error('   Code:', error.code);
    let mensajeError = '⚠️  Ocurrió un error procesando tu mensaje de voz.';

    if (error.response?.status === 500) {
      mensajeError += '\n\n💡 Asegúrate de que:\n' +
        '1. El servidor Flask está ejecutándose\n' +
        '2. Las dependencias de audio están instaladas\n' +
        '3. FFmpeg está instalado en el sistema';
    }

    await client.sendMessage(userId, mensajeError);
  }
}

client.initialize();

process.on('SIGINT', () => {
  console.log('\n👋 Cerrando bot de WhatsApp...');
  client.destroy().finally(() => process.exit(0));
});
