import os, json
import google.generativeai as genai
from telegram.ext import Updater, CommandHandler, PollAnswerHandler, CallbackContext
from telegram import Update

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
TOKEN = os.environ["TELEGRAM_TOKEN"]

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 Bienvenue sur le Quiz INFAS !\n\nTape /quiz pour démarrer 5 questions."
    )

def quiz(update: Update, context: CallbackContext):
    update.message.reply_text("⏳ Génération des questions, patiente...")
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = '''Génère 5 QCM sur les constantes vitales pour le concours INFAS.
Réponds UNIQUEMENT en JSON valide sans markdown :
[{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct":0,"explication":"..."}]'''
    response = model.generate_content(prompt)
    text = response.text.strip().replace("```json","").replace("```","")
    questions = json.loads(text)
    context.user_data.update({"questions": questions, "score": 0, "current": 0, "polls": {}})
    send_question(update, context)

def send_question(update, context):
    qs = context.user_data["questions"]
    i = context.user_data["current"]
    if i >= len(qs):
        s = context.user_data["score"]
        t = len(qs)
        update.message.reply_text(
            f"🏁 Quiz terminé !\nScore : {s}/{t} ({round(s/t*100)}%)\n"
            f"{'🎉 Excellent !' if s>=4 else '💪 Continue à réviser !'}"
        )
        return
    q = qs[i]
    msg = update.message.reply_poll(
        question=f"❓ Q{i+1}: {q['question']}",
        options=q["options"], type="quiz",
        correct_option_id=q["correct"],
        explanation=q["explication"], is_anonymous=False
    )
    context.user_data["polls"][msg.poll.id] = i

def poll_answer(update: Update, context: CallbackContext):
    a = update.poll_answer
    polls = context.user_data.get("polls", {})
    if a.poll_id not in polls:
        return
    i = polls[a.poll_id]
    if a.option_ids[0] == context.user_data["questions"][i]["correct"]:
        context.user_data["score"] += 1
    context.user_data["current"] += 1
    context.bot.send_message(chat_id=a.user.id, text="➡️ Question suivante...")

updater = Updater(TOKEN)
dp = updater.dispatcher
dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("quiz", quiz))
dp.add_handler(PollAnswerHandler(poll_answer))
updater.start_polling()
updater.idle()
