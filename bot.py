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
NOMBRE_TOTAL_QUESTIONS = 50  
HISTORIQUE_FILE = "historique_questions.json"

# BANQUE DE QUESTIONS : 1ère ANNÉE SOINS OBSTÉRICAUX (INFAS)
# "temps": 45 pour les questions simples, 60 pour les cas pratiques/calculs
QUESTIONS_INFAS_SVT = [
    {
        "question": "[Anatomie] Quel diamètre du détroit supérieur (DS) mesure normalement 10,5 cm et constitue le diamètre utile ou chirurgical du bassin osseux ?",
        "options": ["Le diamètre conjugué anatomique", "Le diamètre promonto-rétro-pubien (PRP)", "Le diamètre diagonal", "Le diamètre transverse maximal"],
        "reponse_correcte": 1,
        "temps": 45
    },
    {
        "question": "[Anatomie] Quel muscle principal constitue le plancher pelvien postérieur (diaphragme pelvien) et soutient les organes génitaux ?",
        "options": ["Le muscle élévateur de l'anus (levator ani)", "Le muscle bulbo-spongieux", "Le muscle transverse profond", "Le muscle ischio-caverneux"],
        "reponse_correcte": 0,
        "temps": 45
    },
    {
        "question": "[Physiologie] Lors du cycle menstruel, quelle hormone hypophysaire est responsable du pic déclenchant l'ovulation vers le 14ème jour ?",
        "options": ["La Progestérone", "L'Oestradiol", "L'Hormone Lutéinisante (LH)", "L'Hormone Folliculo-Stimulante (FSH)"],
        "reponse_correcte": 2,
        "temps": 45
    },
    {
        "question": "[Physiologie] Où a lieu précisément la fécondation de l'ovocyte par le spermatozoïde dans l'appareil génital féminin ?",
        "options": ["Dans la cavité utérine", "Dans l'ampoule de la trompe de Fallope", "Au niveau de l'isthme utérin", "Dans le pavillon de la trompe"],
        "reponse_correcte": 1,
        "temps": 45
    },
    {
        "question": "[Obstétrique] À partir de quel repère anatomique précis mesure-t-on la hauteur utérine (HU) lors de l'examen clinique d'une femme enceinte ?",
        "options": ["L'ombilic", "L'appendice xiphoïde", "Le bord supérieur de la symphyse pubienne", "L'épine iliaque antéro-supérieure"],
        "reponse_correcte": 2,
        "temps": 45
    },
    {
        "question": "[Obstétrique] À combien de semaines d'aménorrhée (SA) correspond le terme théorique d'une grossesse normale en Côte d'Ivoire ?",
        "options": ["37 SA", "39 SA", "41 SA", "45 SA"],
        "reponse_correcte": 2,
        "temps": 45
    },
    {
        "question": "[Obstétrique] Quelle hormone, sécrétée par le syncytiotrophoblaste, maintient le corps jaune au début de la grossesse et sert de base aux tests de grossesse ?",
        "options": ["L'hCG (Hormone Chorionique Gonadotrope)", "L'hPL (Hormone Lactogène Placentaire)", "La Progestérone", "L'Oestriol"],
        "reponse_correcte": 0,
        "temps": 45
    },
    {
        "question": "[Calcul de Doses] Cas pratique : Perfuser 5 UI d'Oxytocine (Syntocinon) dans 500 ml de Sérum Glucosé 5% en 4 heures. Quel est le débit de la perfusion en gouttes/minute ?",
        "options": ["21 gouttes/min", "31 gouttes/min", "42 gouttes/min", "50 gouttes/min"],
        "reponse_correcte": 2,
        "temps": 60
    },
    {
        "question": "[Calcul de Doses] Vous disposez d'une ampoule de Gluconate de Calcium à 10% de 10 ml. Combien de grammes de principe actif contient cette ampoule ?",
        "options": ["0,1 g", "1 g", "10 g", "0,01 g"],
        "reponse_correcte": 1,
        "temps": 60
    },
    {
        "question": "[Santé de la Reproduction] Selon les directives nationales, quel est l'intervalle minimum recommandé entre deux grossesses consécutives pour réduire les risques maternels ?",
        "options": ["6 mois", "12 mois", "24 mois (2 ans)", "36 mois"],
        "reponse_correcte": 2,
        "temps": 45
    },
    {
        "question": "[Santé de la Reproduction] Quel outil de surveillance clinique permet de consigner les données de l'accouchement pour prévenir le travail prolongé ?",
        "options": ["Le carnet de santé", "Le partogramme", "La fiche de CPN", "Le dossier infirmer"],
        "reponse_correcte": 1,
        "temps": 45
    }
]

# FONCTIONS DE GESTION DE L'HISTORIQUE GLOBAL
def charger_historique_global() -> list:
    """Charge la liste des questions déjà posées historiquement."""
    if os.path.exists(HISTORIQUE_FILE):
        try:
            with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'historique : {e}")
    return []

