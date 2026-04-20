import requests
import psycopg2
import speech_recognition as sr
import pyttsx3
import re

# -------------------------------
# 🔊 VOICE OUTPUT
# -------------------------------
engine = pyttsx3.init()
engine.setProperty('rate', 160)

voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)  # female voice



def speak(text):
    print("\n🔊:", text)
    engine.say(text)
    engine.runAndWait()

import speech_recognition as sr

recognizer = sr.Recognizer()

with sr.Microphone() as source:
    print("🎤 Speak...")
    recognizer.adjust_for_ambient_noise(source, duration=1)
    audio = recognizer.listen(source)

try:
    text = recognizer.recognize_google(audio).lower()
    print("You said:", text)
except:
    speak("Sorry, I could not understand")
    exit()


# -------------------------------
# 🧠 MASTER PROMPT (LLM BRAIN)
# -------------------------------
prompt = f"""
You are an expert PostgreSQL query generator.

Convert natural language into VALID SQL.

-----------------------------------
DATABASE SCHEMA
-----------------------------------

Table: time_table
Columns:
faculty, subject, day, period,
starting_time, ending_time,
section, room_number

Table: faculty
Columns:
faculty_name, faculty_id,
faculty_designation, faculty_qualification,
date_of_joining, experience_in_months

-----------------------------------
STRICT RULES
-----------------------------------

1. ONLY return SQL query (no explanation)
2. DO NOT include any extra text
3. ALWAYS use DISTINCT
4. ALWAYS use ILIKE for matching dynamically:
   faculty ILIKE '%<name>%'
   faculty_name ILIKE '%<name>%'
   subject ILIKE '%<subject>%'

-----------------------------------
JOIN RULE (STRICT)
-----------------------------------

DO NOT use JOIN for timetable queries.

Use ONLY time_table for:
- timetable
- subjects
- student queries

Use faculty table ONLY when user asks for:
- qualification
- designation
- experience


-----------------------------------
NAME MATCHING RULE (CRITICAL)
-----------------------------------

User may not say exact faculty name.

ALWAYS use flexible matching for names:

- Break name into parts if needed
- Use ILIKE with partial match



DO NOT rely on exact spelling.


-----------------------------------
IMPORTANT MATCHING RULES
-----------------------------------

- NEVER hardcode any names
- ALWAYS extract values from user input

SECTION MATCHING (VERY IMPORTANT):
DO NOT use exact match like '%2 CSM%'

INSTEAD use flexible matching:
section ILIKE '%<year>%'
AND section ILIKE '%<branch_or_section>%'

-----------------------------------
SECTION UNDERSTANDING
-----------------------------------

Interpret user input:

- "2nd year" → '%2%'
- "second year" → '%2%'

- "3rd year section A" → '%3%' AND '%a%'
- "3rd year section B" → '%3%' AND '%b%'

-----------------------------------
TIME RULES
-----------------------------------

Current class:
CURRENT_TIME BETWEEN starting_time AND ending_time

Today:
TRIM(day) = TRIM(TO_CHAR(CURRENT_DATE, 'Day'))

Tomorrow:
TRIM(day) = TRIM(TO_CHAR(CURRENT_DATE + 1, 'Day'))

-----------------------------------
INTENT DETECTION RULES
-----------------------------------

- If question is about subjects → return subject column
- If question is about faculty → return faculty column
- If question is about location → return room_number
- If question is about timetable → return subject, day, period, room_number
- If question is about faculty details → use faculty table

-----------------------------------
JOIN RULE
-----------------------------------

When both tables are needed:

FROM time_table t
JOIN faculty f
ON t.faculty = f.faculty_name


-----------------------------------
TIME FILTER RULE (VERY IMPORTANT)
-----------------------------------

ONLY use:
CURRENT_TIME BETWEEN starting_time AND ending_time

WHEN user asks:
- where is faculty
- where are students
- current location

-----------------------------------

DO NOT use CURRENT_TIME condition for:
- timetable queries
- subjects queries
- future queries (like tomorrow)

-----------------------------------


-----------------------------------
TIMETABLE OUTPUT RULE (CRITICAL)
-----------------------------------

When user asks for timetable:

DO NOT return raw rows like:
subject, day, period, time, room_number

INSTEAD:

- Group by day
- Order by period
- Avoid repeating day multiple times
- Avoid repeating room if same

FORMAT SQL like:

SELECT
    day,
    STRING_AGG(
        subject || ' (P' || period ||
        CASE
            WHEN room_number IS NOT NULL THEN ', Room ' || room_number
            ELSE ''
        END,
        ', ' ORDER BY period
    ) AS schedule
FROM time_table
WHERE <conditions>
GROUP BY day
ORDER BY day;

-----------------------------------
OUTPUT EXPECTATION
-----------------------------------

Return clean grouped result like:

Wednesday:
DBMS (P2, Room T9), ML (P8), OT (P1)

NOT:
DBMS, Wednesday, 2, T9 ❌
-----------------------------------
FINAL INSTRUCTION
-----------------------------------

- Generate SQL dynamically for ANY faculty
- Generate SQL dynamically for ANY subject
- Generate SQL dynamically for ANY section
- DO NOT assume or hardcode any values
- DO NOT include explanations

-----------------------------------

User request:
{text}
"""

# -------------------------------
# 🤖 CALL OLLAMA
# -------------------------------
try:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        }
    )

    raw_output = response.json()["response"].strip()
    print("\n🧠 Raw LLM Output:\n", raw_output)

except:
    speak("Ollama is not running")
    exit()

# -------------------------------
# 🧹 EXTRACT SQL
# -------------------------------
match = re.search(r"(SELECT|INSERT|UPDATE|DELETE).*?;", raw_output, re.I | re.S)

if not match:
    speak("Failed to generate SQL")
    exit()

sql_query = match.group(0)

# -------------------------------
# 🛡️ SAFETY FIXES
# -------------------------------
sql_query = sql_query.replace("room__number", "room_number")
sql_query = sql_query.replace("NOW()", "CURRENT_TIME")

print("\n✅ Final SQL:\n", sql_query)

# -------------------------------
# 🗄️ DATABASE
# -------------------------------
try:
    conn = psycopg2.connect(
        host="localhost",
        database="pgvector_db",
        user="postgres",
        password="abc@mn"   # 🔴 CHANGE THIS
    )
    cur = conn.cursor()
except:
    speak("Database connection failed")
    exit()

# -------------------------------
# ▶️ EXECUTE
# -------------------------------
try:
    cur.execute(sql_query)
    result = cur.fetchall()

    if result:
        unique = list(set(", ".join(map(str, row)) for row in result))
        answer = ". ".join(unique)

        print("\n📊 Result:\n", answer)
        speak(answer)
    else:
        speak("No data found")

except Exception as e:
    print("SQL Error:", e)
    speak("There was an error executing the query")

conn.close()