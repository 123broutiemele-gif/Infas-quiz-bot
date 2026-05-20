import os
import json
import logging
import asyncio
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

# CONFIGURATION ET ENVIRONNEMENT
TELEGRAM_TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

if not TELEGRAM_TOKEN:
    raise ValueError("Le TOKEN de Telegram est manquant dans les variables d'environnement.")
if not GROQ_API_KEY:
    raise ValueError("La clé GROQ_API_KEY est manquante dans les variables d'environnement.")

groq_client = Groq(api_key=GROQ_API_KEY)

# CONSTANTES DU QUIZ
QUESTIONS_PAR_QUIZ = 25
FICHIER_HISTORIQUE = "historique_questions.json"
GROUP_SESSIONS = {}

# GESTION DE L'HISTORIQUE DES QUESTIONS (Anti-répétition persistante)
def charger_historique() -> list:
    if os.path.exists(FICHIER_HISTORIQUE):
        try:
            with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'historique : {e}")
    return []

def sauvegarder_dans_historique(question_text: str):
    historique = charger_historique()
    # Nettoyage basique pour comparaison
    clean_text = question_text.strip().lower()
    if clean_text not in historique:
        historique.append(clean_text)
        try:
            with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
                json.dump(historique, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique : {e}")

# ADAPTATION DU TEMPS DE RÉPONSE
def calculer_temps_reponse(question_data: dict) -> int:
    """ Calcule le temps requis selon le volume de texte et la complexité. """
    texte_total = question_data["question"] + " ".join(question_data["options"])
    nombre_mots = len(texte_total.split())
    
    # Temps de base : 20 secondes
    temps = 20
    # On ajoute du temps pour la lecture (approx 1.5s par tranche de 5 mots)
    temps += int(nombre_mots / 5) * 1.5
    
    # Bonus de complexité si des termes médicaux lourds ou calculs sont détectés
    mots_complexes = ["calculer", "concentration", "posologie", "osmose", "génétique", "dilution", "cycle"]
    if any(mot in texte_total.lower() for mot in mots_complexes):
        temps += 10
        
    # Limites de sécurité (entre 20 et 50 secondes maximum pour un sondage Telegram)
    return min(max(int(temps), 20), 50)


# GÉNÉRATION DE QUESTION VIA GROQ (IA)
async def generer_question_infas_ia() -> dict:
    """Appelle Groq en lui injectant l'historique pour exclure les doublons."""
    historique = charger_historique()
    
    # On ne passe que les 30 dernières questions pour ne pas saturer le contexte du prompt
    historique_recent = historique[-30:] if len(historique) > 30 else historique
    exclusions = "\n".join([f"- {q}" for q in historique_recent])

    system_prompt = (
        "Tu es un concepteur officiel du concours d'entrée à l'INFAS en Côte d'Ivoire.\n"
        "Génère une question de QCM réaliste, rigoureuse et du niveau exact des épreuves des années 2010 à 2025.\n"
        "Domaines cibles : Anatomie-Physiologie (SVT), Santé Publique, Culture Générale Médicale, Secourisme ou Initiation à la Pharmacologie.\n\n"
        "Tu dois impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
        "- 'question': Le texte de la question.\n"
        "- 'options': Un tableau de strictement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) représentant l'index de la bonne réponse.\n\n"
        f"CRITÈRE ABSOLU : Ne génère PAS une question ressemblant à celles-ci :\n{exclusions}\n"
        "Renvoie uniquement l'objet JSON pur, sans aucun texte avant ou après."
    )

    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Génère une question de niveau concours INFAS d'Afrique de l'Ouest."}
            ],
            response_format={"type": "json_object"},
            temperature=0.85 # Température légèrement augmentée pour maximiser la variété
        )
        
        quiz_data = json.loads(completion.choices[0].message.content.strip())
        return quiz_data
    except Exception as e:
        logger.error(f"Erreur de génération Groq : {e}")
        return None


