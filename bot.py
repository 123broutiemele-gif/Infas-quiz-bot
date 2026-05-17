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

# Modèle Groq stable
GROK_MODEL = "llama-3.3-70b-specdec"
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# CONFIGURATION DU QUIZ (MISES À JOUR)
GROUP_SESSIONS = {}
TEMPS_PAR_QUESTION = 25  # Changement : 25 secondes par question
NOMBRE_TOTAL_QUESTIONS = 45  # Changement : 45 questions au total

# BANQUE DE QUESTIONS LOCALE (SVT - LE COEUR ET SA REGULATION)
QUESTIONS_INFAS_SVT = [
    {
        "question": "Quel tissu cardiaque particulier possède la propriété de s'auto-exciter et de se contracter rythmiquement en l'absence de toute innervation ?",
        "options": ["Le tissu myocardique", "Le tissu nodal", "Le réseau de Purkinje uniquement", "Le système nerveux parasympathique"],
        "reponse_correcte": 1
    },
    {
        "question": "Dans quel ordre précis l'onde d'excitation électrique se propage-t-elle à travers le tissu nodal ?",
        "options": [
            "Nœud sinusal -> Nœud septal -> Faisceau de His -> Réseau de Purkinje",
            "Réseau de Purkinje -> Faisceau de His -> Nœud septal -> Nœud sinusal",
            "Nœud septal -> Nœud sinusal -> Faisceau de His -> Réseau de Purkinje",
            "Faisceau de His -> Réseau de Purkinje -> Nœud sinusal -> Nœud septal"
        ],
        "reponse_correcte": 0
    },
    {
        "question": "Qu'appelle-t-on la phase de 'diastole' lors de la révolution cardiaque ?",
        "options": ["La phase de contraction des ventricules", "La fermeture des valvules sigmoïdes", "La phase de relâchement des cavités cardiaques", "L'expulsion du sang dans les artères"],
        "reponse_correcte": 2
    },
    {
        "question": "Lors d'une auscultation cardiaque au stéthoscope, à quoi correspond le premier bruit sec (souvent transcrit par 'TOUM') ?",
        "options": ["À la fermeture des valvules sigmoïdes", "À l'ouverture des valvules tricuspide et mitrale", "À l'accélération brutale du sang dans l'aorte", "À la fermeture des valvules tricuspide et mitrale"],
        "reponse_correcte": 3
    },
    {
        "question": "Quelle méthode clinique permet d'explorer le mécanisme de la révolution cardiaque en mesurant directement son activité électrique ?",
        "options": ["La palpation du pouls", "L'électrocardiogramme (ECG)", "L'auscultation au stéthoscope", "La mesure de la pression artérielle"],
        "reponse_correcte": 1
    },
    {
        "question": "Quel effet produit l'excitation du nerf vague (ou nerf pneumogastrique X) sur l'activité du cœur ?",
        "options": ["Une tachycardie immédiate", "Une augmentation de la force des contractions", "Une bradycardie par ralentissement du rythme grandiose", "Une interruption définitive de l'automatisme"],
        "reponse_correcte": 2
    },
    {
        "question": "Quel médiateur chimique est libéré au niveau de la synapse entre le nerf vague (X) et le nœud sinusal ?",
        "options": ["La noradrénaline", "L'acétylcholine (ACh)", "L'adrénaline", "Le glutamate"],
        "reponse_correcte": 1
    },
    {
        "question": "D'où proviennent les filets nerveux du système orthosympathique qui innervent le muscle cardiaque ?",
        "options": ["Du centre bulbaire directement", "Des ganglions de la chaîne orthosympathique reliés à la moelle épinière", "Du nerf crânien X", "Du cortex cérébral moteur"],
        "reponse_correcte": 1
    },
    {
        "question": "Quelle réponse hormonale adaptative observe-t-on lors d'une situation de danger ou de stress (comme l'audition d'un signal d'alarme) ?",
        "options": ["Une sécrétion massive d'acétylcholine par le foie", "Une libération accrue d'adrénaline dans le sang par les glandes surrénales", "Un blocage complet des récepteurs à la noradrénaline", "Une baisse drastique de la pression artérielle systolique"],
        "reponse_correcte": 1
    },
    {
        "question": "Quelle est la conséquence directe de la libération de noradrénaline au niveau du myocarde ?",
        "options": ["Une tachycardie (accélération du rythme cardiaque)", "Une bradycardie (ralentissement du rythme cardiaque)", "La relaxation totale et immédiate des parois ventriculaires", "L'inhibition des centres cardio-accélérateurs bulbaires"],
        "reponse_correcte": 0
    }
]


