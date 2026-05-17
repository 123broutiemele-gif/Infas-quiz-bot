import os
import json
import logging
import asyncio
import urllib.request
import urllib.error
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuration des logs pour Railway afin de suivre l'activité du bot en temps réel
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 1. RECUPERATION DES VARIABLES DE VOTRE RAILWAY
# Lecture du Token Telegram (Votre variable s'appelle "TOKEN")
TELEGRAM_TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")

# Recherche intelligente de la clé Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    # Si le nom exact n'est pas trouvé, on cherche une variable qui commence par "GROQ"
    for env_name, env_value in os.environ.items():
        if env_name.startswith("GROQ_"):
            GROQ_API_KEY = env_value
            logger.info(f"Clé Groq détectée automatiquement via la variable : {env_name}")
            break

# Modèle Groq recommandé (très performant pour le JSON et la médecine)
GROK_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _executer_requete_groq(payload: dict, headers: dict) -> str:
    """
    Fonction synchrone exécutant l'appel à l'API de Groq via la bibliothèque native urllib.
    Sera exécutée dans un thread séparé pour ne pas bloquer le bot.
    """
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(GROQ_API_URL, data=data_bytes, headers=headers, method="POST")
    
    # Timeout de 15 secondes pour éviter de bloquer indéfiniment
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read().decode("utf-8")


async def generer_quiz_groq() -> dict:
    """
    Appelle l'API de Groq pour générer une question médicale structurée.
    Utilise le mode JSON de Groq et s'exécute de manière asynchrone non-bloquante.
    """
    if not GROQ_API_KEY:
        raise ValueError("La clé API Groq est introuvable dans vos variables de service Railway.")

    system_prompt = (
        "Tu es un enseignant et tuteur expert préparant les étudiants ivoiriens au concours de l'INFAS "
        "(Institut National de Formation des Agents de Santé). Tu génères des questions de révision rigoureuses, "
        "médicalement exactes et adaptées au concours.\n\n"
        "ATTENTION SCIENTIFIQUE :\n"
        "- Ne confonds jamais le débit cardiaque (exprimé en L/min, environ 5 L/min chez l'adulte au repos) "
        "avec la fréquence cardiaque (exprimée en battements par minute, environ 60-80 bpm).\n"
        "- Sois extrêmement précis sur les constantes biologiques et de secourisme.\n\n"
        "Tu dois impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
        "- 'question': La question posée sous forme de texte.\n"
        "- 'options': Un tableau (Array) contenant exactement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) représentant l'index de la bonne réponse.\n\n"
        "Ne mets aucun texte explicatif avant ou après le JSON. Renvoie uniquement le JSON brut."
    )
    
    user_prompt = (
        "Génère une question de quiz portant au hasard sur : l'anatomie, la physiologie, "
        "le secourisme de base, les soins infirmiers de base, la pharmacologie ou l'éthique médicale. "
        "Fournis 4 options de réponse réalistes, dont une seule est incontestablement correcte."
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},  # Force Groq à envoyer du JSON pur
        "temperature": 0.6
    }

    # Système de retry (Backoff exponentiel) pour faire face aux surcharges temporaires de l'API
    delays = [1, 2, 4, 8, 16]
    for attempt, delay in enumerate(delays):
        try:
            # On exécute l'appel réseau synchrone dans un thread asynchrone pour ne pas ralentir le bot
            response_text = await asyncio.to_thread(_executer_requete_groq, payload, headers)
            result = json.loads(response_text)
            
            content = result["choices"][0]["message"]["content"].strip()
            
            # Nettoyage de sécurité au cas où l'IA encapsulerait son JSON
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            quiz_data = json.loads(content)
            
            # Validation des clés requises
            if all(k in quiz_data for k in ["question", "options", "reponse_correcte"]):
                if len(quiz_data["options"]) == 4:
                    return quiz_data
                    
            logger.warning("Structure JSON invalide reçue de Groq. Nouvelle tentative...")
            
        except urllib.error.HTTPError as e:
            logger.error(f"Erreur HTTP Groq (Code {e.code}): {e.read().decode('utf-8', errors='ignore')}")
        except Exception as e:
            logger.error(f"Exception lors de la génération de question (Tentative {attempt+1}): {e}")
        
        # Attente progressive avant de réessayer
        if attempt < len(delays) - 1:
            await asyncio.sleep(delay)
            
    raise Exception("Impossible de générer une question correcte après plusieurs essais.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message d'accueil lorsque l'utilisateur lance le bot."""
    welcome_text = (
        "🎯 *Bienvenue sur INFAS QUIZ !*\n\n"
        "Ce bot vous aide à réviser votre concours d'entrée à l'INFAS grâce à l'IA Groq.\n\n"
        "👉 Tapez la commande /quiz pour générer une question interactive."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Génère la question et l'envoie sous forme de Quiz natif interactif."""
    status_message = await update.message.reply_text("⏳ Génération de la question par Groq en cours...")
    
    try:
        # Appel de l'API de Groq
        quiz_data = await generer_quiz_groq()
        
        question = quiz_data["question"]
        options = quiz_data["options"]
        reponse_correcte = quiz_data["reponse_correcte"]
        
        # On efface le message d'attente
        await status_message.delete()
        
        # Envoi du quiz natif Telegram
        await update.message.reply_poll(
            question=question[:300],  # Limite Telegram : 300 caractères pour la question
            options=[opt[:100] for opt in options],  # Limite Telegram : 100 caractères par option
            correct_option_id=reponse_correcte,
            type="quiz",
            is_anonymous=False
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la commande /quiz : {e}")
        await status_message.edit_text(
            "❌ Une erreur est survenue lors de la création du quiz.\n"
            "Veuillez patienter quelques instants et réessayez avec /quiz !"
        )


def main():
    if not TELEGRAM_TOKEN:
        logger.error("La variable d'environnement 'TOKEN' (ou 'TELEGRAM_TOKEN') est absente sur Railway. Le bot ne peut pas démarrer.")
        return
    if not GROQ_API_KEY:
        logger.error("La variable d'environnement de votre clé d'API Groq est introuvable. Ajoutez 'GROQ_API_KEY' sur Railway.")
        return

    # Initialisation et configuration de l'application Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Déclaration des commandes
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("quiz", quiz_command))

    logger.info("🤖 Bot INFAS QUIZ démarré avec succès sous Groq !")
    application.run_polling()


if __name__ == "__main__":
    main()