def sauvegarder_dans_historique_global(question_texte: str):
    """Ajoute de façon permanente une question à l'historique."""
    historique = charger_historique_global()
    if question_texte not in historique:
        historique.append(question_texte)
        try:
            with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
                json.dump(historique, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique : {e}")


async def generer_quiz_groq(questions_exclues: list) -> dict:
    """Appelle l'API de Groq pour générer un QCM inédit à 45s ou 60s."""
    if not groq_client:
        logger.error("Client Groq non initialisé.")
        return None
        
    exclues_str = "\n".join([f"- {q}" for q in questions_exclues[-20:]]) # Lui donner les dernières questions pour l'orienter
        
    system_prompt = (
        "Tu es un formateur expert à l'INFAS, spécialisé dans la filière Soins Obstétricaux (Sages-femmes / Maïeuticiens).\n"
        "Tu prépares une évaluation pour les étudiants de Première Année.\n\n"
        "Tu dois impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
        "- 'question': La question posée sous forme de texte.\n"
        "- 'options': Un tableau contenant exactement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) représentant l'index de la bonne réponse.\n"
        "- 'temps': Un entier valant obligatoirement SOIT 45 (pour les questions de cours directes), SOIT 60 (pour les calculs de doses ou cas cliniques complexes).\n\n"
        "Modules cibles : Anatomie du bassin osseux, physiologie du cycle menstruel, sémiologie de la grossesse normale, calculs de doses (perfusions oxytociques, dilutions), Santé de la Reproduction.\n\n"
        "CRUCIAL : Ne génère PAS une question proche ou identique à celles-ci :\n"
        f"{exclues_str}\n\n"
        "Utilise l'un de ces préfixes : [Anatomie], [Physiologie], [Sémiologie Obstétricale], [Calcul de Doses] ou [Santé de la Reproduction].\n"
        "Renvoie uniquement le JSON brut, sans introduction ni conclusion."
    )
    user_prompt = "Génère une question de niveau 1ère année Soins Obstétricaux INFAS. Choisis librement entre une question simple (45s) ou un cas pratique complexe (60s)."

    try:
        completion = groq_client.chat.completions.create(
            model=GROK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.85 # Température légèrement augmentée pour favoriser la nouveauté
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Erreur lors de la génération IA Groq : {e}")
        return None


async def envoyer_question_groupe(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Sélectionne ou génère une question non répétée et adapte le chrono."""
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
    
    historique_global = charger_historique_global()
    quiz_data = None
    
    # Filtrer les questions locales qui n'ont JAMAIS été posées (séance actuelle ET anciennes séances)
    questions_disponibles = [q for q in QUESTIONS_INFAS_SVT if q["question"] not in historique_global]
    
    if questions_disponibles and random.random() > 0.40:  
        quiz_data = random.choice(questions_disponibles)
        sauvegarder_dans_historique_global(quiz_data["question"])
        logger.info(f"Question locale inédite sélectionnée pour le groupe {chat_id}")
    else:
        logger.info("Génération d'une question inédite via Groq IA.")
        # On passe l'historique à l'IA pour qu'elle n'invente pas un doublon
        quiz_data = await generer_quiz_groq(historique_global)
        if quiz_data:
            # Vérification de sécurité si l'IA génère malgré tout un doublon historique
            if quiz_data["question"] in historique_global:
                logger.warning("L'IA a généré une question déjà existante. Tentative de repli.")
                quiz_data = None
            else:
                sauvegarder_dans_historique_global(quiz_data["question"])

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)
    except Exception:
        pass

    # Système de secours si l'IA échoue ou donne un doublon
    if not quiz_data:
        if questions_disponibles:
            quiz_data = random.choice(questions_disponibles)
            sauvegarder_dans_historique_global(quiz_data["question"])
        else:
            # Si TOUTES les questions locales ont été épuisées à travers le temps
            await context.bot.send_message(
                chat_id=chat_id, 
                text="⚠️ La banque de questions locale est saturée d'anciens sujets. Génération forcée d'une nouvelle situation clinique..."
            )
            # Retentative unique avec l'IA
            quiz_data = await generer_quiz_groq(historique_global)
            if not quiz_data:
                # Secours ultime (on pioche n'importe où pour ne pas bloquer le bot)
                quiz_data = random.choice(QUESTIONS_INFAS_SVT)
                
    # Récupération et application du temps dynamique (45 ou 60 secondes)
    temps_allocation = int(quiz_data.get("temps", 45))
    session["correct_option_id"] = int(quiz_data["reponse_correcte"])

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"🤰 [Q.{session['current_quiz_index']}/{session['total_questions']}] ({temps_allocation}s) {quiz_data['question']}"[:300],
            options=[opt[:100] for opt in quiz_data["options"]],
            correct_option_id=session["correct_option_id"],
            type="quiz",
            is_anonymous=False,
            open_period=temps_allocation
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du QCM : {e}")
        if chat_id in GROUP_SESSIONS:
            asyncio.create_task(envoyer_question_groupe(context, chat_id))
        return
    
    # Attente calée dynamiquement sur le temps de la question
    for _ in range(temps_allocation + 2):
        await asyncio.sleep(1)
        if chat_id not in GROUP_SESSIONS:  
            return
        if session["status"] == "paused":  
            return

    if chat_id in GROUP_SESSIONS and session["status"] == "running":
        asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def recevoir_reponse_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enregistre les points des étudiants en direct."""
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
    """Lance le grand contrôle continu sans répétition."""
    chat_id = update.effective_chat.id
    
    if chat_id in GROUP_SESSIONS:
        await update.message.reply_text("⚠️ Un contrôle de révision obstétricale est déjà actif. Utilise /pause ou /stop.")
        return

    GROUP_SESSIONS[chat_id] = {
        "scores": {},
        "current_quiz_index": 0,
        "total_questions": NOMBRE_TOTAL_QUESTIONS,
        "status": "running"
    }
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"👶 *INFAS 1ère Année — Filière Soins Obstétricaux* 👶\n"
             f"✨ *Grand Marathon d'Évaluation Sans Répétition* ✨\n\n"
             f"Chaque épreuve s'adapte à votre niveau. Les questions déjà résolues lors des séances passées ne reviendront pas.\n\n"
             f"• Volume de l'épreuve : *{NOMBRE_TOTAL_QUESTIONS} Questions*\n"
             f"• Temps de réflexion : *45s (Théorie) ou 60s (Cas Pratiques/Calculs)*\n\n"
             "⚡ _Futures Sages-femmes et Maïeuticiens, préparez vos blocs-notes ! Début de l'épreuve..._\n\n"
             "🛠️ Commandes : /pause | /resume | /stop",
        parse_mode="Markdown"
    )
    
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def pause_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Met en pause la session."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucune épreuve en cours.")
        return
        
    session = GROUP_SESSIONS[chat_id]
    if session["status"] == "paused":
        await update.message.reply_text("⏸️ L'évaluation est déjà suspendue.")
        return
        
    session["status"] = "paused"
    await update.message.reply_text("⏸️ *Évaluation suspendue.* Utilisez /resume pour relancer les questions.")


async def resume_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reprend la session suspendue."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucune épreuve à reprendre.")
        return
        
    session = GROUP_SESSIONS[chat_id]
    if session["status"] == "running":
        await update.message.reply_text("▶️ L'épreuve est déjà en cours.")
        return
        
    session["status"] = "running"
    await update.message.reply_text("▶️ *Reprise du contrôle continu !* Chargement du cas suivant...")
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def stop_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interrompt définitivement l'évaluation."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Pas de session active à stopper.")
        return
        
    await update.message.reply_text("🛑 *Fin prématurée de l'épreuve.* Tri et correction des copies...")
    await afficher_classement_final(context, chat_id)


