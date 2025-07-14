import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
from uuid import uuid4

# Flask app for webhook
app = Flask(__name__)

# Bot token and admin IDs
BOT_TOKEN = "7882432628:AAGbj6whawzRiia7dKZ14YxGAmuUhcb9hvY"
ADMIN_IDS = ["5899761420"]  # Replace with your Telegram user ID

# Google Sheets setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import os
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(os.environ.get('GOOGLE_CREDENTIALS')), SCOPE)
CLIENT = gspread.authorize(CREDS)
SHEET = CLIENT.open("DebreAminProgress").sheet1

# JSON file for courses
COURSE_FILE = "courses.json"

# Initialize courses if file doesn't exist
if not os.path.exists(COURSE_FILE):
    initial_courses = {
        "Prayer Basics": {
            "chapters": [
                {"name": "Chapter 1", "pdf": None, "audio": None, "video": None, "questions": [
                    {"question": "What is prayer?", "options": ["Talking to God", "Reading", "Singing", "Eating"], "correct_answer": 0},
                    {"question": "Who can pray?", "options": ["Only priests", "Everyone", "Only adults", "Only children"], "correct_answer": 1},
                    {"question": "When should we pray?", "options": ["Never", "Only at church", "Anytime", "Only at night"], "correct_answer": 2}
                ]},
                {"name": "Chapter 2", "pdf": None, "audio": None, "video": None, "questions": [
                    {"question": "What is a common prayer?", "options": ["Our Father", "Happy Birthday", "National Anthem", "Poem"], "correct_answer": 0},
                    {"question": "Why do we pray?", "options": ["To sleep", "To connect with God", "To eat", "To play"], "correct_answer": 1},
                    {"question": "Where can we pray?", "options": ["Only at home", "Only at church", "Anywhere", "Only at school"], "correct_answer": 2}
                ]}
            ]
        },
        "Psalms Intro": {
            "chapters": [
                {"name": "Chapter 1", "pdf": None, "audio": None, "video": None, "questions": [
                    {"question": "Who wrote many Psalms?", "options": ["David", "Moses", "Abraham", "Noah"], "correct_answer": 0},
                    {"question": "What is a Psalm?", "options": ["A story", "A song or poem", "A law", "A letter"], "correct_answer": 1},
                    {"question": "Where are Psalms found?", "options": ["New Testament", "Old Testament", "Apocrypha", "Quran"], "correct_answer": 1}
                ]}
            ]
        }
    }
    with open(COURSE_FILE, "w") as f:
        json.dump(initial_courses, f, indent=4)

def load_courses():
    with open(COURSE_FILE, "r") as f:
        return json.load(f)

