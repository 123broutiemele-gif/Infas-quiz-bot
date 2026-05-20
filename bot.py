import os
import json
import logging
import asyncio
import random
import re
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
NOMBRE_TOTAL_QUESTIONS = 25  # Configuration à 25 questions demandée
HISTORIQUE_FILE = "historique_annales_2010_2025.json"

# BANQUE DE DONNÉES HISTORIQUES (Annales INFAS 2010 à 2025)
QUESTIONS_ANNALES_INFAS = [
    {
        "question": "[Annale SVT] Quelle est l'unité structurelle et fonctionnelle du rein responsable de la filtration du sang et de la formation de l'urine ?",
        "options": ["Le neurone", "Le néphron", "L'alvéole", "L'hépatocyte"],
        "reponse_correcte": 1
    },
    {
        "question": "[Annale SVT] Lors de la réplication de l'ADN, quelle base azotée s'apparie de façon complémentaire et spécifique avec l'Adénine ?",
        "options": ["La Cytosine", "La Guanine", "La Thymine", "L'Uracile"],
        "reponse_correcte": 2
    },
    {
        "question": "[Annale SVT] Quelle glande endocrine, située à la base du cerveau, est qualifiée de 'glande maîtresse' car elle régule la majorité des autres glandes de l'organisme ?",
        "options": ["L'hypophyse", "La thyroïde", "La surrénale", "Le pancréas"],
        "reponse_correcte": 0
    },
    {
        "question": "[Annale SVT] Comment appelle-t-on les vaisseaux sanguins qui ramènent le sang désoxygéné des organes vers l'oreillette droite du cœur ?",
        "options": ["Les artères pulmonaires", "Les veines caves", "L'artère aorte", "Les veines pulmonaires"],
        "reponse_correcte": 1
    },
    {
        "question": "[Annale Culture] Quel médecin et chercheur a mis au point le tout premier vaccin efficace contre la rage en 1885 ?",
        "options": ["Robert Koch", "Louis Pasteur", "Alexander Fleming", "Edward Jenner"],
        "reponse_correcte": 1
    },
    {
        "question": "[Annale Santé Publique] En Côte d'Ivoire, quel programme national coordonne la lutte, la prévention et la distribution gratuite des moustiquaires imprégnées contre le paludisme ?",
        "options": ["PNLS", "PNLP (Programme National de Lutte contre le Paludisme)", "PNLT", "PNDS"],
        "reponse_correcte": 1
    },
    {
        "question": "[Annale Calculs] Un flacon contient 500 mg d'hydrocortisone sous forme de poudre. Vous devez injecter 100 mg. Après dilution de la poudre dans 5 ml d'eau PPI, quel volume devez-vous prélever ?",
        "options": ["0,5 ml", "1 ml", "2 ml", "2,5 ml"],
        "reponse_correcte": 1  # (100 * 5) / 500 = 1 ml
    },
    {
        "question": "[Annale Logique] Complétez la suite logique numérique utilisée dans les tests psychotechniques du concours : 3, 6, 12, 24, ... ?",
        "options": ["30", "36", "48", "60"],
        "reponse_correcte": 2  # Progression x2
    },
    {
        "question": "[Annale SVT] Quel organite cellulaire contient les enzymes lytiques capables de digérer et de recycler les déchets de la cellule ?",
        "options": ["Le ribosome", "Le lysosome", "Le chloroplaste", "Le centrosome"],
        "reponse_correcte": 1
    },
    {
        "question": "[Annale Santé Publique] Quelle maladie infectieuse d'origine bactérienne, caractérisée par une toux persistante et transmise par les voies aériennes, est prévenue par le vaccin BCG ?",
        "options": ["La diphtérie", "La tuberculose", "La coqueluche", "La méningite"],
        "reponse_correcte": 1
    }
]

# FONCTIONS DE GESTION DE L'HISTORIQUE GLOBAL
def charger_historique_global() -> list:
    """Charge l'historique permanent des questions déjà consommées."""
    if os.path.exists(HISTORIQUE_FILE):
        try:
            with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'historique : {e}")
    return []

