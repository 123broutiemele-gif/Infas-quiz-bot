import os, json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes
from anthropic import Anthropic

client = Anthropic()
TOKEN = os.environ["TELEGRAM_TOKEN"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenue sur le Quiz INFAS !\n\nTape /quiz pour démarrer 10 questions sur les constantes vitales."
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Génération des questions, patiente...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system='Génère 5 QCM sur les constantes vitales INFAS. Réponds UNIQUEMENT en JSON valide : [{"question":"...","options":["A....","B....","C....","D...."],"correct":0,"explication":"..."}]',
        messages=[{"role":"user","content":"Génère les questions."}]
    )
    questions = json.loads(response.content[0].text)
    context.user_data.update({"questions": questions, "score": 0, "current": 0, "polls": {}})
    await send_question(update, context)

async def send_question(update, context):
    qs = context.user_data["questions"]
    i = context.user_data["current"]
    if i >= len(qs):
        s = context.user_data["score"]
        t = len(qs)
        await update.message.reply_text(f"🏁 Terminé !\nScore : {s}/{t} ({round(s/t*100)}%)\n{'🎉 Excellent !' if s>=4 else '💪 Continue à réviser !'}")
        return
    q = qs[i]
    msg = await update.message.reply_poll(
        question=f"❓ Q{i+1}: {q['question']}",
        options=q["options"], type="quiz",
        correct_option_id=q["correct"],
        explanation=q["explication"], is_anonymous=False
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
    await context.bot.send_message(chat_id=a.user.id, text="➡️ Prochaine question...")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(PollAnswerHandler(poll_answer))
app.run_polling()