def save_courses(courses):
    with open(COURSE_FILE, "w") as f:
        json.dump(courses, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Courses", callback_data="courses")],
        [InlineKeyboardButton("Progress", callback_data="progress")],
        [InlineKeyboardButton("Admin", callback_data="admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to Debre Amin Sunday School! Please select an option:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    if data == "courses":
        courses = load_courses()
        keyboard = [[InlineKeyboardButton(course, callback_data=f"course_{course}")] for course in courses]
        keyboard.append([InlineKeyboardButton("Back", callback_data="start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Available courses:", reply_markup=reply_markup)

    elif data == "progress":
        records = SHEET.get_all_records()
        user_progress = [r for r in records if r["User ID"] == str(user_id)]
        if not user_progress:
            await query.message.edit_text("You haven't completed any chapters yet.")
        else:
            progress_text = "Your Progress:\n"
            for record in user_progress:
                progress_text += f"Course: {record['Course']}, Chapter: {record['Chapter']}, Completed: {record['Completed']}\n"
            await query.message.edit_text(progress_text)
        keyboard = [[InlineKeyboardButton("Back", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_reply_markup(reply_markup=reply_markup)

    elif data == "admin":
        if user_id not in ADMIN_IDS:
            await query.message.edit_text("You are not authorized to access admin features.")
            keyboard = [[InlineKeyboardButton("Back", callback_data="start")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_reply_markup(reply_markup=reply_markup)
            return
        keyboard = [
            [InlineKeyboardButton("Add Course", callback_data="admin_add_course")],
            [InlineKeyboardButton("Edit Course", callback_data="admin_edit_course")],
            [InlineKeyboardButton("Delete Course", callback_data="admin_delete_course")],
            [InlineKeyboardButton("Back", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Admin Panel:", reply_markup=reply_markup)

    elif data.startswith("course_"):
        course_name = data.split("_")[1]
        context.user_data["current_course"] = course_name
        courses = load_courses()
        chapters = courses[course_name]["chapters"]
        keyboard = [[InlineKeyboardButton(chapter["name"], callback_data=f"chapter_{course_name}_{chapter['name']}")] for chapter in chapters]
        keyboard.append([InlineKeyboardButton("Back", callback_data="courses")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Chapters in {course_name}:", reply_markup=reply_markup)

    elif data.startswith("chapter_"):
        _, course_name, chapter_name = data.split("_", 2)
        context.user_data["current_course"] = course_name
        context.user_data["current_chapter"] = chapter_name
        courses = load_courses()
        chapter = next(c for c in courses[course_name]["chapters"] if c["name"] == chapter_name)
        records = SHEET.get_all_records()
        if any(r["User ID"] == str(user_id) and r["Course"] == course_name and r["Chapter"] == chapter_name and r["Completed"] == "Yes" for r in records):
            await query.message.edit_text("You have already completed this chapter.")
            keyboard = [[InlineKeyboardButton("Back", callback_data=f"course_{course_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_reply_markup(reply_markup=reply_markup)
            return
        if chapter["pdf"]:
            await query.message.reply_document(document=chapter["pdf"], caption=f"{chapter_name} PDF")
        if chapter["audio"]:
            await query.message.reply_audio(audio=chapter["audio"], caption=f"{chapter_name} Audio")
        if chapter["video"]:
            await query.message.reply_text(f"{chapter_name} Video: {chapter['video']}")
        keyboard = [[InlineKeyboardButton("Done Studying", callback_data=f"done_studying_{course_name}_{chapter_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Please study the materials and click 'Done Studying' when ready.", reply_markup=reply_markup)

    elif data.startswith("done_studying_"):
        _, course_name, chapter_name = data.split("_", 2)
        context.user_data["current_course"] = course_name
        context.user_data["current_chapter"] = chapter_name
        context.user_data["current_question"] = 0
        context.user_data["correct_answers"] = 0
        courses = load_courses()
        chapter = next(c for c in courses[course_name]["chapters"] if c["name"] == chapter_name)
        question = chapter["questions"][0]
        keyboard = [[InlineKeyboardButton(opt, callback_data=f"answer_{course_name}_{chapter_name}_{i}")] for i, opt in enumerate(question["options"])]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Question 1: {question['question']}", reply_markup=reply_markup)

    elif data.startswith("answer_"):
        _, course_name, chapter_name, answer_idx = data.split("_", 3)
        answer_idx = int(answer_idx)
        courses = load_courses()
        chapter = next(c for c in courses[course_name]["chapters"] if c["name"] == chapter_name)
        question_idx = context.user_data["current_question"]
        question = chapter["questions"][question_idx]
        if answer_idx == question["correct_answer"]:
            context.user_data["correct_answers"] += 1
        context.user_data["current_question"] += 1
        if context.user_data["current_question"] < len(chapter["questions"]):
            question = chapter["questions"][context.user_data["current_question"]]
            keyboard = [[InlineKeyboardButton(opt, callback_data=f"answer_{course_name}_{chapter_name}_{i}")] for i, opt in enumerate(question["options"])]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Question {context.user_data['current_question'] + 1}: {question['question']}", reply_markup=reply_markup)
        else:
            if context.user_data["correct_answers"] == len(chapter["questions"]):
                SHEET.append_row([str(user_id), username, course_name, chapter_name, "Yes"])
                chapters = courses[course_name]["chapters"]
                current_chapter_idx = next(i for i, c in enumerate(chapters) if c["name"] == chapter_name)
                if current_chapter_idx + 1 < len(chapters):
                    next_chapter = chapters[current_chapter_idx + 1]["name"]
                    keyboard = [[InlineKeyboardButton(f"Go to {next_chapter}", callback_data=f"chapter_{course_name}_{next_chapter}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.edit_text(f"Congratulations! You completed {chapter_name}.", reply_markup=reply_markup)
                else:
                    keyboard = [[InlineKeyboardButton("Select Another Course", callback_data="courses")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.edit_text(f"You have completed all chapters in {course_name}! Please select another course.", reply_markup=reply_markup)
            else:
                context.user_data["current_question"] = 0
                context.user_data["correct_answers"] = 0
                question = chapter["questions"][0]
                keyboard = [[InlineKeyboardButton(opt, callback_data=f"answer_{course_name}_{chapter_name}_{i}")] for i, opt in enumerate(question["options"])]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text(f"Study the lesson again and answer the questions carefully.\nQuestion 1: {question['question']}", reply_markup=reply_markup)

    elif data == "admin_add_course":
        await query.message.edit_text("Please enter the name of the new course:")
        context.user_data["admin_action"] = "add_course_name"

    elif data == "admin_edit_course":
        courses = load_courses()
        keyboard = [[InlineKeyboardButton(course, callback_data=f"edit_course_{course}")] for course in courses]
        keyboard.append([InlineKeyboardButton("Back", callback_data="admin")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Select a course to edit:", reply_markup=reply_markup)

    elif data == "admin_delete_course":
        courses = load_courses()
        keyboard = [[InlineKeyboardButton(course, callback_data=f"delete_course_{course}")] for course in courses]
        keyboard.append([InlineKeyboardButton("Back", callback_data="admin")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Select a course to delete:", reply_markup=reply_markup)

    elif data.startswith("edit_course_"):
        course_name = data.split("_")[2]
        context.user_data["current_course"] = course_name
        keyboard = [
            [InlineKeyboardButton("Add Chapter", callback_data=f"add_chapter_{course_name}")],
            [InlineKeyboardButton("Edit Chapter", callback_data=f"edit_chapter_{course_name}")],
            [InlineKeyboardButton("Delete Chapter", callback_data=f"delete_chapter_{course_name}")],
            [InlineKeyboardButton("Back", callback_data="admin_edit_course")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Editing {course_name}:", reply_markup=reply_markup)

    elif data.startswith("add_chapter_"):
        course_name = data.split("_")[2]
        context.user_data["current_course"] = course_name
        await query.message.edit_text(f"Enter the name of the new chapter for {course_name}:")
        context.user_data["admin_action"] = "add_chapter_name"

    elif data.startswith("edit_chapter_"):
        course_name = data.split("_")[2]
        context.user_data["current_course"] = course_name
        courses = load_courses()
        chapters = courses[course_name]["chapters"]
        keyboard = [[InlineKeyboardButton(chapter["name"], callback_data=f"edit_chapter_select_{course_name}_{chapter['name']}")] for chapter in chapters]
        keyboard.append([InlineKeyboardButton("Back", callback_data=f"edit_course_{course_name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Select a chapter to edit in {course_name}:", reply_markup=reply_markup)

    elif data.startswith("delete_chapter_"):
        course_name = data.split("_")[2]
        context.user_data["current_course"] = course_name
        courses = load_courses()
        chapters = courses[course_name]["chapters"]
        keyboard = [[InlineKeyboardButton(chapter["name"], callback_data=f"delete_chapter_select_{course_name}_{chapter['name']}")] for chapter in chapters]
        keyboard.append([InlineKeyboardButton("Back", callback_data=f"edit_course_{course_name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Select a chapter to delete in {course_name}:", reply_markup=reply_markup)

    elif data.startswith("edit_chapter_select_"):
        _, course_name, chapter_name = data.split("_", 2)
        context.user_data["current_course"] = course_name
        context.user_data["current_chapter"] = chapter_name
        keyboard = [
            [InlineKeyboardButton("Upload PDF", callback_data=f"upload_pdf_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Upload Audio", callback_data=f"upload_audio_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Add Video Link", callback_data=f"add_video_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Add Questions", callback_data=f"add_questions_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Done Uploading", callback_data=f"done_uploading_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Back", callback_data=f"edit_chapter_{course_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Editing {chapter_name} in {course_name}:", reply_markup=reply_markup)

    elif data.startswith("delete_chapter_select_"):
        _, course_name, chapter_name = data.split("_", 2)
        courses = load_courses()
        courses[course_name]["chapters"] = [c for c in courses[course_name]["chapters"] if c["name"] != chapter_name]
        save_courses(courses)
        keyboard = [[InlineKeyboardButton("Back", callback_data=f"edit_course_{course_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Chapter {chapter_name} deleted.", reply_markup=reply_markup)

    elif data.startswith("delete_course_"):
        course_name = data.split("_")[2]
        courses = load_courses()
        del courses[course_name]
        save_courses(courses)
        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_delete_course")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Course {course_name} deleted.", reply_markup=reply_markup)

    elif data.startswith("upload_pdf_"):
        _, course_name, chapter_name = data.split("_", 2)
        context.user_data["current_course"] = course_name
        context.user_data["current_chapter"] = chapter_name
        context.user_data["admin_action"] = "upload_pdf"
        await query.message.edit_text(f"Please upload the PDF for {chapter_name} in {course_name}:")

    elif data.startswith("upload_audio_"):
        _, course_name, chapter_name = data.split("_", 2)
        context.user_data["current_course"] = course_name
        context.user_data["current_chapter"] = chapter_name
        context.user_data["admin_action"] = "upload_audio"
        await query.message.edit_text(f"Please upload the audio for {chapter_name} in {course_name}:")

    elif data.startswith("add_video_"):
        _, course_name, chapter_name = data.split("_", 2)
        context.user_data["current_course"] = course_name
        context.user_data["current_chapter"] = chapter_name
        context.user_data["admin_action"] = "add_video"
        await query.message.edit_text(f"Please paste the video link for {chapter_name} in {course_name}:")

    elif data.startswith("add_questions_"):
        _, course_name, chapter_name = data.split("_", 2)
        context.user_data["current_course"] = course_name
        context.user_data["current_chapter"] = chapter_name
        context.user_data["admin_action"] = "add_question_text"
        context.user_data["current_questions"] = []
        await query.message.edit_text(f"Enter the question text for {chapter_name} in {course_name}:")

    elif data.startswith("done_uploading_"):
        _, course_name, chapter_name = data.split("_", 2)
        keyboard = [[InlineKeyboardButton("Back", callback_data=f"edit_chapter_{course_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Finished uploading for {chapter_name}.", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS and context.user_data.get("admin_action"):
        await update.message.reply_text("You are not authorized to perform this action.")
        return

    if context.user_data.get("admin_action") == "add_course_name":
        course_name = update.message.text
        courses = load_courses()
        courses[course_name] = {"chapters": []}
        save_courses(courses)
        keyboard = [[InlineKeyboardButton("Add Chapter", callback_data=f"add_chapter_{course_name}")], [InlineKeyboardButton("Back", callback_data="admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Course {course_name} added.", reply_markup=reply_markup)
        context.user_data["admin_action"] = None

    elif context.user_data.get("admin_action") == "add_chapter_name":
        course_name = context.user_data["current_course"]
        chapter_name = update.message.text
        courses = load_courses()
        courses[course_name]["chapters"].append({"name": chapter_name, "pdf": None, "audio": None, "video": None, "questions": []})
        save_courses(courses)
        keyboard = [
            [InlineKeyboardButton("Upload PDF", callback_data=f"upload_pdf_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Upload Audio", callback_data=f"upload_audio_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Add Video Link", callback_data=f"add_video_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Add Questions", callback_data=f"add_questions_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Done Uploading", callback_data=f"done_uploading_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Back", callback_data=f"edit_course_{course_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Chapter {chapter_name} added to {course_name}.", reply_markup=reply_markup)
        context.user_data["admin_action"] = None

    elif context.user_data.get("admin_action") == "upload_pdf":
        course_name = context.user_data["current_course"]
        chapter_name = context.user_data["current_chapter"]
        if update.message.document and update.message.document.mime_type == "application/pdf":
            file = await update.message.document.get_file()
            file_path = f"files/{course_name}_{chapter_name}.pdf"
            os.makedirs("files", exist_ok=True)
            await file.download_to_drive(file_path)
            courses = load_courses()
            chapter = next(c for c in courses[course_name]["chapters"] if c["name"] == chapter_name)
            chapter["pdf"] = file_path
            save_courses(courses)
            await update.message.reply_text(f"PDF uploaded for {chapter_name}.")
        else:
            await update.message.reply_text("Please upload a valid PDF file.")
        context.user_data["admin_action"] = None
        keyboard = [[InlineKeyboardButton("Back", callback_data=f"edit_chapter_select_{course_name}_{chapter_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Return to chapter editing:", reply_markup=reply_markup)

    elif context.user_data.get("admin_action") == "upload_audio":
        course_name = context.user_data["current_course"]
        chapter_name = context.user_data["current_chapter"]
        if update.message.audio or (update.message.document and update.message.document.mime_type.startswith("audio/")):
            file = await (update.message.audio or update.message.document).get_file()
            file_path = f"files/{course_name}_{chapter_name}.mp3"
            os.makedirs("files", exist_ok=True)
            await file.download_to_drive(file_path)
            courses = load_courses()
            chapter = next(c for c in courses[course_name]["chapters"] if c["name"] == chapter_name)
            chapter["audio"] = file_path
            save_courses(courses)
            await update.message.reply_text(f"Audio uploaded for {chapter_name}.")
        else:
            await update.message.reply_text("Please upload a valid audio file.")
        context.user_data["admin_action"] = None
        keyboard = [[InlineKeyboardButton("Back", callback_data=f"edit_chapter_select_{course_name}_{chapter_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Return to chapter editing:", reply_markup=reply_markup)

    elif context.user_data.get("admin_action") == "add_video":
        course_name = context.user_data["current_course"]
        chapter_name = context.user_data["current_chapter"]
        video_link = update.message.text
        courses = load_courses()
        chapter = next(c for c in courses[course_name]["chapters"] if c["name"] == chapter_name)
        chapter["video"] = video_link
        save_courses(courses)
        await update.message.reply_text(f"Video link added for {chapter_name}.")
        context.user_data["admin_action"] = None
        keyboard = [[InlineKeyboardButton("Back", callback_data=f"edit_chapter_select_{course_name}_{chapter_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Return to chapter editing:", reply_markup=reply_markup)

    elif context.user_data.get("admin_action") == "add_question_text":
        course_name = context.user_data["current_course"]
        chapter_name = context.user_data["current_chapter"]
        question_text = update.message.text
        context.user_data["current_questions"].append({"question": question_text, "options": [], "correct_answer": None})
        context.user_data["admin_action"] = "add_question_options"
        context.user_data["current_option"] = 0
        await update.message.reply_text(f"Enter option 1 for the question:")

    elif context.user_data.get("admin_action") == "add_question_options":
        course_name = context.user_data["current_course"]
        chapter_name = context.user_data["current_chapter"]
        option_text = update.message.text
        context.user_data["current_questions"][-1]["options"].append(option_text)
        context.user_data["current_option"] += 1
        if context.user_data["current_option"] < 4:
            await update.message.reply_text(f"Enter option {context.user_data['current_option'] + 1} for the question:")
        else:
            await update.message.reply_text("Enter the index (0-3) of the correct answer:")
            context.user_data["admin_action"] = "add_question_correct"

    elif context.user_data.get("admin_action") == "add_question_correct":
        course_name = context.user_data["current_course"]
        chapter_name = context.user_data["current_chapter"]
        correct_answer = int(update.message.text)
        context.user_data["current_questions"][-1]["correct_answer"] = correct_answer
        courses = load_courses()
        chapter = next(c for c in courses[course_name]["chapters"] if c["name"] == chapter_name)
        chapter["questions"].append(context.user_data["current_questions"][-1])
        save_courses(courses)
        keyboard = [
            [InlineKeyboardButton("Add Another Question", callback_data=f"add_questions_{course_name}_{chapter_name}")],
            [InlineKeyboardButton("Done Adding Questions", callback_data=f"edit_chapter_select_{course_name}_{chapter_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Question added. Would you like to add another?", reply_markup=reply_markup)
        context.user_data["admin_action"] = None
        context.user_data["current_questions"] = []
        context.user_data["current_option"] = 0

# Webhook handler
@app.route('/', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return '', 200

async def set_webhook():
    await application.bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/")

def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL | filters.Audio.ALL, handle_message))
    application.run_webhook(listen="0.0.0.0", port=int(os.getenv("PORT", 8443)), webhook_url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8443)))