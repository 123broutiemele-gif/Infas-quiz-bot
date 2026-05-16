import os, json
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes

client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TA_CLE_GROQ_ICI"))
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8819957114:AAHf_RNOHxTkgyQOwjExhErWD9Iool7oqsU")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenue sur INFAS QUIZ ! Tape /quiz pour demarrer."
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generation des questions...")
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": 'Genere 5 QCM sur les constantes vitales INFAS. Reponds UNIQUEMENT en JSON sans markdown : [{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct":0,"explication":"..."}]'}]
        )
        text = response.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        questions = json.loads(text)
        context.user_data["questions"] = questions
        context.user_data["score"] = 0
        context.user_data["current"] = 0
        context.user_data["polls"] = {}
        await send_question(update, context)
    except Exception as e:
        await update.message.reply_text(f"Erreur : {str(e)}")

async def send_question(update, context):
    qs = context.user_data["questions"]
    i = context.user_data["current"]
    total = len(qs)
    if i >= total:
        s = context.user_data["score"]
        pct = round(s / total * 100)
        if pct >= 80:
            mention = "Excellent ! Tu maitrises bien ce chapitre !"
        elif pct >= 60:
            mention = "Bien ! Continue a reviser !"
        else:
            mention = "Revois ta fiche de cours et reessaie !"
        await update.message.reply_text(f"Quiz termine ! Score : {s}/{total} ({pct}%)\n{mention}\nTape /quiz pour un nouveau quiz !")
        return
    q = qs[i]
    msg = await update.message.reply_poll(
        question=f"Q{i+1}/{total} : {q['question']}",
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
    await context.bot.send_message(chat_id=a.user.id, text="Question suivante...")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))
    app.run_polling(allowed_updates=["message", "poll_answer"], drop_pending_updates=True)