# FONCTION PRINCIPALE : ENVOI DE LA QUESTION ET SÉQUENCE
async def orchestrer_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if chat_id not in GROUP_SESSIONS:
        return

    session = GROUP_SESSIONS[chat_id]
    
    if session["status"] != "running":
        return

    session["current_index"] += 1

    # Fin du quiz à 25 questions
    if session["current_index"] > QUESTIONS_PAR_QUIZ:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🏁 *Fin du Quiz spécial Annales INFAS !*\nFélicitations aux participants. Tapez `/infas` pour démarrer une nouvelle session de {QUESTIONS_PAR_QUIZ} questions uniques."
        )
        GROUP_SESSIONS.pop(chat_id, None)
        return

    # Message d'attente pendant la génération Groq
    msg_attente = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔄 _Groq génère une question inédite (Question {session['current_index']}/{QUESTIONS_PAR_QUIZ})..._"
    )

    quiz_data = await generer_question_infas_ia()
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_attente.message_id)
    except Exception:
        pass

    if not quiz_data or "question" not in quiz_data:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ Erreur de communication avec Groq. Nouvelle tentative...")
        session["current_index"] -= 1
        await asyncio.sleep(3)
        asyncio.create_task(orchestrer_quiz(context, chat_id))
        return

    # Sauvegarde immédiate dans l'historique global pour éviter les doublons futurs
    sauvegarder_dans_historique(quiz_data["question"])

    # Calcul dynamique de la durée de la question
    duree_sondage = calculer_temps_reponse(quiz_data)

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"❓ [INFAS {session['current_index']}/{QUESTIONS_PAR_QUIZ}] {quiz_data['question']}"[:300],
            options=[opt[:100] for opt in quiz_data["options"]],
            correct_option_id=int(quiz_data["reponse_correcte"]),
            type="quiz",
            is_anonymous=False,
            open_period=duree_sondage
        )
    except Exception as e:
        logger.error(f"Erreur d'envoi du sondage Telegram : {e}")
        asyncio.create_task(orchestrer_quiz(context, chat_id))
        return

    # Attente dynamique et réactive seconde par seconde
    for _ in range(duree_sondage + 3):
        await asyncio.sleep(1)
        if chat_id not in GROUP_SESSIONS or GROUP_SESSIONS[chat_id]["status"] != "running":
            return

    # Séquence suivante
    asyncio.create_task(orchestrer_quiz(context, chat_id))


# COMMANDES DU BOT
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Bienvenue sur le Bot de révision INFAS automatique !*\n\n"
        "Ce bot utilise l'IA Groq pour extraire et modéliser des questions basées sur les *anciens sujets du concours INFAS (2010 à 2025)*.\n\n"
        "💡 *Règles du jeu :*\n"
        f"• Chaque quiz comporte exactement `{QUESTIONS_PAR_QUIZ} questions`.\n"
        "• Le temps de réponse s'ajuste automatiquement selon la longueur de la question.\n"
        "• Une question posée ne réapparaît *jamais*, d'une session à l'autre.\n\n"
        "➡️ Tapez `/infas` dans votre groupe ou en privé pour lancer un quiz."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def cmd_infas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id in GROUP_SESSIONS:
        await update.message.reply_text("⚠️ Un quiz est déjà en cours dans ce tchat. Attendez qu'il se termine ou tapez `/stop_infas`.")
        return

    # Initialisation de la session
    GROUP_SESSIONS[chat_id] = {
        "status": "running",
        "current_index": 0
    }

    await update.message.reply_text(
        f"🚀 *Démarrage d'un Quiz de {QUESTIONS_PAR_QUIZ} questions (Annales INFAS 2010-2025).*\n"
        "Soyez prêts, la première question arrive..."
    )
    
    asyncio.create_task(orchestrer_quiz(context, chat_id))

async def cmd_stop_infas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in GROUP_SESSIONS:
        GROUP_SESSIONS.pop(chat_id, None)
        await update.message.reply_text("🛑 *Le quiz a été arrêté.* Toutes les questions sauvegardées jusqu'ici ne reviendront plus.")
    else:
        await update.message.reply_text("Aucun quiz n'est actif actuellement.")


# MAIN EXECUTION
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers de commandes
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("infas", cmd_infas))
    application.add_handler(CommandHandler("stop_infas", cmd_stop_infas))

    logger.info("Bot Annales INFAS démarré et prêt.")
    application.run_polling()

if __name__ == "__main__":
    main()
