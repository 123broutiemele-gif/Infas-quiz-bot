import os
import json
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from groq import Groq

# Configuration des logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# CONFIGURATION
TELEGRAM_TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    raise ValueError("Les variables d'environnement TOKEN ou GROQ_API_KEY sont manquantes.")

groq_client = Groq(api_key=GROQ_API_KEY)

# CONSTANTES
QUESTIONS_PAR_QUIZ = 25
GROUP_SESSIONS = {}

# ADAPTATION DU TEMPS DE RÉPONSE
def calculer_temps_reponse(question_data: dict) -> int:
    texte_total = question_data["question"] + " ".join(question_data["options"])
    nombre_mots = len(texte_total.split())
    # Temps de base 20s + lecture
    temps = 20 + (int(nombre_mots / 5) * 1.5)
    # Bonus pour la technicité obstétricale
    return min(max(int(temps), 25), 60)

# GÉNÉRATION DE QUESTION VIA GROQ (IA)
async def generer_question_obstetrique_ia() -> dict:
    """Génère une question sur les soins obstétricaux via Groq."""
    
    system_prompt = (
        "Tu es un expert en enseignement des soins obstétricaux. "
        "Génère une question de QCM de niveau académique pour étudiants en santé/sage-femme. "
        "Domaines : Suivi de grossesse, accouchement, soins post-partum, complications obstétricales, néonatologie de base, hygiène en milieu de maternité.\n\n"
        "Tu dois répondre sous la forme d'un objet JSON strict :\n"
        "- 'question': Le texte de la question.\n"
        "- 'options': Un tableau de 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3).\n\n"
        "Critère : La question doit être inédite, variée, et directement liée aux soins obstétricaux."
    )

    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Génère une nouvelle question de QCM sur les soins obstétricaux."}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Erreur de génération Groq : {e}")
        return None

# ORCHESTRATION
async def orchestrer_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if chat_id not in GROUP_SESSIONS or GROUP_SESSIONS[chat_id]["status"] != "running":
        return

    session = GROUP_SESSIONS[chat_id]
    session["current_index"] += 1

    if session["current_index"] > QUESTIONS_PAR_QUIZ:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🏁 *Fin du Quiz spécial Soins Obstétricaux !*\nBravo pour vos révisions."
        )
        GROUP_SESSIONS.pop(chat_id, None)
        return

    msg_attente = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔄 _Génération de la question {session['current_index']}/{QUESTIONS_PAR_QUIZ}..._"
    )

    quiz_data = await generer_question_obstetrique_ia()
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)
    except: pass

    if not quiz_data or "question" not in quiz_data:
        session["current_index"] -= 1
        await asyncio.sleep(2)
        asyncio.create_task(orchestrer_quiz(context, chat_id))
        return

    duree_sondage = calculer_temps_reponse(quiz_data)

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"❓ [Obstétrique {session['current_index']}/{QUESTIONS_PAR_QUIZ}] {quiz_data['question']}"[:300],
            options=[opt[:100] for opt in quiz_data["options"]],
            correct_option_id=int(quiz_data["reponse_correcte"]),
            type="quiz",
            is_anonymous=False,
            open_period=duree_sondage
        )
    except Exception as e:
        logger.error(f"Erreur d'envoi Telegram : {e}")

    await asyncio.sleep(duree_sondage + 2)
    asyncio.create_task(orchestrer_quiz(context, chat_id))

# COMMANDES
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Bot de Révision : Soins Obstétricaux*\n\n"
        "Je génère des questions basées sur les meilleures pratiques en obstétrique.\n"
        "Tapez `/start_obs` pour commencer une série de 25 questions."
    )

async def cmd_start_obs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in GROUP_SESSIONS:
        await update.message.reply_text("Un quiz est déjà en cours.")
        return

    GROUP_SESSIONS[chat_id] = {"status": "running", "current_index": 0}
    await update.message.reply_text("🚀 Quiz obstétrique lancé !")
    asyncio.create_task(orchestrer_quiz(context, chat_id))

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("start_obs", cmd_start_obs))
    application.run_polling()

if __name__ == "__main__":
    main()
