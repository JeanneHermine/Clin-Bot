import os
import sys
import xml.etree.ElementTree as ET
import requests
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.db import SessionLocal
from app.models import Patient, OtpChallenge

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_patients():
    db = SessionLocal()
    try:
        return db.query(Patient).all()
    finally:
        db.close()

def get_latest_otp(whatsapp_number: str):
    db = SessionLocal()
    try:
        log_path = os.path.join(ROOT_DIR, "twilio_simulation.log")
        if not os.path.exists(log_path):
            return None
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Look backwards for a line containing the number and OTP
        for line in reversed(lines):
            try:
                import json
                data = json.loads(line)
                if data.get("to") == whatsapp_number and "OTP" in data.get("body", ""):
                    import re
                    match = re.search(r'\b\d{6}\b', data["body"])
                    if match:
                        return match.group(0)
            except Exception:
                continue
        return None
    finally:
        db.close()

def send_message(from_number: str, body: str):
    url = "http://localhost:8000/twilio/whatsapp"
    try:
        resp = requests.post(url, data={"From": from_number, "Body": body})
        if resp.status_code != 200:
            return f"Erreur du serveur ({resp.status_code}): {resp.text}"
    except Exception as e:
        return f"Erreur de connexion au serveur local : {e}\nAssurez-vous que le serveur FastAPI tourne sur http://localhost:8000"
    
    # Parse Twiml
    try:
        root = ET.fromstring(resp.text)
        message_element = root.find("Message")
        if message_element is not None:
            body_element = message_element.find("Body")
            media_elements = message_element.findall("Media")
            media_urls = [m.text for m in media_elements if m.text]
            response_text = body_element.text if body_element is not None else ""
            if media_urls:
                response_text += "\n[Médias / Liens de téléchargement] :\n" + "\n".join(media_urls)
            return response_text
        return "Pas de réponse (TwiML vide)."
    except Exception as e:
        return f"Erreur d'analyse de la réponse TwiML : {e}\nRéponse brute :\n{resp.text}"

def main():
    clear_screen()
    print("=" * 60)
    print("      SIMULATEUR DE CHATBOT WHATSAPP (Cid)")
    print("=" * 60)
    
    patients = get_patients()
    if not patients:
        print("Aucun patient dans la base de données. Veuillez d'abord en créer un.")
        return
    
    print("\nChoisissez un patient pour simuler sa conversation :")
    for i, p in enumerate(patients, start=1):
        print(f" {i}. {p.first_name} {p.last_name} ({p.whatsapp_number})")
    
    try:
        choice = input("\nVotre choix (numéro) : ")
        idx = int(choice) - 1
        if idx < 0 or idx >= len(patients):
            print("Choix invalide.")
            return
        patient = patients[idx]
    except Exception:
        print("Saisie invalide.")
        return
    
    whatsapp_number = patient.whatsapp_number
    clear_screen()
    print("=" * 60)
    print(f" Discussion sous l'identité de : {patient.first_name} {patient.last_name} ({whatsapp_number})")
    print(" Instructions :")
    print(" - Tapez vos messages ci-dessous.")
    print(" - Tapez 'menu' pour afficher le menu principal.")
    print(" - Si vous demandez vos résultats, le code OTP sera imprimé ici")
    print("   (lu automatiquement depuis twilio_simulation.log).")
    print(" - Tapez 'quitter' pour arrêter le simulateur.")
    print("=" * 60)
    
    # Start with a welcome message or menu
    print(f"\n[Système] Envoi automatique de 'menu' pour démarrer la session...")
    reply = send_message(whatsapp_number, "menu")
    print(f"\n🤖 Assistant Cid :\n{reply}\n")
    
    while True:
        try:
            msg = input("👤 Vous : ")
            if msg.strip().lower() == 'quitter':
                print("Fin du simulateur. À bientôt !")
                break
            
            if not msg.strip():
                continue
                
            reply = send_message(whatsapp_number, msg)
            print(f"\n🤖 Assistant Cid :\n{reply}\n")
            
            # Check if we should help with OTP
            if "otp" in reply.lower() or "sécuriser" in reply.lower() or "code" in reply.lower():
                import time
                time.sleep(1) # Let the file write complete
                otp = get_latest_otp(whatsapp_number)
                if otp:
                    print(f"🔑 [SIMULATEUR] OTP détecté pour {patient.first_name} : {otp}")
                    print("   Saisissez ce code ci-dessous pour valider.\n")
                    
        except KeyboardInterrupt:
            print("\nFin du simulateur. À bientôt !")
            break

if __name__ == "__main__":
    main()