async def afficher_classement_final(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Proclame le tableau d'honneur de la promotion."""
    session = GROUP_SESSIONS.get(chat_id)
    if not session:
        return

    texte_classement = "🏆 *PROCLAMATION DES RÉSULTATS — SOINS OBSTÉRICAUX* 🏆\n\n"
    
    if not session["scores"]:
        texte_classement += "❌ Aucun étudiant n'a validé de point sur cette session."
    else:
        joueurs_tries = sorted(session["scores"].values(), key=lambda x: x["points"], reverse=True)
        medailles = ["🥇", "🥈", "🥉"]
        for i, joueur in enumerate(joueurs_tries):
            prefixe = medailles[i] if i < 3 else "🔹"
            texte_classement += f"{prefixe} *{joueur['name']}* : {joueur['points']}/{session['current_quiz_index']} validés\n"

    try:
        await context.bot.send_message(chat_id=chat_id, text=texte_classement, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erreur d'affichage du classement : {e}")
        
    GROUP_SESSIONS.pop(chat_id, None)


def main():
    if not TELEGRAM_TOKEN:
        logger.error("Le Token de votre bot Telegram n'a pas été trouvé.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("quiz", start_quiz_command))
    application.add_handler(CommandHandler("pause", pause_quiz_command))
    application.add_handler(CommandHandler("resume", resume_quiz_command))
    application.add_handler(CommandHandler("stop", stop_quiz_command))
    
    application.add_handler(PollAnswerHandler(recevoir_reponse_quiz))

    logger.info("🤖 Bot INFAS Mémoire & Temps Réactif initialisé avec succès !")
    application.run_polling()


if __name__ == "__main__":
    main()
