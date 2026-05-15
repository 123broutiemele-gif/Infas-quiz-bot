import os
import json
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes

# ==================== NOUVEAU SDK GEMINI ====================
from google import genai

# Configuration Gemini
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenue sur le Quiz INFAS !\n\n"
        "Tape /quiz pour démarrer."
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Génération des questions...")

    prompt = '''Génère 5 QCM sur les constantes vitales INFAS.
Réponds UNIQUEMENT en JSON sans markdown :

[
  {
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct": "A"
  },
  ...
]'''

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",   # Tu peux tester "gemini-2.0-flash-exp" si disponible
            contents=prompt
        )
        
        text = response.text
        
        # Nettoyage du texte si Gemini ajoute du markdown
        text = text.replace("```json", "").replace("```", "").strip()
        
        questions = json.loads(text)
        
        context.user_data["questions"] = questions
        context.user_data["score"] = 0
        context.user_data["current"] = 0
        context.user_data["polls"] = {}

        await send_question(update, context)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur lors de la génération : {e}")

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = context.user_data["questions"]
    i = context.user_data["current"]
    
    if i >= len(q):
        s = context.user_data["score"]
        t = len(q)
        await update.message.reply_text(
            f"🏁 Quiz Terminé ! Score : {s}/{t} ({round(s*100/t)}%)\n\n"
            f"{'Excellent !' if s >= 4 else 'Continue !'} 👍"
        )
        return

    qs = q[i]
    await update.message.reply_poll(
        question=f"Q{i+1}: {qs['question']}",
        options=qs["options"],
        type="quiz",
        correct_option_id=qs["correct"],   # Index de la bonne réponse (0,1,2,3)
        explanation=qs.get("explanation", ""),
        is_anonymous=False
    )

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    a = update.poll_answer
    poll_id = a.poll_id
    
    if poll_id not in context.user_data.get("polls", {}):
        return

    i = context.user_data["polls"][poll_id]
    correct_index = context.user_data["questions"][i]["correct"]

    if a.option_ids and a.option_ids[0] == correct_index:
        context.user_data["score"] += 1

    context.user_data["current"] += 1
    await send_question(update, context)   # Note: update n'a pas de message ici, mais send_question utilise update.message

# ====================== MAIN ======================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))

    print("🚀 Bot démarré...")
    app.run_polling(allowed_updates=["message", "poll_answer"])
