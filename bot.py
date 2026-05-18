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
TEMPS_PAR_QUESTION = 45  
NOMBRE_TOTAL_QUESTIONS = 50  

# BANQUE D'ANNALES INFAS & REPERTOIRE FOMESOUTRA (SVT, Culture Générale, Santé Publique, Calculs)
QUESTIONS_INFAS_SVT = [
    # --- SUJETS SVT & ANATOMIE (Annales Récurrentes) ---
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
        "question": "Quel effet produit l'excitation du nerf vague (ou nerf pneumogastrique X) sur l'activité du cœur ?",
        "options": ["Une tachycardie immédiate", "Une augmentation de la force des contractions", "Une bradycardie par ralentissement du rythme cardiaque", "Une interruption définitive de l'automatisme"],
        "reponse_correcte": 2
    },
    {
        "question": "Quel médiateur chimique est libéré au niveau de la synapse entre le nerf vague (X) et le nœud sinusal ?",
        "options": ["La noradrénaline", "L'acétylcholine (ACh)", "L'adrénaline", "Le glutamate"],
        "reponse_correcte": 1
    },
    {
        "question": "[Annales] Quelle hormone hyperglycémiante est sécrétée par les cellules alpha des îlots de Langerhans du pancréas ?",
        "options": ["L'insuline", "Le cortisol", "Le glucagon", "L'adrénaline"],
        "reponse_correcte": 2
    },
    {
        "question": "[Annales] Chez l'homme, où s'effectue précisément la maturation des spermatozoïdes ?",
        "options": ["Dans les tubes séminifères", "Dans l'épididyme", "Dans les canaux déférents", "Dans les vésicules séminales"],
        "reponse_correcte": 1
    },
    {
        "question": "[Annales] Quelle structure de la cellule est le siège principal de la respiration cellulaire et de la production d'ATP ?",
        "options": ["Le réticulum endoplasmique", "L'appareil de Golgi", "La mitochondrie", "Le lysosome"],
        "reponse_correcte": 3
    },
    
    # --- SUJETS CULTURE GÉNÉRALE & SANTE PUBLIQUE (Inspiré de Fomesoutra) ---
    {
        "question": "[Santé] En quelle année le Programme Élargi de Vaccination (PEV) a-t-il été lancé en Côte d'Ivoire ?",
        "options": ["1960", "1978", "1987", "1995"],
        "reponse_correcte": 1
    },
    {
        "question": "[Culture Générale] Quelle institution mondiale est chargée de la direction et de la coordination de la santé publique au sein du système des Nations Unies ?",
        "options": ["L'UNICEF", "L'OMS", "L'UNESCO", "Le PNUD"],
        "reponse_correcte": 1
    },
    {
        "question": "[Santé-CI] Quel acronyme désigne l'organisme ivoirien chargé de la distribution des médicaments essentiels dans les structures publiques ?",
        "options": ["NPSP (Nouvelle Pharmacie de la Santé Publique)", "INHP", "CNAM", "AIRP"],
        "reponse_correcte": 0
    },
    {
        "question": "[Annales] Laquelle de ces maladies est causée par un parasite protozoaire transmissible par la piqûre du moustique anophèle femelle ?",
        "options": ["La fièvre jaune", "La dengue", "Le paludisme", "La filariose lymphatique"],
        "reponse_correcte": 2
    },
    {
        "question": "[Culture] Que signifie l'acronyme INHP, structure clé du dispositif sanitaire en Côte d'Ivoire ?",
        "options": [
            "Institut National d'Hématologie Publique",
            "Institut National d'Hygiène Publique",
            "Institut National de l'Hospitalisation Publique",
            "Instance Nationale d'Hygiène Préventive"
        ],
        "reponse_correcte": 1
    },

    # --- SUJETS TESTS NUMÉRIQUES / CALCULS (Inspiré de Fomesoutra) ---
    {
        "question": "[Calculs] Une solution doit passer en 4 heures. Le volume total est de 1 litre. Quel doit être le débit en gouttes par minute ? (1 ml = 20 gouttes)",
        "options": ["42 gouttes/min", "83 gouttes/min", "60 gouttes/min", "125 gouttes/min"],
        "reponse_correcte": 1  # Calcul : (1000 ml * 20 gtts) / (4 * 60 min) = 20000 / 240 = 83.33
    },
    {
        "question": "[Calculs] Vous devez administrer 250 mg d'un antibiotique. Vous disposez d'un flacon de 1 g dilué dans 10 ml. Quel volume prélevez-vous ?",
        "options": ["1,5 ml", "2 ml", "2,5 ml", "5 ml"],
        "reponse_correcte": 2  # Calcul : (250 mg * 10 ml) / 1000 mg = 2.5 ml
    }
]


