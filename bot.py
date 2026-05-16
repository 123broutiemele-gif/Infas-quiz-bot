import os, json
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyC3fPfSFNE3InvX9u9I3-V5cKXcIIaP_IU")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8819957114:AAHf_RNOHxTkgyQOwjExhErWD9Iool7oqsU")

genai.configure(api_key=GEMINI_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bienvenue sur INFAS QUIZ !\n\nTape /quiz pour démarrer.")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Génération des questions...")
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = 'Génère 3 QCM sur les constantes vitales INFAS. Réponds UNIQUEMENT en JSON : [{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct":0,"explication":"..."}]'
        response = model.generate_content(prompt)
        text = response.text.strip().replace("```json","").replace("```","").strip()
        questions = json.loads(text)
        context.user_data["questions"] = questions
        context.user_data["score"] = 0
        context.user_data["current"] = 0
        context.user_data["polls"] = {}
        await send_question(update, context)
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {str(e)}")

async def send_question(update, context):
    qs = context.user_data["questions"]
    i = context.user_data["current"]
    if i >= len(qs):
        s = context.user_data["score"]
        t = len(qs)
        await update.message.reply_text(
            f"🏁 Terminé ! Score : {s}/{t} ({round(s/t*100)}%)\n"
            f"{'🎉 Excellent !' if s==t else '💪 Continue à réviser !'}"
        )
        return
    q = qs[i]
    msg = await update.message.reply_poll(
        question=f"Q{i+1}: {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=q["explication"],
        is_anonymous=False
    )
    context.user_data["polls"][msg