def sauvegarder_dans_historique_global(question_texte: str):
    """Mémorise définitivement une question pour qu'elle ne revienne jamais."""
    historique = charger_historique_global()
    if question_texte not in historique:
        historique.append(question_texte)
        try:
            with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
                json.dump(historique, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique : {e}")

# ALGORITHME DE DÉTERMINATION DU TEMPS (VOLUME ET COMPLEXITÉ)
def determiner_temps_question(quiz_data: dict) -> int:
    """Analyse l'énoncé de la question pour fixer dynamiquement le chrono (45s ou 60s)."""
    question_text = quiz_data.get("question", "").lower()
    
    # Critère 1 : Longueur du texte (Volume important)
    if len(question_text) > 160:
        return 60
        
    # Critère 2 : Indicateurs de calculs mathématiques ou dosages (Complexité de réflexion)
    # Recherche de chiffres suivis d'unités (mg, ml, g, UI, gouttes, heures, min ou opérations)
    mot_cles_calculs = [
        r"\d+\s*(mg|ml|g|ui|gouttes|l|gtts)", 
        r"débit", r"calculez", r"diluer", r"perfusion", 
        r"égal à", r"suite logique", r"proportion"
    ]
    
    for pattern in mot_cles_calculs:
        if re.search(pattern, question_text):
            return 60  # Nécessite un brouillon -> 60 secondes
            
    return 45  # Question de cours ou de culture pure -> 45 secondes

# GÉNÉRATEUR IA ALIGNÉ SUR LES SUJETS HISTORIQUES 2010-2025
async def generer_quiz_groq(questions_exclues: list) -> dict:
    """Génère des sujets conformes aux sessions d'examen INFAS 2010 à 2025."""
    if not groq_client:
        logger.error("Client Groq non initialisé.")
        return None
        
    exclues_str = "\n".join([f"- {q}" for q in questions_exclues[-20:]])

    system_prompt = (
        "Tu es un concepteur de sujets officiel pour le concours d'entrée à l'INFAS en Côte d'Ivoire.\n"
        "Tu dois formuler une question calquée rigoureusement sur le style des épreuves des sessions 2010 à 2025.\n"
        "REMARQUE DE LANGUE : Écris en français académique. N'emploie aucun mot technique en anglais.\n\n"
        "Format de retour attendu : Un objet JSON contenant strictement ces trois clés :\n"
        "- 'question': La question posée sous forme de texte.\n"
        "- 'options': Un tableau contenant exactement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) désignant l'index de la bonne réponse.\n\n"
        "Thématiques autorisées :\n"
        "1. SVT / Biologie Humaine (Anatomie, physiologie, génétique, immunologie, reproduction).\n"
        "2. Culture Générale et Sanitaire Ivoirienne (Sigles sanitaires, dates clés de santé publique, épidémiologie, institutions).\n"
        "3. Tests psychotechniques et calculs de conversion (Règles de trois, débits de fluides, logique numérique).\n\n"
        "RÈGLE STRICTE : Ne propose pas une question identique ou très similaire à la liste suivante :\n"
        f"{exclues_str}\n\n"
        "Ajoute obligatoirement l'un de ces marqueurs au début de la question : [Annale SVT], [Annale Culture] ou [Annale Calculs]."
    )
    user_prompt = "Produis un sujet d'examen type concours INFAS (Période historique 2010-2025) au format JSON."

    try:
        completion = groq_client.chat.completions.create(
            model=GROK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.82
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Erreur lors de la génération IA Groq : {e}")
        return None


async def envoyer_question_groupe(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Sélectionne, calcule le temps requis et diffuse la question sans doublon."""
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
        text=f"📂 *Recherche dans les archives des sessions 2010-2025 (Question {session['current_quiz_index']}/{session['total_questions']})...*",
        parse_mode="Markdown"
    )
    
    historique_global = charger_historique_global()
    quiz_data = None
    
    # Identification des questions locales jamais posées
    questions_disponibles = [q for q in QUESTIONS_ANNALES_INFAS if q["question"] not in historique_global]
    
    if questions_disponibles and random.random() > 0.45:  
        quiz_data = random.choice(questions_disponibles)
        sauvegarder_dans_historique_global(quiz_data["question"])
        logger.info(f"Sujet d'archive fixe extrait pour le groupe {chat_id}")
    else:
        logger.info("Simulation d'une question d'archive 2010-2025 via Groq.")
        quiz_data = await generer_quiz_groq(historique_global)
        if quiz_data:
            if quiz_data["question"] in historique_global:
                logger.warning("Redondance détectée par l'IA. Tentative d'annulation.")
                quiz_data = None
            else:
                sauvegarder_dans_historique_global(quiz_data["question"])

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)
    except Exception:
        pass

    # Gestion de secours en cas d'épuisement total ou d'erreur réseau
    if not quiz_data:
        if questions_disponibles:
            quiz_data = random.choice(questions_disponibles)
            sauvegarder_dans_historique_global(quiz_data["question"])
        else:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="⚠️ Attention : La banque d'annales fixes a été entièrement résolue par le groupe. Génération alternative active..."
            )
            quiz_data = await generer_quiz_groq(historique_global)
            if not quiz_data:
                quiz_data = random.choice(QUESTIONS_ANNALES_INFAS)
                
    # ÉVALUATION AUTOMATIQUE DU TEMPS (45s ou 60s selon le volume/complexité)
    temps_allocation = determiner_temps_question(quiz_data)
    session["correct_option_id"] = int(quiz_data["reponse_correcte"])

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"📝 [Q.{session['current_quiz_index']}/{session['total_questions']}] ({temps_allocation}s) {quiz_data['question']}"[:300],
            options=[opt[:100] for opt in quiz_data["options"]],
            correct_option_id=session["correct_option_id"],
            type="quiz",
            is_anonymous=False,
            open_period=temps_allocation
        )
    except Exception as e:
        logger.error(f"Erreur d'envoi du sondage Telegram : {e}")
        if chat_id in GROUP_SESSIONS:
            asyncio.create_task(envoyer_question_groupe(context, chat_id))
        return
    
    # Attente calée sur la décision de l'algorithme de temps
    for _ in range(temps_allocation + 2):
        await asyncio.sleep(1)
        if chat_id not in GROUP_SESSIONS:  
            return
        if session["status"] == "paused":  
            return

    if chat_id in GROUP_SESSIONS and session["status"] == "running":
        asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def recevoir_reponse_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cumule les scores des étudiants réactifs."""
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
    """Initialise un module de 25 questions uniques."""
    chat_id = update.effective_chat.id
    
    if chat_id in GROUP_SESSIONS:
        await update.message.reply_text("⚠️ Un examen blanc basé sur les annales est déjà en cours. Commandes : /pause ou /stop.")
        return

    GROUP_SESSIONS[chat_id] = {
        "scores": {},
        "current_quiz_index": 0,
        "total_questions": NOMBRE_TOTAL_QUESTIONS,
        "status": "running"
    }
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🏢 *CONCOURS ACCÈS INFAS — SESSIONS 2010 À 2025* 🏢\n"
             f"🏁 *Lancement d'une Épreuve Blanche Officielle* 🏁\n\n"
             f"Toutes les questions passées sont mémorisées et ne se répéteront pas d'une séance à l'autre tant que la réserve n'est pas épuisée.\n\n"
             f"• Longueur du sujet : *{NOMBRE_TOTAL_QUESTIONS} Questions de Concours*\n"
             f"• Gestion du chrono : *Automatique (45s théorique / 60s calculs & logique)*\n\n"
             "💡 _Concentration maximale requise. Début de la distribution des copies..._\n\n"
             "🧰 Commandes d'administration : /pause | /resume | /stop",
        parse_mode="Markdown"
    )
    
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def pause_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suspend temporairement l'exercice."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucune épreuve en cours.")
        return
        
    session = GROUP_SESSIONS[chat_id]
    if session["status"] == "paused":
        await update.message.reply_text("⏸️ L'épreuve est déjà suspendue.")
        return
        
    session["status"] = "paused"
    await update.message.reply_text("⏸️ *Chrono arrêté.* Utilisez /resume pour relancer le flux des questions.")


async def resume_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Relance l'épreuve suspendue."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucun flux suspendu.")
        return
        
    session = GROUP_SESSIONS[chat_id]
    if session["status"] == "running":
        await update.message.reply_text("▶️ L'épreuve est déjà active.")
        return
        
    session["status"] = "running"
    await update.message.reply_text("▶️ *Reprise de l'épreuve blanche !* Analyse de la question suivante...")
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def stop_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Arrête la session et comptabilise immédiatement les copies."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Pas de session active à clôturer.")
        return
        
    await update.message.reply_text("🛑 *Interruption de l'épreuve.* Centralisation des fiches de réponses...")
    await afficher_classement_final(context, chat_id)


async def afficher_classement_final(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Génère le récapitulatif des admissions de la session."""
    session = GROUP_SESSIONS.get(chat_id)
    if not session:
        return

    texte_classement = "📊 *RÉSULTATS DE L'ÉPREUVE BLANCHE (ANNALES 2010-2025)* 📊\n\n"
    
    if not session["scores"]:
        texte_classement += "❌ Aucun candidat n'a réuni de points sur cette série."
    else:
        joueurs_tries = sorted(session["scores"].values(), key=lambda x: x["points"], reverse=True)
        medailles = ["🥇", "🥈", "🥉"]
        for i, joueur in enumerate(joueurs_tries):
            prefixe = medailles[i] if i < 3 else "👉"
            texte_classement += f"{prefixe} *{joueur['name']}* : {joueur['points']}/{session['current_quiz_index']} bonnes réponses\n"

    try:
        await context.bot.send_message(chat_id=chat_id, text=texte_classement, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erreur d'affichage des scores : {e}")
        
    GROUP_SESSIONS.pop(chat_id, None)


def main():
    if not TELEGRAM_TOKEN:
        logger.error("Le Token d'authentification Telegram est introuvable.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("quiz", start_quiz_command))
    application.add_handler(CommandHandler("pause", pause_quiz_command))
    application.add_handler(CommandHandler("resume", resume_quiz_command))
    application.add_handler(CommandHandler("stop", stop_quiz_command))
    
    application.add_handler(PollAnswerHandler(recevoir_reponse_quiz))

    logger.info("🤖 Bot INFAS Examen Blanc (2010-2025) démarré avec succès !")
    application.run_polling()


if __name__ == "__main__":
    main()
