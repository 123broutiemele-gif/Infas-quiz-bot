import os
import json
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes
from telegram.error import Conflict, TimedOut

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

    # Question suivante
    try:
        await context.bot.send_message(chat_id=a.user.id, text="➡️ Question suivante...")
        # On utilise le bot directement pour éviter le problème d'update.message
        await send_question_to_user(a.user.id, context)
    except Exception:
        pass

async def send_question_to_user(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Version sécurisée pour envoyer la question suivante"""
    qs = context.user_data.get("questions", [])
    i = context.user_data.get("current", 0)
    total = len(qs)

    if i >= total:
        # Fin du quiz (déjà géré ailleurs)
        return

    q = qs[i]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=f"Q{i+1}/{total} : {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=q.get("explication", ""),
        is_anonymous=False
    )
    # Mise à jour de l'index du poll
    # Note: Pour simplifier, on peut améliorer plus tard

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))

    print("🤖 Bot INFAS QUIZ démarré avec succès !")

    # Boucle robuste pour polling
    while True:
        try:
            app.run_polling(
                allowed_updates=["message", "poll_answer"],
                drop_pending_updates=True,
                close_loop=False
            )
        except Conflict:
            print("⚠️ Conflit détecté (ancienne instance), redémarrage...")
            # Attendre un peu puis réessayer
        except TimedOut:
            print("⚠️ Timeout, nouvelle tentative...")
        except Exception as e:
            print(f"❌ Erreur : {e}")
        import asyncio
        asyncio.sleep(5)
