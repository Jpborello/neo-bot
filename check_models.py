import google.generativeai as genai
import os
from dotenv import load_dotenv

# Cargar variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Error: No se encontró la API KEY en el archivo .env")
else:
    genai.configure(api_key=api_key)
    print(f"🔑 Probando con Key: {api_key[:5]}...*****")
    print("\n📋 LISTA DE MODELOS DISPONIBLES:")
    
    try:
        found = False
        for m in genai.list_models():
            # Filtramos solo los que sirven para chatear (generateContent)
            if 'generateContent' in m.supported_generation_methods:
                print(f"  ✅ {m.name}")
                found = True
        
        if not found:
            print("⚠️ No se encontraron modelos compatibles con 'generateContent'.")
            
    except Exception as e:
        print(f"❌ Error al conectar con Google: {e}")