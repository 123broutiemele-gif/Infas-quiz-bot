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
TEMPS_PAR_QUESTION = 60   # ← Modifié à 60 secondes comme demandé par Rita
NOMBRE_TOTAL_QUESTIONS = 50  

# BANQUE DE QUESTIONS (inchangée)
QUESTIONS_INFAS_SVT = [
    # --- ANATOMIE & PHYSIOLOGIE DU BASSIN ET DE L'APPAREIL GÉNITAL ---
    {
        "question": "[Anatomie] Quel diamètre du détroit supérieur (DS) mesure normalement 10,5 cm et constitue le diamètre utile ou chirurgical du bassin osseux ?",
        "options": ["Le diamètre conjugué anatomique", "Le diamètre promonto-rétro-pubien (PRP)", "Le diamètre diagonal", "Le diamètre transverse maximal"],
        "reponse_correcte": 1
    },
    {
        "question": "[Anatomie] Quel muscle principal constitue le plancher pelvien postérieur (diaphragme pelvien) et soutient les organes génitaux ?",
        "options": ["Le muscle élévateur de l'anus (levator ani)", "Le muscle bulbo-spongieux", "Le muscle transverse profond", "Le muscle ischio-caverneux"],
        "reponse_correcte": 0
    },
    {
        "question": "[Physiologie] Lors du cycle menstruel, quelle hormone hypophysaire est responsable du pic déclenchant l'ovulation vers le 14ème jour ?",
        "options": ["La Progestérone", "L'Oestradiol", "L'Hormone Lutéinisante (LH)", "L'Hormone Folliculo-Stimulante (FSH)"],
        "reponse_correcte": 2
    },
    {
        "question": "[Physiologie] Où a lieu précisément la fécondation de l'ovocyte par le spermatozoïde dans l'appareil génital féminin ?",
        "options": ["Dans la cavité utérine", "Dans l'ampoule de la trompe de Fallope", "Au niveau de l'isthme utérin", "Dans le pavillon de la trompe"],
        "reponse_correcte": 1
    },
    
    # --- OBSTÉTRIQUE ET SÉMIOLOGIE DE LA GROSSESSE NORMALE ---
    {
        "question": "[Obstétrique] À partir de quel repère anatomique précis mesure-t-on la hauteur utérine (HU) lors de l'examen clinique d'une femme enceinte ?",
        "options": ["L'ombilic", "L'appendice xiphoïde", "Le bord supérieur de la symphyse pubienne", "L'épine iliaque antéro-supérieure"],
        "reponse_correcte": 2
    },
    {
        "question": "[Obstétrique] À combien de semaines d'aménorrhée (SA) correspond le terme théorique d'une grossesse normale en Côte d'Ivoire ?",
        "options": ["37 SA", "39 SA", "41 SA", "45 SA"],
        "reponse_correcte": 2
    },
    {
        "question": "[Obstétrique] Quelle hormone, sécrétée par le syncytiotrophoblaste, maintient le corps jaune au début de la grossesse et sert de base aux tests de grossesse ?",
        "options": ["L'hCG (Hormone Chorionique Gonadotrope)", "L'hPL (Hormone Lactogène Placentaire)", "La Progestérone", "L'Oestriol"],
        "reponse_correcte": 0
    },
    
    # --- CALCULS DE DOSES & PHARMACOLOGIE OBSTÉRICALE ---
    {
        "question": "[Calculs] Prescription : Perfuser 5 UI d'Oxytocine (Syntocinon) dans 500 ml de Sérum Glucosé 5% en 4 heures. Quel est le débit de la perfusion en gouttes/minute ?",
        "options": ["21 gouttes/min", "31 gouttes/min", "42 gouttes/min", "50 gouttes/min"],
        "reponse_correcte": 2
    },
    {
        "question": "[Calculs] Vous disposez d'une ampoule de Gluconate de Calcium à 10% de 10 ml. Combien de grammes de principe actif contient cette ampoule ?",
        "options": ["0,1 g", "1 g", "10 g", "0,01 g"],
        "reponse_correcte": 1
    },
    
    # --- SANTÉ DE LA REPRODUCTION (SR) ---
    {
        "question": "[Santé de la Reproduction] Selon les directives nationales, quel est l'intervalle minimum recommandé entre deux grossesses consécutives pour réduire les risques maternels ?",
        "options": ["6 mois", "12 mois", "24 mois (2 ans)", "36 mois"],
        "reponse_correcte": 2
    },
    {
        "question": "[SR] Quel outil de surveillance clinique permet de consigner les données de l'accouchement pour prévenir le travail prolongé ?",
        "options": ["Le carnet de santé", "Le partogramme", "La fiche de CPN", "Le dossier infirmer"],
        "reponse_correcte": 1
    }
]


