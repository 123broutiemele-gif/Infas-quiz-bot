import os, json
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyC3fPfSFNE3InvX9u9I3-V5cKXcIIaP_IU")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "NOUVEAU_TOKEN_ICI")

genai.configure(api_key=GEMINI_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bienvenue ! Tape /quiz pour démarrer.")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Génération des questions...")
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = 'Génère 3 QCM sur les constantes vitales INFAS. Réponds UNIQUEMENT en JSON : [{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct":0,"explication":"..."}]'
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = text.replace("```json","").replace("```","").strip()
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
        await update.message.reply_text(f"🏁 Terminé ! Score : {s}/{t}")
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
    context.user_data["polls"][msg.poll.id] = i

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    a = update.poll_answer
    polls = context.user_data.get("polls", {})
    if a.poll_id not in polls:
        return
    i = polls[a.poll_id]
    if a.option_ids[0] == context.user_data["questions"][i]["correct"]:
        context.user_data["score"] += 1
    context.user_data["current"] += 1
    await context.bot.send_message(chat_id=a.user.id, text="➡️ Question suivante...")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))
    app.run_polling(allowed_updates=["message", "poll_answer"], drop_pending_updates=True)
