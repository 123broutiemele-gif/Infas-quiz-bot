import os
import json
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, PollAnswerHandler, ContextTypes
from groq import Groq

# Configuration des logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# VARIABLES D'ENVIRONNEMENT
TELEGRAM_TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    for env_name, env_value in os.environ.items():
        if env_name.startswith("GROQ_"):
            GROQ_API_KEY = env_value
            break

GROK_MODEL = "llama-3.3-70b-versatile"

groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)


async def generer_quiz_groq() -> dict:
    """Appelle l'API de Groq pour générer un QCM au format JSON."""
    if not groq_client:
        raise ValueError("La clé API Groq est introuvable.")

    system_prompt = (
        "Tu es un enseignant et tuteur expert préparant les étudiants ivoiriens au concours de l'INFAS. "
        "Tu génères des questions de révision rigoureuses, médicalement exactes et adaptées au concours.\n\n"
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

    for attempt in range(3):
        try:
            completion = groq_client.chat.completions.create(
                model=GROK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            content = completion.choices[0].message.content.strip()
            quiz_data = json.loads(content)
            
            if all(k in quiz_data for k in ["question", "options", "reponse_correcte"]):
                if len(quiz_data["options"]) == 4:
                    return quiz_data
        except Exception as e:
            logger.error(f"Erreur Groq tentative {attempt+1}: {e}")
            
    raise Exception("Échec de génération du quiz.")


async def envoyer_nouveau_quiz(bot, chat_id):
    """Fonction centrale pour envoyer un quiz dans une discussion spécifique."""
    status_message = await bot.send_message(chat_id=chat_id, text="⏳ Préparation de la question suivante...")
    
    try:
        quiz_data = await generer_quiz_groq()
        
        await bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)
        
        await bot.send_poll(
            chat_id=chat_id,
            question=quiz_data["question"][:300],
            options=[opt[:100] for opt in quiz_data["options"]],
            correct_option_id=int(quiz_data["reponse_correcte"]),
            type="quiz",
            is_anonymous=False
        )
    except Exception as e:
        logger.error(f"Erreur envoi quiz: {e}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message.message_id,
            text="❌ Une erreur est survenue. Réessayez avec /quiz !"
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🎯 *Bienvenue sur INFAS QUIZ !*\n\n"
        "Le mode automatique est activé. Dès que vous répondrez à une question, "
        "la suivante se générera toute seule.\n\n"
        "👉 Tapez /quiz pour lancer la première question !"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lance la toute première question lorsque l'utilisateur le demande."""
    await envoyer_nouveau_quiz(context.bot, update.effective_chat.id)


async def recevoir_reponse_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Déclenché automatiquement dès que l'étudiant coche une réponse."""
    answer = update.poll_answer
    chat_id = answer.user.id  # Récupère l'identifiant de l'étudiant
    
    # Petite pause de 2 secondes pour laisser le temps à l'étudiant de voir s'il a eu juste ou faux
    await asyncio.sleep(2)
    
    # Envoie automatiquement la question d'après !
    await envoyer_nouveau_quiz(context.bot, chat_id)


def main():
    if not TELEGRAM_TOKEN or not GROQ_API_KEY:
        logger.error("Variables d'environnement manquantes.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Les commandes classiques
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("quiz", quiz_command))
    
    # LE RECOURS MAGIQUE : Écoute quand quelqu'un répond au sondage/quiz
    application.add_handler(PollAnswerHandler(recevoir_reponse_quiz))

    logger.info("🤖 Bot INFAS QUIZ en mode CONTINU démarré !")
    application.run_polling()


if __name__ == "__main__":
    main()
