import os
import json
import re
import asyncio
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes

# ==================== CONFIGURATION ====================
TOKEN = os.environ.get("TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TOKEN:
    raise ValueError("❌ Le TOKEN Telegram n'est pas configuré !")
if not GROQ_API_KEY:
    raise ValueError("❌ La clé GROQ_API_KEY n'est pas configurée !")

client = Groq(api_key=GROQ_API_KEY)
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenue sur **INFAS QUIZ** ! 🎯\n\n"
        "Tape /quiz pour démarrer un nouveau quiz sur les constantes vitales."
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sauvegarde du chat_id pour pouvoir envoyer les questions suivantes plus tard
    chat_id = update.effective_chat.id
    context.user_data["chat_id"] = chat_id
    
    await context.bot.send_message(chat_id=chat_id, text="⏳ Génération des questions en cours...")

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user", 
                "content": (
                    'Génère exactement 5 QCM sur les constantes vitales INFAS. '
                    'Réponds UNIQUEMENT avec un tableau JSON valide, rien d\'autre. '
                    'Pas de markdown, pas d\'explication. '
                    'Format : [{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct":0,"explication":"..."}]'
                )
            }],
            temperature=0.5,
            max_tokens=2000
        )

        text = response.choices[0].message.content.strip()

        # Nettoyage renforcé du JSON
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        text = text.replace("```json", "").replace("```", "").strip()
        questions = json.loads(text)

        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("JSON invalide")

        context.user_data["questions"] = questions
        context.user_data["score"] = 0
        context.user_data["current"] = 0

        # Envoi de la première question
        await send_question(context)

    except Exception as e:
        print(f"Erreur IA / JSON : {e}")
        await context.bot.send_message(chat_id=chat_id, text="❌ L'IA n'a pas renvoyé un JSON valide. Réessayez avec /quiz.")

async def send_question(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.user_data.get("chat_id")
    qs = context.user_data.get("questions", [])
    i = context.user_data.get("current", 0)
    total = len(qs)

    # Si on a atteint la fin des questions
    if i >= total:
        s = context.user_data.get("score", 0)
        pct = round(s / total * 100) if total > 0 else 0
        mention = "Excellent ! Tu maîtrises bien ce chapitre ! 🎉" if pct >= 80 else "Bien ! Continue à réviser ! 👍" if pct >= 60 else "Revois ta fiche de cours 📚"
        await context.bot.send_message(chat_id=chat_id, text=f"🏁 Quiz terminé !\nScore : {s}/{total} ({pct}%)\n{mention}\n\nTape /quiz pour un nouveau quiz.")
        return

    q = qs[i]
    cleaned_options = [opt[:100] for opt in q["options"]]
    
    await context.bot.reply_poll(
        chat_id=chat_id,
        question=f"Q{i+1}/{total} : {q['question']}",
        options=cleaned_options,
        type="quiz",
        correct_option_id=int(q["correct"]),
        explanation=q.get("explication", "")[:200],
        is_anonymous=False
    )

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cette fonction se déclenche automatiquement dès que l'étudiant clique sur une réponse.
    """
    poll_answer = update.poll_answer
    
    # Vérification si la réponse est correcte pour compter les points
    qs = context.user_data.get("questions", [])
    i = context.user_data.get("current", 0)
    
    if i < len(qs):
        correct_id = int(qs[i]["correct"])
        # Si l'utilisateur a choisi la bonne option, on augmente son score
        if poll_answer.option_ids and poll_answer.option_ids[0] == correct_id:
            context.user_data["score"] = context.user_data.get("score", 0) + 1

    # On passe à l'index de la question suivante
    context.user_data["current"] = i + 1
    
    # On attend 2 petites secondes pour laisser le temps à l'étudiant de lire l'explication Telegram
    await asyncio.sleep(2)
    
    # On appelle la fonction pour envoyer automatiquement la question suivante
    await send_question(context)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    print("🤖 Bot INFAS QUIZ démarré avec succès (Polling)")

    await app.initialize()
    await app.updater.start_polling(allowed_updates=["message", "poll_answer"], drop_pending_updates=True)
    await app.start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot arrêté.")
