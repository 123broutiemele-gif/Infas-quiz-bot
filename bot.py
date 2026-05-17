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
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Structure pour stocker l'état du quiz par groupe
# { chat_id: { "scores": {user_id: {"name": str, "points": int}}, "current_quiz_index": int, "total_questions": int, "correct_option_id": int } }
GROUP_SESSIONS = {}
TEMPS_PAR_QUESTION = 25  # Durée en secondes pour répondre à chaque question
NOMBRE_TOTAL_QUESTIONS = 45  # Nombre de questions par session de quiz


async def generer_quiz_groq() -> dict:
    """Appelle l'API de Groq pour générer un QCM médical au format JSON."""
    system_prompt = (
        "Tu es un enseignant expert préparant les étudiants ivoiriens au concours de l'INFAS.\n"
        "Tu dois impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
        "- 'question': La question posée sous forme de texte.\n"
        "- 'options': Un tableau contenant exactement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) représentant l'index de la bonne réponse.\n\n"
        "Renvoie uniquement le JSON brut, sans fioritures."
    )
    user_prompt = "Génère une question de quiz aléatoire sur l'anatomie, la physiologie, le secourisme ou les soins infirmiers."

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
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Erreur Groq: {e}")
        return None


async def envoyer_question_groupe(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Génère et envoie la question suivante dans le groupe."""
    session = GROUP_SESSIONS[chat_id]
    session["current_quiz_index"] += 1
    
    # Si on a atteint le nombre maximum de questions, on affiche le classement final
    if session["current_quiz_index"] > session["total_questions"]:
        await afficher_classement_final(context, chat_id)
        return

    msg_attente = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"⏳ *Préparation de la question {session['current_quiz_index']}/{session['total_questions']}...*",
        parse_mode="Markdown"
    )
    
    quiz_data = await generer_quiz_groq()
    await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)

    if not quiz_data:
        await context.bot.send_message(chat_id=chat_id, text="❌ Erreur de génération, passage à la question suivante.")
        await envoyer_question_groupe(context, chat_id)
        return

    session["correct_option_id"] = int(quiz_data["reponse_correcte"])

    # Envoi du Quiz Telegram natif fermé automatiquement après X secondes
    poll_msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"❓ [Q.{session['current_quiz_index']}] {quiz_data['question']}"[:300],
        options=[opt[:100] for opt in quiz_data["options"]],
        correct_option_id=session["correct_option_id"],
        type="quiz",
        is_anonymous=False,
        open_period=TEMPS_PAR_QUESTION  # Le chronomètre Telegram !
    )
    
    # On attend la fin du chronomètre + 2 secondes de battement avant d'enchaîner
    await asyncio.sleep(TEMPS_PAR_QUESTION + 2)
    await envoyer_question_groupe(context, chat_id)


async def recevoir_reponse_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enregistre les points des membres du groupe lorsqu'ils répondent correctement."""
    answer = update.poll_answer
    
    # On cherche à quel groupe appartient ce vote (Telegram ne donne pas directement le chat_id dans poll_answer)
    for chat_id, session in GROUP_SESSIONS.items():
        if "correct_option_id" in session:
            # Vérifie si l'utilisateur a choisi la bonne option
            if answer.option_ids and answer.option_ids[0] == session["correct_option_id"]:
                user_id = answer.user.id
                user_name = answer.user.first_name
                
                # Initialise le score du joueur s'il n'existe pas
                if user_id not in session["scores"]:
                    session["scores"][user_id] = {"name": user_name, "points": 0}
                
                # Ajoute 1 point pour la bonne réponse
                session["scores"][user_id]["points"] += 1
                break


async def start_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Démarre une session de quiz chronométrée pour le groupe."""
    chat_id = update.effective_chat.id
    
    # Initialisation de la session de ce groupe
    GROUP_SESSIONS[chat_id] = {
        "scores": {},
        "current_quiz_index": 0,
        "total_questions": NOMBRE_TOTAL_QUESTIONS
    }
    
    await update.message.reply_text(
        f"🏁 *Lancement du défi INFAS QUIZ !*\n\n"
        f"• Nombre de questions : {NOMBRE_TOTAL_QUESTIONS}\n"
        f"• Chronomètre : {TEMPS_PAR_QUESTION} secondes par question.\n\n"
        "Préparez-vous, la première question arrive !",
        parse_mode="Markdown"
    )
    
    # Lance la première question en arrière-plan
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def afficher_classement_final(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Calcule et affiche le tableau des scores à la fin du jeu."""
    session = GROUP_SESSIONS.get(chat_id)
    if not session:
        return

    texte_classement = "🏆 *FIN DU QUIZ - CLASSEMENT DES AGENTS DE SANTÉ* 🏆\n\n"
    
    if not session["scores"]:
        texte_classement += "😢 Personne n'a obtenu de points durant cette session."
    else:
        # Tri des joueurs du plus grand nombre de points au plus petit
        joueurs_tries = sorted(session["scores"].values(), key=lambda x: x["points"], reverse=True)
        
        medailles = ["🥇", "🥈", "🥉"]
        for i, joueur in enumerate(joueurs_tries):
            prefixe = medailles[i] if i < 3 else "🔹"
            texte_classement += f"{prefixe} *{joueur['name']}* : {joueur['points']} points\n"

    await context.bot.send_message(chat_id=chat_id, text=texte_classement, parse_mode="Markdown")
    # Nettoyage de la mémoire
    GROUP_SESSIONS.pop(chat_id, None)


def main():
    if not TELEGRAM_TOKEN or not GROQ_API_KEY:
        logger.error("Variables d'environnement manquantes.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Changement de commande : /quiz lance la compétition dans le groupe
    application.add_handler(CommandHandler("quiz", start_quiz_command))
    application.add_handler(PollAnswerHandler(recevoir_reponse_quiz))

    logger.info("🤖 Bot INFAS QUIZ de Groupe démarré !")
    application.run_polling()


if __name__ == "__main__":
    main()
