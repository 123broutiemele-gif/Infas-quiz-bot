import os
import json
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from groq import Groq  # Import du SDK officiel de Groq

# Configuration des logs pour Railway afin de suivre l'activité du bot en temps réel
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 1. RÉCUPÉRATION DES VARIABLES DE VOTRE RAILWAY
TELEGRAM_TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")

# Recherche de la clé Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    for env_name, env_value in os.environ.items():
        if env_name.startswith("GROQ_"):
            GROQ_API_KEY = env_value
            logger.info(f"Clé Groq détectée automatiquement via la variable : {env_name}")
            break

# Modèle Groq recommandé
GROK_MODEL = "llama-3.3-70b-versatile"

# Initialisation sécurisée du client officiel Groq
# Le SDK gère nativement les en-têtes (User-Agent) pour éviter définitivement l'erreur 403 / 1010
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)


async def generer_quiz_groq() -> dict:
    """
    Appelle l'API de Groq via le SDK officiel pour générer une question médicale structurée.
    """
    if not groq_client:
        raise ValueError("La clé API Groq est introuvable dans vos variables de service Railway.")

    system_prompt = (
        "Tu es un enseignant et tuteur expert préparant les étudiants ivoiriens au concours de l'INFAS "
        "(Institut National de Formation des Agents de Santé). Tu génères des questions de révision rigoureuses, "
        "médicalement exactes et adaptées au concours.\n\n"
        "ATTENTION SCIENTIFIQUE :\n"
        "- Ne confonds jamais le débit cardiaque (exprimé en L/min, environ 5 L/min chez l'adulte au repos) "
        "avec la fréquence cardiaque (exprimée en battements par minute, environ 60-80 bpm).\n"
        "- Sois extrêmement précis sur les constantes biologiques et de secourisme.\n\n"
        "Tu devez impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
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

    # Système de retry pour faire face aux surcharges temporaires de l'API
    for attempt in range(3):
        try:
            # Appel asynchrone non-bloquant de Groq avec le format JSON activé
            completion = groq_client.chat.completions.create(
                model=GROK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.6
            )
            
            content = completion.choices[0].message.content.strip()
            quiz_data = json.loads(content)
            
            # Validation de la structure reçue
            if all(k in quiz_data for k in ["question", "options", "reponse_correcte"]):
                if len(quiz_data["options"]) == 4:
                    return quiz_data
                    
            logger.warning("Structure JSON invalide reçue de Groq. Nouvelle tentative...")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération Groq (Tentative {attempt+1}): {e}")
            
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
        # Appel de la fonction de génération
        quiz_data = await generer_quiz_groq()
        
        question = quiz_data["question"]
        options = quiz_data["options"]
        reponse_correcte = int(quiz_data["reponse_correcte"])
        
        # On efface le message d'attente
        await status_message.delete()
        
        # Envoi du quiz natif interactif Telegram
        await update.message.reply_poll(
            question=question[:300],  # Limites de sécurité de l'API Telegram
            options=[opt[:100] for opt in options],
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
        logger.error("La variable d'environnement 'TOKEN' ou 'TELEGRAM_TOKEN' est absente sur Railway.")
        return
    if not GROQ_API_KEY:
        logger.error("La variable d'environnement 'GROQ_API_KEY' est introuvable sur Railway.")
        return

    # Initialisation de l'application Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Déclaration des commandes
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("quiz", quiz_command))

    logger.info("🤖 Bot INFAS QUIZ démarré avec succès sous Groq SDK !")
    application.run_polling()


if __name__ == "__main__":
    main()
