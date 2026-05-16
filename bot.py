import os
import json
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
                    'Génère 5 QCM sur les constantes vitales INFAS. '
                    'Réponds UNIQUEMENT en JSON valide sans aucun markdown, '
                    'sans explication supplémentaire : '
                    '[{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],'
                    '"correct":0,"explication":"..."}]'
                )
            }],
            temperature=0.7,
            max_tokens=1500
        )

        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()

        questions = json.loads(text)

        if not questions or len(questions) == 0:
            raise ValueError("Aucune question générée")

        context.user_data["questions"] = questions
        context.user_data["score"] = 0
        context.user_data["current"] = 0
        context.user_data["polls"] = {}

        await send_question(update, context)

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
            f"🏁 **Quiz terminé !**\n\nScore : **{s}/{total}** ({pct}%)\n\n{mention}\n\nTape /quiz pour un nouveau quiz."
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
    if not a or a.poll_id is None:
        return

    polls = context.user_data.get("polls", {})
    if a.poll_id not in polls:
        return

    i = polls[a.poll_id]
    questions = context.user_data.get("questions", [])

    # Incrémenter le score si bonne réponse
    if a.option_ids and a.option_ids[0] == questions[i]["correct"]:
        context.user_data["score"] = context.user_data.get("score", 0) + 1

    context.user_data["current"] += 1

    # Envoyer la prochaine question (utiliser chat_id de l'utilisateur)
    try:
        await context.bot.send_message(chat_id=a.user.id, text="➡️ Question suivante...")
        # On recrée un Update fictif pour send_question (solution simple)
        fake_update = Update(0, None)
        fake_update.message = await context.bot.send_message(chat_id=a.user.id, text="...")
        await send_question(fake_update, context)
    except Exception:
        pass  # On évite les crashes

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))

    print("🤖 Bot INFAS QUIZ démarré avec succès !")

    # === MODE WEBHOOK (recommandé sur Railway) ===
    import asyncio
    PORT = int(os.environ.get("PORT", 8080))

    async def main():
        await app.initialize()
        await app.start()
        
        # Supprime l'ancien webhook et en met un nouveau
        await app.bot.delete_webhook(drop_pending_updates=True)
        await app.bot.set_webhook(
            url=f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN')}/",
            allowed_updates=["message", "poll_answer"]
        )
        
        print(f"🌐 Webhook activé sur le port {PORT}")
        await asyncio.Event().wait()  # Garde le bot vivant

    asyncio.run(main())
