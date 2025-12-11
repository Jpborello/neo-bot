import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: No encontré la API KEY en el archivo .env")
else:
    genai.configure(api_key=api_key)
    print("🔍 Buscando modelos FLASH disponibles para tu cuenta...")
    print("-" * 40)
    
    found = False
    try:
        for m in genai.list_models():
            # Filtramos solo los que sirven para chatear (generateContent)
            if 'generateContent' in m.supported_generation_methods:
                # Buscamos que tenga "flash" en el nombre
                if 'flash' in m.name.lower():
                    print(f"✅ {m.name}")
                    found = True
    except Exception as e:
        print(f"Error conectando con Google: {e}")

    if not found:
        print("❌ No encontré modelos 'Flash'. Listando TODOS los disponibles:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"👉 {m.name}")