async def generer_quiz_groq() -> dict:
    """Appelle l'API de Groq pour générer un QCM"""
    if not groq_client:
        logger.error("Client Groq non initialisé.")
        return None
        
    system_prompt = (
        "Tu es un formateur expert à l'INFAS, spécialisé dans la filière Soins Obstétricaux...\n"
        # (Le reste du prompt reste identique)
        "Renvoie uniquement le JSON brut, sans introduction ni conclusion."
    )
    user_prompt = "Génère une question difficile de niveau 1ère année Soins Obstétricaux INFAS Côte d'Ivoire."

    try:
        completion = groq_client.chat.completions.create(
            model=GROK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.70
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Erreur lors de la génération IA Groq : {e}")
        return None


async def envoyer_question_groupe(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Envoie une question"""
    if chat_id not in GROUP_SESSIONS:
        return

    session = GROUP_SESSIONS[chat_id]

    if session["status"] == "paused":
        return

    session["current_quiz_index"] += 1
    
    if session["current_quiz_index"] > session["total_questions"]:
        await afficher_classement_final(context, chat_id)
        return

    msg_attente = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"📖 *Analyse du dossier clinique (Question {session['current_quiz_index']}/{session['total_questions']})...*",
        parse_mode="Markdown"
    )
    
    quiz_data = None
    questions_disponibles = [q for q in QUESTIONS_INFAS_SVT if q["question"] not in session["questions_utilisees"]]
    
    if questions_disponibles and random.random() > 0.30:  
        quiz_data = random.choice(questions_disponibles)
        session["questions_utilisees"].append(quiz_data["question"])
    else:
        quiz_data = await generer_quiz_groq()
        if quiz_data:
            session["questions_utilisees"].append(quiz_data["question"])

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)
    except Exception:
        pass

    if not quiz_data:
        if questions_disponibles:
            quiz_data = random.choice(questions_disponibles)
            session["questions_utilisees"].append(quiz_data["question"])
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Erreur, passage à la question suivante...")
            await asyncio.sleep(2)
            if chat_id in GROUP_SESSIONS:
                asyncio.create_task(envoyer_question_groupe(context, chat_id))
            return

    session["correct_option_id"] = int(quiz_data["reponse_correcte"])

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"🤰 [Q.{session['current_quiz_index']}/{session['total_questions']}] {quiz_data['question']}"[:300],
            options=[opt[:100] for opt in quiz_data["options"]],
            correct_option_id=session["correct_option_id"],
            type="quiz",
            is_anonymous=False,
            open_period=TEMPS_PAR_QUESTION
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du QCM : {e}")
        if chat_id in GROUP_SESSIONS:
            asyncio.create_task(envoyer_question_groupe(context, chat_id))
        return
    
    # Surveillance
    for _ in range(TEMPS_PAR_QUESTION + 5):  # +5 pour plus de marge
        await asyncio.sleep(1)
        if chat_id not in GROUP_SESSIONS or GROUP_SESSIONS[chat_id]["status"] == "paused":
            return

    if chat_id in GROUP_SESSIONS and GROUP_SESSIONS[chat_id]["status"] == "running":
        asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change le temps par question dynamiquement"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text(
            f"⏱️ **Temps actuel** : {TEMPS_PAR_QUESTION} secondes par question.\n\n"
            "Utilisation : `/temps 60`"
        )
        return

    try:
        nouveau_temps = int(context.args[0])
        if nouveau_temps < 30 or nouveau_temps > 180:
            await update.message.reply_text("❌ Le temps doit être entre **30** et **180** secondes.")
            return
            
        global TEMPS_PAR_QUESTION
        ancien_temps = TEMPS_PAR_QUESTION
        TEMPS_PAR_QUESTION = nouveau_temps
        
        await update.message.reply_text(
            f"✅ Temps par question mis à jour :\n"
            f"**{ancien_temps}s → {nouveau_temps}s**"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Utilisation : `/temps 60` (nombre uniquement)")


# ====================== AUTRES FONCTIONS (inchangées) ======================

async def recevoir_reponse_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    for chat_id, session in GROUP_SESSIONS.items():
        if session["status"] == "running" and "correct_option_id" in session:
            if answer.option_ids and answer.option_ids[0] == session["correct_option_id"]:
                user_id = answer.user.id
                user_name = answer.user.first_name
                if user_id not in session["scores"]:
                    session["scores"][user_id] = {"name": user_name, "points": 0}
                session["scores"][user_id]["points"] += 1
                break


async def start_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id in GROUP_SESSIONS:
        await update.message.reply_text("⚠️ Un quiz est déjà actif.")
        return

    GROUP_SESSIONS[chat_id] = {
        "scores": {},
        "current_quiz_index": 0,
        "total_questions": NOMBRE_TOTAL_QUESTIONS,
        "questions_utilisees": [],
        "status": "running"
    }
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"👶 *INFAS 1ère Année — Soins Obstétricaux* 👶\n"
             f"✨ *Grand Marathon d'Évaluation* ✨\n\n"
             f"• {NOMBRE_TOTAL_QUESTIONS} questions\n"
             f"• ⏱️ *{TEMPS_PAR_QUESTION} secondes* par question\n\n"
             "Bon courage à toutes et à tous !\n\n"
             "Commandes : /pause | /resume | /stop | /temps",
        parse_mode="Markdown"
    )
    
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def pause_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucune session active.")
        return
    GROUP_SESSIONS[chat_id]["status"] = "paused"
    await update.message.reply_text("⏸️ Évaluation mise en pause.")


async def resume_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucune session à reprendre.")
        return
    GROUP_SESSIONS[chat_id]["status"] = "running"
    await update.message.reply_text("▶️ Reprise de l'évaluation...")
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def stop_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucune session active.")
        return
    await update.message.reply_text("🛑 Fin de l'épreuve.")
    await afficher_classement_final(context, chat_id)


async def afficher_classement_final(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    session = GROUP_SESSIONS.get(chat_id)
    if not session:
        return

    texte_classement = "🏆 *PROCLAMATION DES RÉSULTATS* 🏆\n\n"
    
    if not session["scores"]:
        texte_classement += "Aucun point enregistré."
    else:
        joueurs_tries = sorted(session["scores"].values(), key=lambda x: x["points"], reverse=True)
        medailles = ["🥇", "🥈", "🥉"]
        for i, joueur in enumerate(joueurs_tries):
            prefixe = medailles[i] if i < 3 else "🔹"
            texte_classement += f"{prefixe} *{joueur['name']}* : {joueur['points']}/{session['current_quiz_index']}\n"

    await context.bot.send_message(chat_id=chat_id, text=texte_classement, parse_mode="Markdown")
    GROUP_SESSIONS.pop(chat_id, None)


def main():
    if not TELEGRAM_TOKEN:
        logger.error("Token Telegram non trouvé.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("quiz", start_quiz_command))
    application.add_handler(CommandHandler("pause", pause_quiz_command))
    application.add_handler(CommandHandler("resume", resume_quiz_command))
    application.add_handler(CommandHandler("stop", stop_quiz_command))
    application.add_handler(CommandHandler("temps", set_time_command))   # ← Nouvelle commande
    
    application.add_handler(PollAnswerHandler(recevoir_reponse_quiz))

    logger.info("🤖 Bot INFAS Soins Obstétricaux démarré avec succès !")
    application.run_polling()


if __name__ == "__main__":
    main()
