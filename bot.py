import os
import json
import logging
import asyncio
import random
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

# MODÈLE GROQ
GROK_MODEL = "llama-3.3-70b-versatile"
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# CONFIGURATION DU QUIZ
GROUP_SESSIONS = {}
TEMPS_PAR_QUESTION = 60   # ← Temps par défaut (60 secondes)
NOMBRE_TOTAL_QUESTIONS = 50  

# ====================== BANQUE DE QUESTIONS ======================
QUESTIONS_INFAS_SVT = [
    {"question": "[Anatomie] Quel diamètre du détroit supérieur (DS) mesure normalement 10,5 cm et constitue le diamètre utile ou chirurgical du bassin osseux ?", "options": ["Le diamètre conjugué anatomique", "Le diamètre promonto-rétro-pubien (PRP)", "Le diamètre diagonal", "Le diamètre transverse maximal"], "reponse_correcte": 1},
    {"question": "[Anatomie] Quel muscle principal constitue le plancher pelvien postérieur ?", "options": ["Le muscle élévateur de l'anus (levator ani)", "Le muscle bulbo-spongieux", "Le muscle transverse profond", "Le muscle ischio-caverneux"], "reponse_correcte": 0},
    {"question": "[Physiologie] Lors du cycle menstruel, quelle hormone hypophysaire déclenche l'ovulation ?", "options": ["La Progestérone", "L'Oestradiol", "L'Hormone Lutéinisante (LH)", "L'Hormone Folliculo-Stimulante (FSH)"], "reponse_correcte": 2},
    # ... (tu peux garder toutes tes questions)
    # Je les ai raccourcies ici pour la lisibilité, remets-les toutes si tu veux
]

# ====================== FONCTIONS ======================

async def generer_quiz_groq() -> dict:
    if not groq_client:
        return None
    # ... (fonction inchangée, tu peux la remettre telle quelle)
    try:
        completion = groq_client.chat.completions.create(
            model=GROK_MODEL,
            messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return json.loads(completion.choices[0].message.content.strip())
    except:
        return None


async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change le temps par question"""
    chat_id = update.effective_chat.id
    
    global TEMPS_PAR_QUESTION   # ← Déclaration global en PREMIER
    
    if not context.args:
        await update.message.reply_text(f"⏱️ Temps actuel : **{TEMPS_PAR_QUESTION} secondes** par question.\n\nUtilise : `/temps 60`")
        return

    try:
        nouveau_temps = int(context.args[0])
        if nouveau_temps < 30 or nouveau_temps > 180:
            await update.message.reply_text("❌ Temps entre 30 et 180 secondes.")
            return
            
        ancien = TEMPS_PAR_QUESTION
        TEMPS_PAR_QUESTION = nouveau_temps
        
        await update.message.reply_text(f"✅ Temps mis à jour : **{ancien}s → {nouveau_temps}s**")
        
    except ValueError:
        await update.message.reply_text("❌ Utilisation : `/temps 60`")


async def envoyer_question_groupe(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    # ... (cette fonction reste presque identique)
    # Je te donne juste la partie modifiée :
    if chat_id not in GROUP_SESSIONS:
        return
    session = GROUP_SESSIONS[chat_id]
    if session["status"] == "paused":
        return

    session["current_quiz_index"] += 1
    if session["current_quiz_index"] > session["total_questions"]:
        await afficher_classement_final(context, chat_id)
        return

    # ... (le reste de la fonction reste le même que dans la version précédente)

    # À la fin de la fonction :
    for _ in range(TEMPS_PAR_QUESTION + 5):
        await asyncio.sleep(1)
        if chat_id not in GROUP_SESSIONS or GROUP_SESSIONS[chat_id]["status"] == "paused":
            return


# Les autres fonctions (start_quiz_command, pause, resume, stop, etc.) restent identiques à la version précédente.

# ====================== MAIN ======================
def main():
    if not TELEGRAM_TOKEN:
        logger.error("Token Telegram non trouvé.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("quiz", start_quiz_command))
    application.add_handler(CommandHandler("pause", pause_quiz_command))
    application.add_handler(CommandHandler("resume", resume_quiz_command))
    application.add_handler(CommandHandler("stop", stop_quiz_command))
    application.add_handler(CommandHandler("temps", set_time_command))
    
    application.add_handler(PollAnswerHandler(recevoir_reponse_quiz))

    logger.info("🤖 Bot démarré avec succès ! Temps par défaut : 60s")
    application.run_polling()


if __name__ == "__main__":
    main()
