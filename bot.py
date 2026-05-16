import os
import json
import re
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
        context.user_data["polls"] = {}

        await send_question(update, context)

    except Exception as e:
        await update.message.reply_text("❌ L'IA n'a pas renvoyé un JSON valide. Réessayez avec /quiz.")

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qs = context.user_data.get("questions", [])
    i = context.user_data.get("current", 0)
    total = len(qs)

    if i >= total:
        s = context.user_data.get("score", 0)
        pct = round(s / total * 100) if total > 0 else 0
        mention = "Excellent ! Tu maîtrises bien ce chapitre ! 🎉" if pct >= 80 else "Bien ! Continue à réviser ! 👍" if pct >= 60 else "Revois ta fiche de cours 📚"
        await update.message.reply_text(f"🏁 Quiz terminé !\nScore : {s}/{total} ({pct}%)\n{mention}\n\nTape /quiz pour un nouveau quiz.")
        return

    q = qs[i]
    await update.message.reply_poll(
        question=f"Q{i+1}/{total} : {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=q.get("explication", ""),
        is_anonymous=False
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(lambda update, context: None))  # Temporaire

    print("🤖 Bot INFAS QUIZ démarré avec succès (Polling)")

    # Mode Polling robuste
    import asyncio
    while True:
        try:
            app.run_polling(
                allowed_updates=["message", "poll_answer"],
                drop_pending_updates=True
            )
        except Conflict:
            print("⚠️ Conflit détecté (ancienne instance), redémarrage...")
        except TimedOut:
            print("⚠️ Timeout, nouvelle tentative...")
        except Exception as e:
            print(f"❌ Erreur : {e}")
        asyncio.sleep(5)
