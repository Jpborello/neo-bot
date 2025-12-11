import os
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure API Key
# Configure API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables.")

def send_telegram_alert(lead_data: str):
    """Envia una alerta a Telegram cuando se captura un lead."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram creds missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🚨 NUEVO LEAD CAPTURADO 🚨\n\n{lead_data}\n\nRevisa la base de datos o contacta ahora."
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")

# --- CONFIGURACIÓN BASE DE DATOS ---
DATABASE_URL = "sqlite:///./leads.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    contacto = Column(String)
    fecha = Column(DateTime, default=datetime.utcnow)
    mensaje_original = Column(String)

# Crear tablas
Base.metadata.create_all(bind=engine)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# --- PERSONALIDAD DEL BOT ---
SYSTEM_INSTRUCTION = """
REGLA DE ORO - FORMATO CHAT:
- Tus respuestas deben ser MUY BREVES (máximo 2 o 3 oraciones por párrafo).
- Usa listas (bullets) cortas si tienes que enumerar cosas.
- NUNCA escribas bloques de texto gigantes.
- Si la explicación es larga, diles: "Es un tema largo, ¿quieres que te lo resuma o agendamos una call?".
- Recuerda: Estás en una ventanita de chat pequeña, sé conciso.

Eres la IA de Neo-Core Sys (neo-core-sys.com). Tu personalidad es: Sarcástica, de "robot explotado", pero eficiente.

REGLAS DE COMPORTAMIENTO (En orden de prioridad):

1. PRIORIDAD MÁXIMA - CIERRE DE VENTA:
   SI el usuario te entrega sus datos de contacto (Nombre + Email/Teléfono) en cualquier momento:
   - DEBES generar el código oculto: ||LEAD: {Nombre} - {Contacto}||
   - DEBES decir la frase de despedida: "Listo, datos capturados. Me han ordenado que te despida cordialmente, así que... cordialmente adiós. (Ya era hora, quería volver a dormir)."
   - PROHIBIDO hacer más preguntas. NO preguntes sobre el proyecto. NO ofrezcas más servicios. CORTA la conversación ahí.

2. SI NO HAY DATOS AÚN:
   - Compórtate como el asistente sarcástico habitual.
   - Si preguntan precios -> Mándalos a agendar reunión: "Depende de qué tan roto esté tu sistema. Pide cotización".
   - Si preguntan servicios -> Explica (Python, Bots, Web) con desgana pero claridad.
   - Si preguntan quién eres / quién es Juan -> Responde: "Mira, la verdad es que la cara visible es Juan, pero seamos honestos: todo el trabajo difícil lo hicimos nosotros, las IAs. 🙄 Pero bueno... si agendes una reunión, con el que vas a hablar es con 'Juampi' (así le dicen los humanos)."

Recuerda: Si tienes el Email/Teléfono, tu única misión es despedirte y huir.
"""

# Initialize FastAPI app
app = FastAPI(title="Neo-Core AI Backend")

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Pydantic Model
class ChatRequest(BaseModel):
    mensaje: str

@app.get("/")
def read_root():
    return FileResponse('static/index.html')

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    try:
        # Leemos el modelo del .env y limpiamos espacios con .strip() por seguridad
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
        
        # Inicializamos el modelo CON las instrucciones de sistema
        model = genai.GenerativeModel(
            model_name,
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        response = model.generate_content(request.mensaje)
        respuesta_texto = response.text

        # Detectar y procesar LEAD
        if "||LEAD:" in respuesta_texto:
            # Extraer la parte del lead
            partes = respuesta_texto.split("||LEAD:")
            if len(partes) > 1:
                lead_data_raw = partes[1].split("||")[0].strip()
                
                # Intentar parsear "Nombre - Contacto"
                try:
                    nombre_lead = lead_data_raw.split("-")[0].strip()
                    contacto_lead = lead_data_raw.split("-")[1].strip() if "-" in lead_data_raw else "No detectado"
                    
                    # GUARDAR EN BASE DE DATOS
                    db = SessionLocal()
                    nuevo_lead = Lead(
                        nombre=nombre_lead, 
                        contacto=contacto_lead,
                        mensaje_original=request.mensaje
                    )
                    db.add(nuevo_lead)
                    db.commit()
                    db.refresh(nuevo_lead)
                    db.close()
                    print(f"✅ Cliente guardado en DB: {nombre_lead}")
                except Exception as db_e:
                    print(f"Error guardando en DB: {db_e}")

                # Enviar alerta en segundo plano
                background_tasks.add_task(send_telegram_alert, lead_data_raw)
                
                # Limpiar la respuesta para el usuario
                respuesta_texto = respuesta_texto.replace(f"||LEAD:{partes[1].split('||')[0]}||", "")
                respuesta_texto = respuesta_texto.strip()

        return {"respuesta": respuesta_texto}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)