async def generer_quiz_groq() -> dict:
    """Appelle l'API de Groq en cas de secours pour générer un QCM au format JSON."""
    if not groq_client:
        return None
        
    system_prompt = (
        "Tu es un enseignant expert préparant les étudiants ivoiriens au concours de l'INFAS.\n"
        "Tu dois impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
        "- 'question': La question posée sous forme de texte.\n"
        "- 'options': Un tableau contenant exactement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) représentant l'index de la bonne réponse.\n\n"
        "Génère une question sur la pharmacologie, l'éthique médicale, la santé publique, le secourisme de base ou l'anatomie.\n"
        "Renvoie uniquement le JSON brut, sans fioritures."
    )
    user_prompt = "Génère une question de quiz de niveau concours de santé."

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
    if chat_id not in GROUP_SESSIONS:
        return

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
    
    quiz_data = None
    
    # 1. On essaie d'abord de vider la banque de questions SVT locale
    questions_disponibles = [q for q in QUESTIONS_INFAS_SVT if q["question"] not in session["questions_utilisees"]]
    
    if questions_disponibles:
        quiz_data = random.choice(questions_disponibles)
        session["questions_utilisees"].append(quiz_data["question"])
        logger.info(f"Question locale sélectionnée pour le groupe {chat_id}")
    else:
        # 2. Une fois épuisée (après 10 questions), Groq prend automatiquement le relais
        logger.info("Banque locale épuisée ou indisponible, appel à Groq IA.")
        quiz_data = await generer_quiz_groq()

    # Nettoyage du message d'attente
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)
    except Exception:
        pass

    if not quiz_data:
        await context.bot.send_message(chat_id=chat_id, text="❌ Erreur de génération, passage à la question suivante.")
        await envoyer_question_groupe(context, chat_id)
        return

    session["correct_option_id"] = int(quiz_data["reponse_correcte"])

    # Envoi du Quiz Telegram natif fermé automatiquement après 25 secondes
    try:
        poll_msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=f"❓ [Q.{session['current_quiz_index']}] {quiz_data['question']}"[:300],
            options=[opt[:100] for opt in quiz_data["options"]],
            correct_option_id=session["correct_option_id"],
            type="quiz",
            is_anonymous=False,
            open_period=TEMPS_PAR_QUESTION
        )
    except Exception as e:
        logger.error(f"Erreur d'envoi du sondage : {e}")
        await envoyer_question_groupe(context, chat_id)
        return
    
    # Attente dynamique calée sur vos 25 secondes + 2s de transition réseau
    await asyncio.sleep(TEMPS_PAR_QUESTION + 2)
    await envoyer_question_groupe(context, chat_id)


async def recevoir_reponse_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enregistre les points des membres du groupe lorsqu'ils répondent correctement."""
    answer = update.poll_answer
    
    for chat_id, session in GROUP_SESSIONS.items():
        if "correct_option_id" in session:
            if answer.option_ids and answer.option_ids[0] == session["correct_option_id"]:
                user_id = answer.user.id
                user_name = answer.user.first_name
                
                if user_id not in session["scores"]:
                    session["scores"][user_id] = {"name": user_name, "points": 0}
                
                session["scores"][user_id]["points"] += 1
                break


async def start_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Démarre une session de quiz chronométrée pour le groupe."""
    chat_id = update.effective_chat.id
    
    # Initialisation de la session de ce groupe
    GROUP_SESSIONS[chat_id] = {
        "scores": {},
        "current_quiz_index": 0,
        "total_questions": NOMBRE_TOTAL_QUESTIONS,
        "questions_utilisees": []
    }
    
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🏁 *Lancement du Grand Marathon INFAS QUIZ !*\n\n"
                 f"• Total de questions : *{NOMBRE_TOTAL_QUESTIONS}*\n"
                 f"• Chronomètre : *{TEMPS_PAR_QUESTION} secondes* par question.\n\n"
                 "Bonne chance à tous les futurs agents de santé ! Préparez-vous...",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du message /quiz: {e}")
    
    # Lance la première question en arrière-plan
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def afficher_classement_final(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Calcule et affiche le tableau des scores à la fin du jeu."""
    session = GROUP_SESSIONS.get(chat_id)
    if not session:
        return

    texte_classement = "🏆 *FIN DU MARATHON - CLASSEMENT DES AGENTS DE SANTÉ* 🏆\n\n"
    
    if not session["scores"]:
        texte_classement += "😢 Aucun point n'a été marqué durant ce marathon."
    else:
        joueurs_tries = sorted(session["scores"].values(), key=lambda x: x["points"], reverse=True)
        
        medailles = ["🥇", "🥈", "🥉"]
        for i, joueur in enumerate(joueurs_tries):
            prefixe = medailles[i] if i < 3 else "🔹"
            texte_classement += f"{prefixe} *{joueur['name']}* : {joueur['points']}/{session['total_questions']} points\n"

    try:
        await context.bot.send_message(chat_id=chat_id, text=texte_classement, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erreur envoi classement : {e}")
        
    # Nettoyage de la mémoire
    GROUP_SESSIONS.pop(chat_id, None)


def main():
    if not TELEGRAM_TOKEN:
        logger.error("Le Token Telegram est manquant dans les variables d'environnement.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("quiz", start_quiz_command))
    application.add_handler(PollAnswerHandler(recevoir_reponse_quiz))

    logger.info("🤖 Bot INFAS QUIZ de Groupe configuré pour un marathon de 45 questions !")
    application.run_polling()


if __name__ == "__main__":
    main()