async def generer_quiz_groq() -> dict:
    """Appelle l'API de Groq pour générer un QCM basé sur les exigences réelles du concours INFAS."""
    if not groq_client:
        logger.error("Client Groq non initialisé.")
        return None
        
    system_prompt = (
        "Tu es un enseignant expert préparant les candidats ivoiriens au concours direct de l'INFAS (Infirmiers, Sages-femmes, Techniciens de santé).\n"
        "Inspirations majeures : Annales des années précédentes, plateformes spécialisées comme Fomesoutra et directives de l'INHP/Ministère de la Santé de Côte d'Ivoire.\n\n"
        "Tu dois impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
        "- 'question': La question posée sous forme de texte.\n"
        "- 'options': Un tableau contenant exactement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) représentant l'index de la bonne réponse.\n\n"
        "Les questions doivent être d'un niveau rigoureux de concours et cibler exclusivement :\n"
        "1. Biologie humaine / SVT (Physiologie, reproduction, système nerveux, immunologie, appareil rénal, génétique).\n"
        "2. Culture Générale Sanitaire (Histoire de la santé en CI, acronymes : NPSP, INHP, OMS, UNICEF, PEV, épidémiologie locale, actualités sanitaires).\n"
        "3. Aptitudes logiques et calculs de conversion basiques (Dosages, débits de perfusion, règles de trois appliquées au domaine de la santé).\n\n"
        "Ajoute parfois un préfixe subtil comme [Sujet SVT], [Culture Sanitaire] ou [Logique Numérique] au début de la question pour faire pro.\n"
        "Renvoie uniquement le JSON brut, sans introduction ni conclusion."
    )
    user_prompt = "Génère une question de niveau Concours INFAS, mixte entre les tendances d'annales et Fomesoutra."

    try:
        completion = groq_client.chat.completions.create(
            model=GROK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.72
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Erreur lors de la génération IA Groq : {e}")
        return None


async def envoyer_question_groupe(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Sélectionne aléatoirement une question dans le vivier d'annales locales ou bascule sur Groq."""
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
        text=f"⏳ *Sélection d'un sujet d'annale INFAS (Question {session['current_quiz_index']}/{session['total_questions']})...*",
        parse_mode="Markdown"
    )
    
    quiz_data = None
    
    # Sélection purement aléatoire parmi le vivier disponible pour casser l'ordre linéaire
    questions_disponibles = [q for q in QUESTIONS_INFAS_SVT if q["question"] not in session["questions_utilisees"]]
    
    if questions_disponibles and random.random() > 0.35:  # Mélange équilibré entre banque fixe et génération dynamique
        quiz_data = random.choice(questions_disponibles)
        session["questions_utilisees"].append(quiz_data["question"])
        logger.info(f"Question issue de la banque d'annales sélectionnée pour le groupe {chat_id}")
    else:
        logger.info("Génération d'une question inédite via l'IA Groq (Modèle Annales & Fomesoutra).")
        quiz_data = await generer_quiz_groq()
        if quiz_data:
            session["questions_utilisees"].append(quiz_data["question"])

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)
    except Exception:
        pass

    if not quiz_data:
        # Secours si l'IA échoue et qu'il reste des questions locales
        if questions_disponibles:
            quiz_data = random.choice(questions_disponibles)
            session["questions_utilisees"].append(quiz_data["question"])
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Erreur de récupération du sujet, transition vers la question suivante...")
            await asyncio.sleep(2)
            if chat_id in GROUP_SESSIONS:
                asyncio.create_task(envoyer_question_groupe(context, chat_id))
            return

    session["correct_option_id"] = int(quiz_data["reponse_correcte"])

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"📝 [Q.{session['current_quiz_index']}/{session['total_questions']}] {quiz_data['question']}"[:300],
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
    
    # Surveillance réactive seconde par seconde
    for _ in range(TEMPS_PAR_QUESTION + 2):
        await asyncio.sleep(1)
        if chat_id not in GROUP_SESSIONS:  
            return
        if session["status"] == "paused":  
            return

    if chat_id in GROUP_SESSIONS and session["status"] == "running":
        asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def recevoir_reponse_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enregistre les scores en temps réel."""
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
    """Lance le grand marathon basé sur les compositions passées."""
    chat_id = update.effective_chat.id
    
    if chat_id in GROUP_SESSIONS:
        await update.message.reply_text("⚠️ Un marathon de révision est déjà actif. Utilise /pause ou /stop.")
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
        text=f"🏁 *Préparation Concours INFAS 2026 - Grand Marathon de Révision* 🏁\n\n"
             f"Sujets extraits des compositions passées et des banques de données d'excellence (*Fomesoutra & Annales Officielles*).\n\n"
             f"• Volume de l'épreuve : *{NOMBRE_TOTAL_QUESTIONS} Questions*\n"
             f"• Temps de réflexion : *{TEMPS_PAR_QUESTION} secondes* par matière.\n\n"
             "⚡ _Que les meilleurs intègrent l'institut ! Début de la première épreuve dans quelques instants..._\n\n"
             "🛠️ Commandes : /pause | /resume | /stop",
        parse_mode="Markdown"
    )
    
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def pause_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Met en pause la session."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucun marathon en cours.")
        return
        
    session = GROUP_SESSIONS[chat_id]
    if session["status"] == "paused":
        await update.message.reply_text("⏸️ Le marathon est déjà suspendu.")
        return
        
    session["status"] = "paused"
    await update.message.reply_text("⏸️ *Marathon suspendu.* Utilisez /resume pour relancer les compositions.")


async def resume_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reprend la session suspendue."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Aucun marathon à reprendre.")
        return
        
    session = GROUP_SESSIONS[chat_id]
    if session["status"] == "running":
        await update.message.reply_text("▶️ Le marathon est déjà en cours.")
        return
        
    session["status"] = "running"
    await update.message.reply_text("▶️ *Reprise immédiate des compositions !* Analyse du sujet suivant...")
    asyncio.create_task(envoyer_question_groupe(context, chat_id))


async def stop_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interrompt définitivement la session."""
    chat_id = update.effective_chat.id
    if chat_id not in GROUP_SESSIONS:
        await update.message.reply_text("❌ Pas de session active à stopper.")
        return
        
    await update.message.reply_text("🛑 *Fin prématurée de l'épreuve.* Correction des copies en cours...")
    await afficher_classement_final(context, chat_id)


async def afficher_classement_final(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Proclame les résultats de la session."""
    session = GROUP_SESSIONS.get(chat_id)
    if not session:
        return

    texte_classement = "🏆 *PROCLAMATION DES RÉSULTATS - CONCOURS INFAS* 🏆\n\n"
    
    if not session["scores"]:
        texte_classement += "❌ Aucun candidat n'a validé de point sur cette session éditée."
    else:
        joueurs_tries = sorted(session["scores"].values(), key=lambda x: x["points"], reverse=True)
        medailles = ["🥇", "🥈", "🥉"]
        for i, joueur in enumerate(joueurs_tries):
            prefixe = medailles[i] if i < 3 else "🔹"
            texte_classement += f"{prefixe} *{joueur['name']}* : {joueur['points']}/{session['current_quiz_index']} Admis\n"

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

    logger.info("🤖 Bot INFAS Marathon [Sujets Passés & Fomesoutra] initialisé avec succès !")
    application.run_polling()


if __name__ == "__main__":
    main()
