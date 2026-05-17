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

# CORRECTION DU MODÈLE GROQ : Utilisation du modèle versatile stable et supporté
GROK_MODEL = "llama-3.3-70b-versatile"
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# CONFIGURATION DU QUIZ
GROUP_SESSIONS = {}
TEMPS_PAR_QUESTION = 25  
NOMBRE_TOTAL_QUESTIONS = 45  

# BANQUE DE QUESTIONS LOCALE ISSUE DIRECTEMENT DU MANUEL INFAS (Pages 223, 224 et Tests d'évaluation de la page 226)
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
        "options": ["Une tachycardie immédiate", "Une augmentation de la force des contractions", "Une bradycardie par ralentissement du rythme cardiaque", "Une interruption définitive de l'automatisme"],
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
    },
    {
        "question": "[Manuel p.226] L'élément cité ci-dessous est une partie du néphron :",
        "options": ["Le tube contourné proximal", "La capsule de Bowman", "L'Anse de Henlé", "Toutes les réponses sont correctes"],
        "reponse_correcte": 3
    },
    {
        "question": "[Manuel p.226] Une systole est :",
        "options": ["Un relâchement cardiaque", "Une contraction cardiaque", "Une pause globale du cœur", "Une baisse de la pression artérielle"],
        "reponse_correcte": 1
    },
    {
        "question": "[Manuel p.226] L'acétylcholine est le médiateur chimique du nerf X. Son action :",
        "options": ["Entraîne une tachycardie au niveau du cœur", "Entraîne une bradycardie au niveau du cœur", "Augmente la force de contraction ventriculaire", "N'a aucun effet sur le tissu nodal"],
        "reponse_correcte": 1
    }
]


async def generer_quiz_groq() -> dict:
    """Appelle l'API de Groq pour générer un QCM au format JSON."""
    if not groq_client:
        logger.error("Client Groq non initialisé.")
        return None
        
    system_prompt = (
        "Tu es un enseignant expert préparant les étudiants ivoiriens au concours de l'INFAS.\n"
        "Tu dois impérativement répondre sous la forme d'un objet JSON contenant exactement ces clés :\n"
        "- 'question': La question posée sous forme de texte.\n"
        "- 'options': Un tableau contenant exactement 4 propositions de réponses.\n"
        "- 'reponse_correcte': Un entier (0, 1, 2 ou 3) représentant l'index de la bonne réponse.\n\n"
        "Génère une question portant sur la santé publique, l'anatomie humaine, la pharmacologie de base, l'obstétrique ou le secourisme.\n"
        "Renvoie uniquement le JSON brut, sans fioritures."
    )
    user_prompt = "Génère une question de QCM difficile de niveau concours INFAS."

    try:
        completion = groq_client.chat.completions.create(
            model=GROK_MODEL,
            messages=[
                {"role": "system", "system_prompt"},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.65
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Erreur lors de la requête Groq : {e}")
        return None


async def envoyer_question_groupe(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Génère et envoie la question suivante dans le groupe."""
    if chat_id not in GROUP_SESSIONS:
        return

    session = GROUP_SESSIONS[chat_id]
    session["current_quiz_index"] += 1
    
    if session["current_quiz_index"] > session["total_questions"]:
        await afficher_classement_final(context, chat_id)
        return

    msg_attente = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"⏳ *Préparation de
