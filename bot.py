import os
import json
import re
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
    await update.message.reply_text("⏳ Génération des questions en cours...")

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user", 
                "content": (
                    'Génère exactement 5 QCM sur les constantes vitales INFAS. '
                    'Réponds UNIQUEMENT avec un tableau JSON valide, rien d\'autre. '
                    'Pas de markdown, pas de ```json, pas d\'explication. '
                    'Format exact : '
                    '[{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct":0,"explication":"..."}]'
                )
            }],
            temperature=0.5,
            max_tokens=2000
        )

        text = response.choices[0].message.content.strip()

        # Nettoyage renforcé du JSON
        # 1. Extraire seulement la partie entre [ et ]
        json_match = re.search(r'\[.*?\]', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        # 2. Nettoyage supplémentaire
        text = text.replace("```json", "").replace("```", "").strip()

        questions = json.loads(text)

        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("Le JSON généré n'est pas une liste valide")

        context.user_data["questions"] = questions
        context.user_data["score"] = 0
        context.user_data["current"] = 0
        context.user_data["polls"] = {}

        await send_question(update, context)

    except json.JSONDecodeError:
        await update.message.reply_text("❌ L'IA n'a pas renvoyé un JSON valide. Réessayez avec /quiz.")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur génération : {str(e)}")

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qs = context.user_data.get("questions", [])
    i = context.user_data.get("current", 0)
    total = len(qs)

    if i >= total:
        s = context.user_data.get("score", 0)
        pct = round(s / total * 100) if total > 0 else 0
        if pct >= 80:
            mention = "Excellent ! Tu maîtrises bien ce chapitre ! 🎉"
        elif pct >= 60:
            mention = "Bien ! Continue à réviser ! 👍"
        else:
            mention = "Revois ta fiche de cours et réessaie ! 📚"
        
        await update.message.reply_text(
            f"🏁 **Quiz terminé !**\n\n"
            f"Score : **{s}/{total}** ({pct}%)\n\n"
            f"{mention}\n\nTape /quiz pour un nouveau quiz."
        )
        return

    q = qs[i]
    msg = await update.message.reply_poll(
        question=f"Q{i+1}/{total} : {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=q.get("explication", ""),
        is_anonymous=False
    )
    context.user_data["polls"][msg.poll.id] = i

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    a = update.poll_answer
    if not a or not a.poll_id:
        return

    polls = context.user_data.get("polls", {})
    if a.poll_id not in polls:
        return

    i = polls[a.poll_id]
    questions = context.user_data.get("questions", [])

    if a.option_ids and a.option_ids[0] == questions[i]["correct"]:
        context.user_data["score"] = context.user_data.get("score", 0) + 1

    context.user_data["current"] += 1
    await context.bot.send_message(chat_id=a.user.id, text="➡️ Question suivante...")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))

    print("🤖 Bot INFAS QUIZ démarré avec succès !")
    app.run_polling(allowed_updates=["message", "poll_answer"], drop_pending_updates=True)
